"""
Payments routes — Payment In (reducing AR) and Payment Out (reducing AP).
"""
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import render
from app.middleware import require_auth
from app.models import (
    Party, PartyType, PaymentIn, PaymentInOutMethod, PaymentOut,
)
from app.services.accounting import get_next_receipt_number

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("")
@router.get("/")
async def list_payments(
    request: Request,
    search: str = "",
    type_filter: str = "all",
    date_from: str = "",
    date_to: str = "",
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    payments_in = []
    payments_out = []

    if type_filter in ("all", "incoming"):
        q = db.query(PaymentIn).filter(PaymentIn.is_deleted == False)
        if search:
            q = q.join(Party).filter(Party.name.ilike(f"%{search}%"))
        if date_from:
            try:
                q = q.filter(PaymentIn.date >= date.fromisoformat(date_from))
            except ValueError:
                pass
        if date_to:
            try:
                q = q.filter(PaymentIn.date <= date.fromisoformat(date_to))
            except ValueError:
                pass
        payments_in = q.order_by(PaymentIn.date.desc()).all()

    if type_filter in ("all", "outgoing"):
        q = db.query(PaymentOut).filter(PaymentOut.is_deleted == False)
        if search:
            q = q.join(Party).filter(Party.name.ilike(f"%{search}%"))
        if date_from:
            try:
                q = q.filter(PaymentOut.date >= date.fromisoformat(date_from))
            except ValueError:
                pass
        if date_to:
            try:
                q = q.filter(PaymentOut.date <= date.fromisoformat(date_to))
            except ValueError:
                pass
        payments_out = q.order_by(PaymentOut.date.desc()).all()

    customers = db.query(Party).filter(
        Party.is_deleted == False,
        Party.type.in_([PartyType.customer, PartyType.both]),
    ).order_by(Party.name).all()

    suppliers = db.query(Party).filter(
        Party.is_deleted == False,
        Party.type.in_([PartyType.supplier, PartyType.both]),
    ).order_by(Party.name).all()

    return render(request, "payments/list.html",
        payments_in=payments_in,
        payments_out=payments_out,
        customers=customers,
        suppliers=suppliers,
        search=search,
        type_filter=type_filter,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/add-in")
async def add_payment_in(
    request: Request,
    party_id: int = Form(...),
    amount: float = Form(...),
    date_str: str = Form(...),
    method: str = Form("cash"),
    notes: str = Form(default=""),
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    try:
        pdate = date.fromisoformat(date_str)
    except ValueError:
        pdate = date.today()

    receipt = get_next_receipt_number(db, party_id, "INV")

    payment = PaymentIn(
        party_id=party_id,
        amount=amount,
        receipt_number=receipt,
        date=pdate,
        method=PaymentInOutMethod(method),
        notes=notes.strip(),
    )
    db.add(payment)
    db.commit()

    return RedirectResponse(url="/payments", status_code=302)


@router.post("/add-out")
async def add_payment_out(
    request: Request,
    party_id: int = Form(...),
    amount: float = Form(...),
    date_str: str = Form(...),
    method: str = Form("cash"),
    notes: str = Form(default=""),
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    try:
        pdate = date.fromisoformat(date_str)
    except ValueError:
        pdate = date.today()

    receipt = get_next_receipt_number(db, party_id, "POUT")

    payment = PaymentOut(
        party_id=party_id,
        amount=amount,
        receipt_number=receipt,
        date=pdate,
        method=PaymentInOutMethod(method),
        notes=notes.strip(),
    )
    db.add(payment)
    db.commit()

    return RedirectResponse(url="/payments", status_code=302)


@router.post("/delete-in/{payment_id}")
async def delete_payment_in(
    request: Request,
    payment_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    payment = db.query(PaymentIn).filter(PaymentIn.id == payment_id).first()
    if payment:
        payment.is_deleted = True
        db.commit()

    return RedirectResponse(url="/payments", status_code=302)


@router.post("/delete-out/{payment_id}")
async def delete_payment_out(
    request: Request,
    payment_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    payment = db.query(PaymentOut).filter(PaymentOut.id == payment_id).first()
    if payment:
        payment.is_deleted = True
        db.commit()

    return RedirectResponse(url="/payments", status_code=302)