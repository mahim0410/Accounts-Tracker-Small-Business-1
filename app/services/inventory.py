"""
Inventory management service.
"""
from sqlalchemy.orm import Session

from app.models import Item, StockAdjustment


def adjust_stock(
    db: Session, item_id: int, quantity: float, reason: str = ""
) -> StockAdjustment:
    """Create a stock adjustment. Negative quantity = deduction."""
    adj = StockAdjustment(item_id=item_id, quantity=quantity, reason=reason)
    db.add(adj)
    db.flush()

    # Apply to item
    from app.services.accounting import apply_stock_adjustment
    apply_stock_adjustment(db, adj)

    return adj


def get_low_stock_items(db: Session) -> list[Item]:
    """Return items where quantity is below reorder level."""
    return (
        db.query(Item)
        .filter(
            Item.is_deleted == False,
            Item.reorder_level > 0,
            Item.quantity_on_hand < Item.reorder_level,
        )
        .all()
    )


def get_item_history(db: Session, item_id: int) -> dict:
    """Get purchase and sale history for an item."""
    from app.models import PurchaseLine, Sale

    purchases = (
        db.query(PurchaseLine)
        .filter(PurchaseLine.item_id == item_id)
        .all()
    )
    sales = (
        db.query(Sale)
        .filter(Sale.item_id == item_id, Sale.is_deleted == False)
        .order_by(Sale.date.desc())
        .all()
    )
    adjustments = (
        db.query(StockAdjustment)
        .filter(StockAdjustment.item_id == item_id)
        .order_by(StockAdjustment.created_at.desc())
        .all()
    )

    return {
        "purchases": [
            {
                "id": pl.id,
                "date": pl.purchase.date,
                "supplier": pl.purchase.party.name,
                "quantity": pl.quantity,
                "unit_cost": pl.unit_cost,
                "total": round(pl.quantity * pl.unit_cost, 2),
            }
            for pl in purchases
            if not pl.purchase.is_deleted
        ],
        "sales": [
            {
                "id": s.id,
                "date": s.date,
                "customer": s.party.name,
                "quantity": s.quantity,
                "unit_price": s.unit_price,
                "total": s.total_amount,
            }
            for s in sales
        ],
        "adjustments": [
            {
                "id": a.id,
                "date": a.date,
                "quantity": a.quantity,
                "reason": a.reason,
            }
            for a in adjustments
        ],
    }