"""
Reports routes — Profit & Loss, Inventory Valuation, AR/AP Aging.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import render
from app.middleware import require_auth
from app.services.accounting import compute_profit, compute_inventory_valuation, compute_aging
from app.services.export import (
    export_parties_csv, export_items_csv, export_sales_csv,
    export_purchases_csv, export_expenses_csv, export_payments_csv,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _parse_date_range(request: Request):
    """Get date_from and date_to from query params, with defaults."""
    date_from = request.query_params.get("date_from", "")
    date_to = request.query_params.get("date_to", "")
    if not date_to:
        date_to = date.today().isoformat()
    if not date_from:
        date_from = (date.today() - timedelta(days=30)).isoformat()
    return date_from, date_to


@router.get("/profit-loss")
async def profit_loss(request: Request, db: Session = Depends(get_db)):
    require_auth(getattr(request.state, "user", None))
    date_from, date_to = _parse_date_range(request)
    result = compute_profit(db, date.fromisoformat(date_from), date.fromisoformat(date_to))
    return render(request, "reports/profit_loss.html",
        **result, date_from=date_from, date_to=date_to)


@router.get("/profit-loss/csv")
async def profit_loss_csv(request: Request, db: Session = Depends(get_db)):
    require_auth(getattr(request.state, "user", None))
    date_from, date_to = _parse_date_range(request)
    result = compute_profit(db, date.fromisoformat(date_from), date.fromisoformat(date_to))
    csv = f"Date Range,{date_from} to {date_to}\n"
    csv += f"Total Income,{result['total_income']}\n"
    csv += f"Total Purchases,{result['total_purchases']}\n"
    csv += f"Total Operating Expenses,{result['total_operating_expenses']}\n"
    csv += f"Total Expenses,{result['total_expenses']}\n"
    csv += f"Profit,{result['profit']}\n"
    return PlainTextResponse(
        "\ufeff" + csv,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=profit_loss.csv"},
    )


@router.get("/inventory-valuation")
async def inventory_valuation(request: Request, db: Session = Depends(get_db)):
    require_auth(getattr(request.state, "user", None))
    items = compute_inventory_valuation(db)
    total_value = round(sum(i["value"] for i in items), 2)
    return render(request, "reports/inventory_valuation.html",
        items=items, total_value=total_value)


@router.get("/inventory-valuation/csv")
async def inventory_csv(request: Request, db: Session = Depends(get_db)):
    require_auth(getattr(request.state, "user", None))
    return PlainTextResponse(
        "\ufeff" + export_items_csv(db),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_valuation.csv"},
    )


@router.get("/aging")
async def aging(request: Request, db: Session = Depends(get_db)):
    require_auth(getattr(request.state, "user", None))
    data = compute_aging(db)
    return render(request, "reports/aging.html", **data)


@router.get("/aging/ar-csv")
async def aging_ar_csv(request: Request, db: Session = Depends(get_db)):
    require_auth(getattr(request.state, "user", None))
    data = compute_aging(db)
    import csv, io
    output = io.StringIO()
    output.write("\ufeff")
    w = csv.writer(output)
    w.writerow(["Party", "Balance", "Days", "Bucket"])
    for r in data["ar"]:
        w.writerow([r["party_name"], r["balance"], r["days"], r["bucket"]])
    return PlainTextResponse(output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ar_aging.csv"})


@router.get("/aging/ap-csv")
async def aging_ap_csv(request: Request, db: Session = Depends(get_db)):
    require_auth(getattr(request.state, "user", None))
    data = compute_aging(db)
    import csv, io
    output = io.StringIO()
    output.write("\ufeff")
    w = csv.writer(output)
    w.writerow(["Party", "Balance", "Days", "Bucket"])
    for r in data["ap"]:
        w.writerow([r["party_name"], r["balance"], r["days"], r["bucket"]])
    return PlainTextResponse(output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ap_aging.csv"})