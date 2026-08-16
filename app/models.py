"""
SQLAlchemy ORM models for the Accounts Tracker.
"""
import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ── Enums ──────────────────────────────────────────────────────────

class PartyType(str, enum.Enum):
    customer = "customer"
    supplier = "supplier"
    both = "both"


class ItemType(str, enum.Enum):
    finished = "finished"
    raw_material = "raw_material"


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    credit = "credit"


class PaymentInOutMethod(str, enum.Enum):
    cash = "cash"
    check = "check"


class UserRole(str, enum.Enum):
    owner = "owner"
    staff = "staff"


# ── User ───────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.staff, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    max_uses = Column(Integer, default=0)  # 0 = unlimited
    uses = Column(Integer, default=0)
    expires_at = Column(Date, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    creator = relationship("User")


# ── Party ──────────────────────────────────────────────────────────

class Party(Base):
    __tablename__ = "parties"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, index=True)
    type = Column(Enum(PartyType), nullable=False, default=PartyType.customer)
    contact = Column(String(100), nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Computed balances (live from related records)
    @property
    def ar_balance(self) -> float:
        """Total outstanding amount customers owe us (for this party)."""
        total_sales = sum(
            (s.total_amount - s.cash_received)
            for s in self.sales if not s.is_deleted
        )
        total_payments_in = sum(
            p.amount for p in self.payments_in if not p.is_deleted
        )
        return round(total_sales - total_payments_in, 2)

    @property
    def ap_balance(self) -> float:
        """Total amount we owe suppliers (for this party)."""
        total_purchases = sum(
            p.total_cost for p in self.purchases
            if not p.is_deleted and p.payment_method == PaymentMethod.credit
        )
        total_payments_out = sum(
            p.amount for p in self.payments_out if not p.is_deleted
        )
        return round(total_purchases - total_payments_out, 2)

    # Relationships
    sales = relationship("Sale", back_populates="party", foreign_keys="Sale.party_id")
    purchases = relationship("Purchase", back_populates="party", foreign_keys="Purchase.party_id")
    payments_in = relationship("PaymentIn", back_populates="party")
    payments_out = relationship("PaymentOut", back_populates="party")


# ── Item (Inventory) ───────────────────────────────────────────────

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    sku = Column(String(50), nullable=True, unique=True)
    type = Column(Enum(ItemType), nullable=False, default=ItemType.finished)
    unit = Column(String(20), nullable=False, default="pcs")
    quantity_on_hand = Column(Float, default=0.0)
    total_units_purchased = Column(Float, default=0.0)
    total_units_sold = Column(Float, default=0.0)
    average_cost = Column(Float, default=0.0)
    sale_price = Column(Float, default=0.0)
    reorder_level = Column(Float, default=0.0)
    reorder_quantity = Column(Float, default=0.0)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    @property
    def is_low_stock(self) -> bool:
        return self.reorder_level > 0 and self.quantity_on_hand < self.reorder_level

    @property
    def value(self) -> float:
        return round(self.quantity_on_hand * self.average_cost, 2)

    purchase_lines = relationship("PurchaseLine", back_populates="item")
    sales = relationship("Sale", back_populates="item")


# ── Purchase ───────────────────────────────────────────────────────

class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True)
    party_id = Column(Integer, ForeignKey("parties.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, default=date.today)
    payment_method = Column(Enum(PaymentMethod), nullable=False, default=PaymentMethod.cash)
    cash_paid = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    party = relationship("Party", back_populates="purchases", foreign_keys=[party_id])
    lines = relationship(
        "PurchaseLine", back_populates="purchase",
        cascade="all, delete-orphan",
    )


class PurchaseLine(Base):
    __tablename__ = "purchase_lines"

    id = Column(Integer, primary_key=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_cost = Column(Float, nullable=False)

    purchase = relationship("Purchase", back_populates="lines")
    item = relationship("Item", back_populates="purchase_lines")


# ── Sale ───────────────────────────────────────────────────────────

class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True)
    party_id = Column(Integer, ForeignKey("parties.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, default=date.today)
    unit_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    cash_received = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    party = relationship("Party", back_populates="sales", foreign_keys=[party_id])
    item = relationship("Item", back_populates="sales")


# ── Payment In (reducing AR) ───────────────────────────────────────

class PaymentIn(Base):
    __tablename__ = "payments_in"

    id = Column(Integer, primary_key=True)
    party_id = Column(Integer, ForeignKey("parties.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    receipt_number = Column(String(20), nullable=False)
    date = Column(Date, nullable=False, default=date.today)
    method = Column(Enum(PaymentInOutMethod), default=PaymentInOutMethod.cash)
    notes = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    party = relationship("Party", back_populates="payments_in")


# ── Payment Out (reducing AP) ──────────────────────────────────────

class PaymentOut(Base):
    __tablename__ = "payments_out"

    id = Column(Integer, primary_key=True)
    party_id = Column(Integer, ForeignKey("parties.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    receipt_number = Column(String(20), nullable=False)
    date = Column(Date, nullable=False, default=date.today)
    method = Column(Enum(PaymentInOutMethod), default=PaymentInOutMethod.cash)
    notes = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    party = relationship("Party", back_populates="payments_out")


# ── Expense ────────────────────────────────────────────────────────

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    category = Column(String(50), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False, default=date.today)
    description = Column(Text, nullable=True)
    party_id = Column(Integer, ForeignKey("parties.id"), nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    party = relationship("Party")


# ── Stock Adjustment ───────────────────────────────────────────────

class StockAdjustment(Base):
    __tablename__ = "stock_adjustments"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    quantity = Column(Float, nullable=False)  # negative = deduction
    reason = Column(String(200), nullable=True)
    date = Column(Date, nullable=False, default=date.today)
    created_at = Column(DateTime, server_default=func.now())

    item = relationship("Item")