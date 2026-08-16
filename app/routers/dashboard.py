"""
Dashboard route — homepage with summary cards, quick actions, recent activity.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import render
from app.middleware import require_auth
from app.models import Expense, Item, Party, PaymentIn, PaymentOut, Purchase, Sale, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
@router.get("/")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_auth(getattr(request.state, "user", None))
    today = date.today()

    # Today's cash flow
    sales_today = (
        db.query(sa_func.coalesce(sa_func.sum(Sale.cash_received), 0))
        .filter(Sale.date == today, Sale.is_deleted == False)
        .scalar()
    ) or 0
    cash_in_from_payments = (
        db.query(sa_func.coalesce(sa_func.sum(PaymentIn.amount), 0))
        .filter(PaymentIn.date == today, PaymentIn.is_deleted == False)
        .scalar()
    ) or 0
    purchases_today = (
        db.query(sa_func.coalesce(sa_func.sum(Purchase.cash_paid), 0))
        .filter(Purchase.date == today, Purchase.is_deleted == False)
        .scalar()
    ) or 0
    payments_out_today = (
        db.query(sa_func.coalesce(sa_func.sum(PaymentOut.amount), 0))
        .filter(PaymentOut.date == today, PaymentOut.is_deleted == False)
        .scalar()
    ) or 0
    expenses_today = (
        db.query(sa_func.coalesce(sa_func.sum(Expense.amount), 0))
        .filter(Expense.date == today, Expense.is_deleted == False)
        .scalar()
    ) or 0
    cash_in = float(sales_today) + float(cash_in_from_payments)
    cash_out = float(purchases_today) + float(payments_out_today) + float(expenses_today)
    today_cash = round(cash_in - cash_out, 2)

    # Inventory value
    items = db.query(Item).filter(Item.is_deleted == False).all()
    inventory_value = round(sum(i.value for i in items), 2)

    # AR / AP totals
    parties = db.query(Party).filter(Party.is_deleted == False).all()
    total_ar = round(sum(p.ar_balance for p in parties), 2)
    total_ap = round(sum(p.ap_balance for p in parties), 2)

    # Low stock items
    low_stock = [i for i in items if i.is_low_stock]

    # Recent activity (last 15 transactions across all types)
    recent = _get_recent_activity(db)

    return render(request, "dashboard.html",
        today_cash=today_cash,
        inventory_value=inventory_value,
        total_ar=total_ar,
        total_ap=total_ap,
        low_stock=low_stock,
        recent=recent,
    )


def _get_recent_activity(db: Session, limit: int = 15):
    """Get the most recent transactions across all types.
    Fetches each type separately and merges in Python to avoid SQL UNION column aliasing issues.
    """
    from datetime import date as dt_date
    result = []

    sales = db.query(Sale).filter(Sale.is_deleted == False).order_by(Sale.date.desc()).limit(limit).all()
    for s in sales:
        party = db.query(Party).filter(Party.id == s.party_id).first()
        result.append({
            "type": "sale", "id": s.id, "date": s.date,
            "amount": round(s.total_amount, 2),
            "party_name": party.name if party else "",
        })

    purchases = db.query(Purchase).filter(Purchase.is_deleted == False).order_by(Purchase.date.desc()).limit(limit).all()
    for p in purchases:
        party = db.query(Party).filter(Party.id == p.party_id).first()
        result.append({
            "type": "purchase", "id": p.id, "date": p.date,
            "amount": round(p.total_cost, 2),
            "party_name": party.name if party else "",
        })

    payments_in = db.query(PaymentIn).filter(PaymentIn.is_deleted == False).order_by(PaymentIn.date.desc()).limit(limit).all()
    for p in payments_in:
        party = db.query(Party).filter(Party.id == p.party_id).first()
        result.append({
            "type": "payment_in", "id": p.id, "date": p.date,
            "amount": round(p.amount, 2),
            "party_name": party.name if party else "",
        })

    payments_out = db.query(PaymentOut).filter(PaymentOut.is_deleted == False).order_by(PaymentOut.date.desc()).limit(limit).all()
    for p in payments_out:
        party = db.query(Party).filter(Party.id == p.party_id).first()
        result.append({
            "type": "payment_out", "id": p.id, "date": p.date,
            "amount": round(p.amount, 2),
            "party_name": party.name if party else "",
        })

    expenses = db.query(Expense).filter(Expense.is_deleted == False).order_by(Expense.date.desc()).limit(limit).all()
    for e in expenses:
        result.append({
            "type": "expense", "id": e.id, "date": e.date,
            "amount": round(e.amount, 2),
            "party_name": "",
        })

    # Sort merged list by date descending and take top 'limit'
    result.sort(key=lambda x: x["date"], reverse=True)
    return result[:limit]