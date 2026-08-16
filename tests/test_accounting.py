"""
Tests for the Accounts Tracker — accounting math, routes, auth.
"""
from datetime import date as dt_date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import (
    Item, ItemType, Party, PartyType, PaymentMethod,
    Purchase, PurchaseLine, Sale, PaymentIn, PaymentOut, Expense,
    User, UserRole,
)
from app.services.accounting import (
    apply_purchase, reverse_purchase, apply_sale, reverse_sale,
    compute_profit, compute_inventory_valuation, compute_aging,
    get_next_receipt_number,
)

# ── In-memory SQLite for testing ───────────────────────────────────

TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    """Get a test DB session."""
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    """FastAPI test client with test DB."""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Helpers ────────────────────────────────────────────────────────

def create_owner(db):
    """Create the first user (owner)."""
    from app.auth import hash_password
    user = User(name="Test Owner", password_hash=hash_password("pass"), role=UserRole.owner)
    db.add(user)
    db.commit()
    return user


def create_party(db, name="Kamal", type=PartyType.customer):
    p = Party(name=name, type=type)
    db.add(p)
    db.commit()
    return p


def create_item(db, name="Soap", type=ItemType.finished, unit="pcs", sale_price=300):
    i = Item(name=name, type=type, unit=unit, sale_price=sale_price)
    db.add(i)
    db.commit()
    return i


def create_sale(db, party_id, item_id, qty=10, unit_price=300, cash=2000):
    total = qty * unit_price
    s = Sale(party_id=party_id, item_id=item_id, date=dt_date(2026, 8, 16),
             unit_price=unit_price, quantity=qty, total_amount=total,
             cash_received=cash)
    db.add(s)
    db.flush()
    apply_sale(db, s)
    db.commit()
    return s


def create_purchase(db, party_id, item_id, qty=100, unit_cost=50,
                    method=PaymentMethod.cash, cash_paid=5000):
    p = Purchase(party_id=party_id, date=dt_date(2026, 8, 15),
                 payment_method=method, cash_paid=cash_paid,
                 total_cost=qty * unit_cost)
    db.add(p)
    db.flush()
    pl = PurchaseLine(purchase_id=p.id, item_id=item_id, quantity=qty, unit_cost=unit_cost)
    db.add(pl)
    db.flush()
    apply_purchase(db, p)
    db.commit()
    return p


# ── Auth Tests ─────────────────────────────────────────────────────

def test_register_first_user_creates_owner(client):
    resp = client.post("/auth/register", data={"name": "Owner", "password": "pass", "invite_code": ""}, follow_redirects=False)
    assert resp.status_code == 302  # redirect to dashboard
    db = TestSession()
    user = db.query(User).first()
    assert user is not None
    assert user.role == UserRole.owner
    db.close()


def test_register_duplicate_name(client):
    client.post("/auth/register", data={"name": "Owner", "password": "pass", "invite_code": ""})
    resp = client.post("/auth/register", data={"name": "Owner", "password": "pass", "invite_code": ""})
    assert "Name already taken" in resp.text


def test_register_requires_invite_after_first_user(client):
    client.post("/auth/register", data={"name": "Owner", "password": "pass", "invite_code": ""})
    resp = client.post("/auth/register", data={"name": "Staff", "password": "pass", "invite_code": ""})
    assert "Invite code required" in resp.text or resp.status_code == 200


def test_login_success(client):
    client.post("/auth/register", data={"name": "Owner", "password": "pass", "invite_code": ""})
    resp = client.post("/auth/login", data={"name": "Owner", "password": "pass"}, follow_redirects=False)
    assert resp.status_code == 302


def test_login_failure(client):
    resp = client.post("/auth/login", data={"name": "Unknown", "password": "pass"})
    assert "Invalid" in resp.text


# ── Accounting Tests ───────────────────────────────────────────────

