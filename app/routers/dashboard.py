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
    """Get the most recent transactions across all types."""
    from sqlalchemy import union, literal_column

    sales_q = db.query(
        literal_column("'sale'").label("type"),
        Sale.id,
        Sale.date,
        Sale.total_amount.label("amount"),
        Sale.party_id,
        Sale.is_deleted,
    ).filter(Sale.is_deleted == False)

    purchases_q = db.query(
        literal_column("'purchase'").label("type"),
        Purchase.id,
        Purchase.date,
        Purchase.total_cost.label("amount"),
        Purchase.party_id,
        Purchase.is_deleted,
    ).filter(Purchase.is_deleted == False)

    payments_in_q = db.query(
        literal_column("'payment_in'").label("type"),
        PaymentIn.id,
        PaymentIn.date,
        PaymentIn.amount,
        PaymentIn.party_id,
        PaymentIn.is_deleted,
    ).filter(PaymentIn.is_deleted == False)

    payments_out_q = db.query(
        literal_column("'payment_out'").label("type"),
        PaymentOut.id,
        PaymentOut.date,
        PaymentOut.amount,
        PaymentOut.party_id,
        PaymentOut.is_deleted,
    ).filter(PaymentOut.is_deleted == False)

    expenses_q = db.query(
        literal_column("'expense'").label("type"),
        Expense.id,
        Expense.date,
        Expense.amount,
        literal_column("NULL").label("party_id"),
        Expense.is_deleted,
    ).filter(Expense.is_deleted == False)

    union_q = sales_q.union_all(
        purchases_q, payments_in_q, payments_out_q, expenses_q
    ).order_by(literal_column("date").desc()).limit(limit)

    rows = db.execute(union_q).fetchall()

    result = []
    for row in rows:
        party_name = ""
        if row.party_id:
            party = db.query(Party).filter(Party.id == row.party_id).first()
            party_name = party.name if party else ""
        result.append({
            "type": row.type,
            "id": row.id,
            "date": row.date,
            "amount": round(float(row.amount), 2),
            "party_name": party_name,
        })
    return result