"""
Expenses CRUD routes.
"""
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import render
from app.middleware import require_auth
from app.models import Expense

# Standard expense categories
EXPENSE_CATEGORIES = [
    "salary", "rent", "electricity", "water", "gas", "internet",
    "transport", "packaging", "marketing", "maintenance",
    "meals", "stationery", "tax", "fees", "materials", "others",
]

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("")
@router.get("/")
async def list_expenses(
    request: Request,
    search: str = "",
    category: str = "",
    date_from: str = "",
    date_to: str = "",
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    query = db.query(Expense).filter(Expense.is_deleted == False)

    if category:
        query = query.filter(Expense.category == category)

    if search:
        query = query.filter(Expense.description.ilike(f"%{search}%"))

    if date_from:
        try:
            query = query.filter(Expense.date >= date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Expense.date <= date.fromisoformat(date_to))
        except ValueError:
            pass

    expenses = query.order_by(Expense.date.desc()).all()

    return render(request, "expenses/list.html",
        expenses=expenses,
        categories=EXPENSE_CATEGORIES,
        search=search,
        category=category,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/add")
async def add_expense(
    request: Request,
    category: str = Form(...),
    amount: float = Form(...),
    date_str: str = Form(...),
    description: str = Form(default=""),
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    try:
        exp_date = date.fromisoformat(date_str)
    except ValueError:
        exp_date = date.today()

    expense = Expense(
        category=category,
        amount=amount,
        date=exp_date,
        description=description.strip(),
    )
    db.add(expense)
    db.commit()

    return RedirectResponse(url="/expenses", status_code=302)


@router.post("/edit/{expense_id}")
async def edit_expense(
    request: Request,
    expense_id: int,
    category: str = Form(...),
    amount: float = Form(...),
    date_str: str = Form(...),
    description: str = Form(default=""),
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if expense:
        try:
            expense.date = date.fromisoformat(date_str)
        except ValueError:
            pass
        expense.category = category
        expense.amount = amount
        expense.description = description.strip()
        db.commit()

    return RedirectResponse(url="/expenses", status_code=302)


@router.post("/delete/{expense_id}")
async def delete_expense(
    request: Request,
    expense_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if expense:
        expense.is_deleted = True
        db.commit()

    return RedirectResponse(url="/expenses", status_code=302)


@router.post("/restore/{expense_id}")
async def restore_expense(
    request: Request,
    expense_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if expense:
        expense.is_deleted = False
        db.commit()

    return RedirectResponse(url="/expenses", status_code=302)