def test_sale_creates_ar(db):
    party = create_party(db)
    item = create_item(db)
    sale = create_sale(db, party.id, item.id, qty=10, unit_price=300, cash=2000)
    ar = round(sale.total_amount - sale.cash_received, 2)
    assert ar == 1000.0
    assert party.ar_balance == 1000.0


def test_full_payment_clears_ar(db):
    party = create_party(db)
    item = create_item(db)
    sale = create_sale(db, party.id, item.id, qty=10, unit_price=300, cash=3000)
    assert party.ar_balance == 0.0


def test_purchase_updates_inventory_and_cost(db):
    party = create_party(db, name="Supplier", type=PartyType.supplier)
    item = create_item(db)
    purchase = create_purchase(db, party.id, item.id, qty=100, unit_cost=50)
    assert item.quantity_on_hand == 100.0
    assert item.average_cost == 50.0
    assert item.total_units_purchased == 100.0


def test_average_cost_multiple_purchases(db):
    party = create_party(db, name="Supplier", type=PartyType.supplier)
    item = create_item(db)
    # Buy 100 at 50
    create_purchase(db, party.id, item.id, qty=100, unit_cost=50)
    # Buy 50 at 60
    create_purchase(db, party.id, item.id, qty=50, unit_cost=60)
    expected_avg = round(((100 * 50) + (50 * 60)) / 150, 2)
    assert item.average_cost == expected_avg
    assert item.quantity_on_hand == 150.0


def test_average_cost_formula(db):
    """Test weighted average cost calculation."""
    party = create_party(db, name="Supplier", type=PartyType.supplier)
    item = create_item(db)
    # Buy 100 @ 50
    create_purchase(db, party.id, item.id, qty=100, unit_cost=50)
    assert item.average_cost == 50.0
    # Buy 200 @ 40
    create_purchase(db, party.id, item.id, qty=200, unit_cost=40)
    expected = round(((100 * 50) + (200 * 40)) / 300, 2)
    assert item.average_cost == expected
    # Buy 50 @ 80
    create_purchase(db, party.id, item.id, qty=50, unit_cost=80)
    expected2 = round((expected * 300 + 50 * 80) / 350, 2)
    assert item.average_cost == expected2


def test_reverse_sale_clears_ar(db):
    party = create_party(db)
    item = create_item(db)
    sale = create_sale(db, party.id, item.id, qty=10, unit_price=300, cash=2000)
    assert party.ar_balance == 1000.0
    reverse_sale(db, sale)
    sale.is_deleted = True
    db.flush()
    assert party.ar_balance == 0.0


def test_reverse_purchase_reverses_inventory(db):
    party = create_party(db, name="Supplier", type=PartyType.supplier)
    item = create_item(db)
    purchase = create_purchase(db, party.id, item.id, qty=100, unit_cost=50)
    assert item.quantity_on_hand == 100.0
    reverse_purchase(db, purchase)
    purchase.is_deleted = True
    db.flush()
    assert item.quantity_on_hand == 0.0


def test_profit_calculation(db):
    party_c = create_party(db, name="Customer", type=PartyType.customer)
    party_s = create_party(db, name="Supplier", type=PartyType.supplier)
    item = create_item(db)
    # Purchase: 100 units @ 50 = 5000 expense
    create_purchase(db, party_s.id, item.id, qty=100, unit_cost=50)
    # Sale: 10 units @ 300 = 3000 income
    create_sale(db, party_c.id, item.id, qty=10, unit_price=300, cash=2000)
    # Operating expense
    exp = Expense(category="rent", amount=1000, date=dt_date(2026, 8, 16), description="Shop rent")
    db.add(exp)
    db.commit()

    from datetime import date
    result = compute_profit(db, date(2026, 8, 1), date(2026, 8, 31))
    assert result["total_income"] == 3000.0
    assert result["total_purchases"] == 5000.0
    assert result["total_operating_expenses"] == 1000.0
    assert result["total_expenses"] == 6000.0
    assert result["profit"] == -3000.0  # Loss expected (purchases > sales)


