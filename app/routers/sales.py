"""
Sales CRUD routes.
"""
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import render
from app.middleware import require_auth
from app.models import Item, Party, PartyType, Sale
from app.services.accounting import apply_sale, reverse_sale

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("")
@router.get("/")
async def list_sales(
    request: Request,
    search: str = "",
    date_from: str = "",
    date_to: str = "",
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    query = db.query(Sale).filter(Sale.is_deleted == False)

    if search:
        query = query.join(Party).filter(Party.name.ilike(f"%{search}%"))

    if date_from:
        try:
            query = query.filter(Sale.date >= date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Sale.date <= date.fromisoformat(date_to))
        except ValueError:
            pass

    sales = query.order_by(Sale.date.desc()).all()
    customers = db.query(Party).filter(
        Party.is_deleted == False,
        Party.type.in_([PartyType.customer, PartyType.both]),
    ).order_by(Party.name).all()
    items = db.query(Item).filter(Item.is_deleted == False).order_by(Item.name).all()

    return render(request, "sales/list.html",
        sales=sales,
        customers=customers,
        items=items,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/add")
async def add_sale(
    request: Request,
    party_id: int = Form(...),
    item_id: int = Form(...),
    date_str: str = Form(...),
    unit_price: float = Form(...),
    quantity: float = Form(...),
    total_amount: float = Form(...),
    cash_received: float = Form(0.0),
    notes: str = Form(default=""),
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    try:
        sale_date = date.fromisoformat(date_str)
    except ValueError:
        sale_date = date.today()

    sale = Sale(
        party_id=party_id,
        item_id=item_id,
        date=sale_date,
        unit_price=unit_price,
        quantity=quantity,
        total_amount=total_amount,
        cash_received=cash_received,
        notes=notes.strip(),
    )
    db.add(sale)
    db.flush()

    apply_sale(db, sale)
    db.commit()

    return RedirectResponse(url="/sales", status_code=302)


@router.get("/detail/{sale_id}")
async def sale_detail(
    request: Request,
    sale_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if not sale:
        return RedirectResponse(url="/sales", status_code=302)

    ar_remaining = round(sale.total_amount - sale.cash_received, 2)
    return render(request, "sales/detail.html", sale=sale, ar_remaining=ar_remaining)


@router.post("/delete/{sale_id}")
async def delete_sale(
    request: Request,
    sale_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if sale and not sale.is_deleted:
        reverse_sale(db, sale)
        sale.is_deleted = True
        db.commit()

    return RedirectResponse(url="/sales", status_code=302)


@router.post("/restore/{sale_id}")
async def restore_sale(
    request: Request,
    sale_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if sale and sale.is_deleted:
        sale.is_deleted = False
        apply_sale(db, sale)
        db.commit()

    return RedirectResponse(url="/sales", status_code=302)