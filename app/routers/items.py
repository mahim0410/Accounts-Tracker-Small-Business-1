"""
Inventory (Items) CRUD routes.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import render
from app.middleware import require_auth
from app.models import Item, ItemType
from app.services.inventory import adjust_stock, get_item_history, get_low_stock_items

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("")
@router.get("/")
async def list_items(
    request: Request,
    search: str = "",
    type_filter: str = "",
    low_stock_only: bool = False,
    show_deleted: bool = False,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    query = db.query(Item)

    if not show_deleted:
        query = query.filter(Item.is_deleted == False)

    if type_filter in ("finished", "raw_material"):
        query = query.filter(Item.type == type_filter)

    if search:
        query = query.filter(Item.name.ilike(f"%{search}%"))

    items = query.order_by(Item.name).all()

    if low_stock_only:
        items = [i for i in items if i.is_low_stock]

    return render(request, "inventory/list.html",
        items=items,
        search=search,
        type_filter=type_filter,
        low_stock_only=low_stock_only,
        show_deleted=show_deleted,
    )


@router.post("/add")
async def add_item(
    request: Request,
    name: str = Form(...),
    sku: str = Form(default=""),
    type: str = Form("finished"),
    unit: str = Form("pcs"),
    sale_price: float = Form(0.0),
    reorder_level: float = Form(0.0),
    reorder_quantity: float = Form(0.0),
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    item = Item(
        name=name.strip(),
        sku=sku.strip() or None,
        type=ItemType(type),
        unit=unit.strip(),
        sale_price=sale_price,
        reorder_level=reorder_level,
        reorder_quantity=reorder_quantity,
    )
    db.add(item)
    db.commit()
    return RedirectResponse(url="/inventory", status_code=302)


@router.post("/edit/{item_id}")
async def edit_item(
    request: Request,
    item_id: int,
    name: str = Form(...),
    sku: str = Form(default=""),
    type: str = Form("finished"),
    unit: str = Form("pcs"),
    sale_price: float = Form(0.0),
    reorder_level: float = Form(0.0),
    reorder_quantity: float = Form(0.0),
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    item = db.query(Item).filter(Item.id == item_id).first()
    if item:
        item.name = name.strip()
        item.sku = sku.strip() or None
        item.type = ItemType(type)
        item.unit = unit.strip()
        item.sale_price = sale_price
        item.reorder_level = reorder_level
        item.reorder_quantity = reorder_quantity
        db.commit()

    return RedirectResponse(url="/inventory", status_code=302)


@router.post("/adjust-stock/{item_id}")
async def adjust_stock_route(
    request: Request,
    item_id: int,
    quantity: float = Form(...),
    reason: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Record a stock-out adjustment (negative quantity = reduction)."""
    require_auth(getattr(request.state, "user", None))

    if quantity >= 0:
        return RedirectResponse(url="/inventory", status_code=302)

    adjust_stock(db, item_id, quantity, reason)
    return RedirectResponse(url="/inventory", status_code=302)


@router.get("/detail/{item_id}")
async def item_detail(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        return RedirectResponse(url="/inventory", status_code=302)

    history = get_item_history(db, item_id)

    return render(request, "inventory/detail.html",
        item=item,
        history=history,
    )


@router.post("/delete/{item_id}")
async def delete_item(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    item = db.query(Item).filter(Item.id == item_id).first()
    if item:
        item.is_deleted = True
        db.commit()

    return RedirectResponse(url="/inventory", status_code=302)


@router.post("/restore/{item_id}")
async def restore_item(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    item = db.query(Item).filter(Item.id == item_id).first()
    if item:
        item.is_deleted = False
        db.commit()

    return RedirectResponse(url="/inventory", status_code=302)