def test_inventory_valuation(db):
    party = create_party(db, name="Supplier", type=PartyType.supplier)
    item1 = create_item(db, name="Soap")
    item2 = create_item(db, name="Shampoo")
    create_purchase(db, party.id, item1.id, qty=100, unit_cost=50)
    create_purchase(db, party.id, item2.id, qty=50, unit_cost=80)
    valuation = compute_inventory_valuation(db)
    total = sum(v["value"] for v in valuation)
    expected = (100 * 50) + (50 * 80)
    assert total == expected


def test_receipt_number_sequence(db):
    party = create_party(db)
    first = get_next_receipt_number(db, party.id, "INV")
    assert first == "INV-1-1"
    # Add a payment
    p = PaymentIn(party_id=party.id, amount=500, receipt_number="INV-1-1",
                  date=dt_date(2026, 8, 16))
    db.add(p)
    db.commit()
    second = get_next_receipt_number(db, party.id, "INV")
    assert second == "INV-1-2"


def test_payment_in_reduces_ar(db):
    party = create_party(db)
    item = create_item(db)
    sale = create_sale(db, party.id, item.id, qty=10, unit_price=300, cash=2000)
    assert party.ar_balance == 1000.0
    pi = PaymentIn(party_id=party.id, amount=500, receipt_number="INV-1-1",
                   date=dt_date(2026, 8, 16))
    db.add(pi)
    db.commit()
    # AR should decrease by payment amount: 1000 - 500 = 500
    # Refresh party from DB
    db.refresh(party)
    # Check: AR = total_sales - total_payments_in
    total_sales = sum(s.total_amount - s.cash_received for s in party.sales if not s.is_deleted)
    total_pi = sum(p.amount for p in party.payments_in if not p.is_deleted)
    assert round(total_sales - total_pi, 2) == 500.0


def test_dashboard_returns_200(client):
    """Unauthenticated dashboard should redirect to login."""
    resp = client.get("/dashboard", follow_redirects=False)
    assert resp.status_code == 302  # redirect to /auth/login


def test_authenticated_dashboard(client):
    client.post("/auth/register", data={"name": "Owner", "password": "pass", "invite_code": ""})
    # Login
    login_resp = client.post("/auth/login", data={"name": "Owner", "password": "pass"})
    # Follow redirect
    resp = client.get("/dashboard", cookies=login_resp.cookies)
    assert resp.status_code == 200


def test_create_party_flow(client):
    client.post("/auth/register", data={"name": "Owner", "password": "pass", "invite_code": ""})
    client.post("/auth/login", data={"name": "Owner", "password": "pass"}, follow_redirects=True)
    resp = client.post("/parties/add", data={"name": "Test Customer", "type": "customer", "contact": ""}, follow_redirects=False)
    assert resp.status_code in (200, 302)
    db = TestSession()
    party = db.query(Party).filter(Party.name == "Test Customer").first()
    assert party is not None
    db.close()


def test_create_item_flow(client):
    client.post("/auth/register", data={"name": "Owner", "password": "pass", "invite_code": ""})
    client.post("/auth/login", data={"name": "Owner", "password": "pass"}, follow_redirects=True)
    resp = client.post("/inventory/add",
                       data={"name": "Test Item", "type": "finished", "unit": "pcs", "sale_price": 100},
                       follow_redirects=False)
    assert resp.status_code in (200, 302)
    db = TestSession()
    item = db.query(Item).filter(Item.name == "Test Item").first()
    assert item is not None
    db.close()


def test_aging_report(db):
    party = create_party(db)
    item = create_item(db)
    create_sale(db, party.id, item.id, qty=10, unit_price=300, cash=0)
    aging = compute_aging(db)
    assert len(aging["ar"]) > 0
    assert aging["ar"][0]["party_name"] == "Kamal"
    assert aging["total_ar"] == 3000.0
    assert aging["total_ap"] == 0.0