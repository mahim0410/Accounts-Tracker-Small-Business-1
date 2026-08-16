"""
CSV export service.
"""
import csv
import io
from datetime import date

from sqlalchemy.orm import Session

from app.models import Expense, Item, Party, PaymentIn, PaymentOut, Purchase, Sale


def _make_csv(headers: list[str], rows: list[list]) -> str:
    output = io.StringIO()
    output.write("\ufeff")  # BOM for Excel compatibility
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def export_parties_csv(db: Session) -> str:
    parties = db.query(Party).filter(Party.is_deleted == False).all()
    headers = ["ID", "Name", "Type", "Contact", "AR Balance", "AP Balance"]
    rows = [
        [p.id, p.name, p.type.value, p.contact or "", p.ar_balance, p.ap_balance]
        for p in parties
    ]
    return _make_csv(headers, rows)


def export_items_csv(db: Session) -> str:
    items = db.query(Item).filter(Item.is_deleted == False).all()
    headers = ["ID", "Name", "SKU", "Type", "Unit", "Qty On Hand",
               "Avg Cost", "Sale Price", "Value", "Reorder Level"]
    rows = [
        [i.id, i.name, i.sku or "", i.type.value, i.unit,
         i.quantity_on_hand, i.average_cost, i.sale_price,
         i.value, i.reorder_level]
        for i in items
    ]
    return _make_csv(headers, rows)


def export_sales_csv(db: Session) -> str:
    sales = db.query(Sale).filter(Sale.is_deleted == False).order_by(Sale.date.desc()).all()
    headers = ["ID", "Date", "Customer", "Item", "Unit Price", "Quantity",
               "Total", "Cash Received", "AR Remaining", "Notes"]
    rows = [
        [
            s.id, s.date, s.party.name, s.item.name,
            s.unit_price, s.quantity, s.total_amount, s.cash_received,
            round(s.total_amount - s.cash_received, 2),
            s.notes or "",
        ]
        for s in sales
    ]
    return _make_csv(headers, rows)


def export_purchases_csv(db: Session) -> str:
    purchases = db.query(Purchase).filter(Purchase.is_deleted == False).order_by(Purchase.date.desc()).all()
    headers = ["ID", "Date", "Supplier", "Payment Method", "Cash Paid",
               "Total Cost", "Notes"]
    rows = [
        [
            p.id, p.date, p.party.name, p.payment_method.value,
            p.cash_paid, p.total_cost, p.notes or "",
        ]
        for p in purchases
    ]
    return _make_csv(headers, rows)


def export_expenses_csv(db: Session) -> str:
    expenses = db.query(Expense).filter(Expense.is_deleted == False).order_by(Expense.date.desc()).all()
    headers = ["ID", "Date", "Category", "Amount", "Description", "Party"]
    rows = [
        [e.id, e.date, e.category, e.amount, e.description or "",
         e.party.name if e.party else ""]
        for e in expenses
    ]
    return _make_csv(headers, rows)


def export_payments_csv(db: Session) -> dict[str, str]:
    payments_in = db.query(PaymentIn).filter(PaymentIn.is_deleted == False).order_by(PaymentIn.date.desc()).all()
    payments_out = db.query(PaymentOut).filter(PaymentOut.is_deleted == False).order_by(PaymentOut.date.desc()).all()

    csv_in = _make_csv(
        ["ID", "Date", "Party", "Amount", "Receipt", "Method", "Notes"],
        [[p.id, p.date, p.party.name, p.amount, p.receipt_number,
          p.method.value, p.notes or ""] for p in payments_in]
    )
    csv_out = _make_csv(
        ["ID", "Date", "Party", "Amount", "Receipt", "Method", "Notes"],
        [[p.id, p.date, p.party.name, p.amount, p.receipt_number,
          p.method.value, p.notes or ""] for p in payments_out]
    )
    return {"payments_in": csv_in, "payments_out": csv_out}