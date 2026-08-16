"""
Purchases CRUD routes.
"""
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import render
from app.middleware import require_auth
from app.models import Item, Party, PartyType, PaymentMethod, Purchase, PurchaseLine
from app.services.accounting import apply_purchase, reverse_purchase

router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.get("")
@router.get("/")
async def list_purchases(
    request: Request,
    search: str = "",
    date_from: str = "",
    date_to: str = "",
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    query = db.query(Purchase).filter(Purchase.is_deleted == False)

    if search:
        query = query.join(Party).filter(Party.name.ilike(f"%{search}%"))

    if date_from:
        try:
            query = query.filter(Purchase.date >= date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Purchase.date <= date.fromisoformat(date_to))
        except ValueError:
            pass

    purchases = query.order_by(Purchase.date.desc()).all()
    suppliers = db.query(Party).filter(
        Party.is_deleted == False,
        Party.type.in_([PartyType.supplier, PartyType.both]),
    ).order_by(Party.name).all()
    items = db.query(Item).filter(Item.is_deleted == False).order_by(Item.name).all()

    return render(request, "purchases/list.html",
        purchases=purchases,
        suppliers=suppliers,
        items=items,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/add")
async def add_purchase(
    request: Request,
    party_id: int = Form(...),
    date_str: str = Form(...),
    payment_method: str = Form("cash"),
    cash_paid: float = Form(0.0),
    notes: str = Form(default=""),
    item_ids: list[int] = Form(default=[]),
    quantities: list[float] = Form(default=[]),
    unit_costs: list[float] = Form(default=[]),
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    try:
        purchase_date = date.fromisoformat(date_str)
    except ValueError:
        purchase_date = date.today()

    purchase = Purchase(
        party_id=party_id,
        date=purchase_date,
        payment_method=PaymentMethod(payment_method),
        cash_paid=cash_paid,
        notes=notes.strip(),
    )
    db.add(purchase)
    db.flush()

    total_cost = 0
    for i in range(len(item_ids or [])):
        qty = quantities[i] if i < len(quantities) else 0
        cost = unit_costs[i] if i < len(unit_costs) else 0
        if qty <= 0 or cost <= 0:
            continue
        line = PurchaseLine(
            purchase_id=purchase.id,
            item_id=item_ids[i],
            quantity=qty,
            unit_cost=cost,
        )
        db.add(line)
        total_cost += qty * cost

    purchase.total_cost = round(total_cost, 2)
    if payment_method == "cash":
        purchase.cash_paid = min(cash_paid, total_cost)

    db.flush()
    apply_purchase(db, purchase)
    db.commit()

    return RedirectResponse(url="/purchases", status_code=302)


@router.get("/detail/{purchase_id}")
async def purchase_detail(
    request: Request,
    purchase_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not purchase:
        return RedirectResponse(url="/purchases", status_code=302)

    return render(request, "purchases/detail.html", purchase=purchase)


@router.post("/delete/{purchase_id}")
async def delete_purchase(
    request: Request,
    purchase_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if purchase and not purchase.is_deleted:
        reverse_purchase(db, purchase)
        purchase.is_deleted = True
        db.commit()

    return RedirectResponse(url="/purchases", status_code=302)


@router.post("/restore/{purchase_id}")
async def restore_purchase(
    request: Request,
    purchase_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if purchase and purchase.is_deleted:
        purchase.is_deleted = False
        apply_purchase(db, purchase)
        db.commit()

    return RedirectResponse(url="/purchases", status_code=302)