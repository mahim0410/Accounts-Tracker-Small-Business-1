"""
Core accounting logic — AR/AP/income/expense with reversal support.
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    Expense,
    Item,
    Party,
    PartyType,
    PaymentIn,
    PaymentOut,
    PaymentMethod,
    Purchase,
    PurchaseLine,
    Sale,
    StockAdjustment,
)


def apply_sale(db: Session, sale: Sale) -> None:
    """Record income + update AR + track units sold."""
    # Update item sold count
    item = db.query(Item).filter(Item.id == sale.item_id).first()
    if item:
        item.total_units_sold = (item.total_units_sold or 0) + sale.quantity
    db.flush()


def reverse_sale(db: Session, sale: Sale) -> None:
    """Reverse a sale's effects (soft delete)."""
    item = db.query(Item).filter(Item.id == sale.item_id).first()
    if item:
        item.total_units_sold = max(0, (item.total_units_sold or 0) - sale.quantity)
    db.flush()


def apply_purchase(db: Session, purchase: Purchase) -> None:
    """Update inventory (qty + avg cost), record expense, update AP."""
    for line in purchase.lines:
        item = db.query(Item).filter(Item.id == line.item_id).first()
        if not item:
            continue
        old_qty = item.quantity_on_hand or 0
        old_avg = item.average_cost or 0
        new_qty = old_qty + line.quantity
        # Weighted average cost
        if new_qty > 0:
            item.average_cost = round(
                ((old_avg * old_qty) + (line.unit_cost * line.quantity)) / new_qty, 2
            )
        item.quantity_on_hand = new_qty
        item.total_units_purchased = (item.total_units_purchased or 0) + line.quantity
    db.flush()


def reverse_purchase(db: Session, purchase: Purchase) -> None:
    """Reverse a purchase's effects."""
    for line in purchase.lines:
        item = db.query(Item).filter(Item.id == line.item_id).first()
        if not item:
            continue
        old_qty = item.quantity_on_hand or 0
        old_purchased = item.total_units_purchased or 0
        item.quantity_on_hand = max(0, old_qty - line.quantity)
        item.total_units_purchased = max(0, old_purchased - line.quantity)
        # Note: average_cost is NOT reversed to its previous value — too complex
        # for soft-delete. The user can re-enter the purchase if needed.
    db.flush()


def apply_stock_adjustment(db: Session, adj: StockAdjustment) -> None:
    """Deduct (or add) stock quantity."""
    item = db.query(Item).filter(Item.id == adj.item_id).first()
    if item:
        item.quantity_on_hand = max(0, (item.quantity_on_hand or 0) + adj.quantity)
    db.flush()


def get_next_receipt_number(db: Session, party_id: int, prefix: str) -> str:
    """Generate the next receipt number for a party: {prefix}-{party_id}-{seq}."""
    if prefix == "INV":
        model = PaymentIn
    else:
        model = PaymentOut
    count = (
        db.query(model)
        .filter(model.party_id == party_id, model.is_deleted == False)
        .count()
    )
    return f"{prefix}-{party_id}-{count + 1}"


def compute_profit(db: Session, start_date, end_date) -> dict:
    """Compute profit & loss for a date range."""
    from sqlalchemy import func as sa_func

    # Total income from sales (accrual)
    total_income = (
        db.query(sa_func.coalesce(sa_func.sum(Sale.total_amount), 0))
        .filter(Sale.date >= start_date, Sale.date <= end_date, Sale.is_deleted == False)
        .scalar()
    )

    # Total purchase costs
    total_purchases = (
        db.query(sa_func.coalesce(sa_func.sum(Purchase.total_cost), 0))
        .filter(Purchase.date >= start_date, Purchase.date <= end_date, Purchase.is_deleted == False)
        .scalar()
    )

    # Total operating expenses
    total_expenses = (
        db.query(sa_func.coalesce(sa_func.sum(Expense.amount), 0))
        .filter(Expense.date >= start_date, Expense.date <= end_date, Expense.is_deleted == False)
        .scalar()
    )

    total_operating = float(total_expenses or 0)
    total_income_val = float(total_income or 0)
    total_purchases_val = float(total_purchases or 0)
    total_expense = total_purchases_val + total_operating
    profit = total_income_val - total_expense

    return {
        "total_income": round(total_income_val, 2),
        "total_purchases": round(total_purchases_val, 2),
        "total_operating_expenses": round(total_operating, 2),
        "total_expenses": round(total_expense, 2),
        "profit": round(profit, 2),
    }


def compute_inventory_valuation(db: Session) -> list:
    """Return all items with their current valuation."""
    items = db.query(Item).filter(Item.is_deleted == False).all()
    result = []
    for item in items:
        result.append({
            "id": item.id,
            "name": item.name,
            "sku": item.sku or "",
            "type": item.type.value,
            "unit": item.unit,
            "quantity_on_hand": item.quantity_on_hand,
            "average_cost": item.average_cost,
            "value": item.value,
            "total_units_purchased": item.total_units_purchased,
            "total_units_sold": item.total_units_sold,
        })
    return result


def compute_aging(db: Session) -> dict:
    """Compute AR/AP aging per party."""
    from datetime import date, timedelta

    today = date.today()
    parties = db.query(Party).filter(Party.is_deleted == False).all()

    ar_data = []
    ap_data = []
    total_ar = 0
    total_ap = 0

    for party in parties:
        # Skip parties that are only suppliers for AR, only customers for AP
        if party.type in (PartyType.customer, PartyType.both):
            ar = party.ar_balance
            if ar > 0:
                # Find oldest unpaid sale
                oldest_sale = (
                    db.query(Sale)
                    .filter(
                        Sale.party_id == party.id,
                        Sale.is_deleted == False,
                    )
                    .order_by(Sale.date.asc())
                    .first()
                )
                days = (today - oldest_sale.date).days if oldest_sale else 0
                bucket = _aging_bucket(days)
                ar_data.append({
                    "party_id": party.id,
                    "party_name": party.name,
                    "balance": ar,
                    "days": days,
                    "bucket": bucket,
                })
                total_ar += ar

        if party.type in (PartyType.supplier, PartyType.both):
            ap = party.ap_balance
            if ap > 0:
                oldest_purchase = (
                    db.query(Purchase)
                    .filter(
                        Purchase.party_id == party.id,
                        Purchase.is_deleted == False,
                        Purchase.payment_method == PaymentMethod.credit,
                    )
                    .order_by(Purchase.date.asc())
                    .first()
                )
                days = (today - oldest_purchase.date).days if oldest_purchase else 0
                bucket = _aging_bucket(days)
                ap_data.append({
                    "party_id": party.id,
                    "party_name": party.name,
                    "balance": ap,
                    "days": days,
                    "bucket": bucket,
                })
                total_ap += ap

    return {
        "ar": ar_data,
        "ap": ap_data,
        "total_ar": round(total_ar, 2),
        "total_ap": round(total_ap, 2),
    }


def _aging_bucket(days: int) -> str:
    if days <= 30:
        return "0-30 days"
    elif days <= 60:
        return "31-60 days"
    elif days <= 90:
        return "61-90 days"
    else:
        return "90+ days"