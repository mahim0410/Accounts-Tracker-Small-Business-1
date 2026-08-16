"""
Parties CRUD routes.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import render
from app.middleware import require_auth
from app.models import Party, PartyType

router = APIRouter(prefix="/parties", tags=["parties"])


@router.get("")
@router.get("/")
async def list_parties(
    request: Request,
    search: str = "",
    type_filter: str = "",
    show_deleted: bool = False,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    query = db.query(Party)

    if not show_deleted:
        query = query.filter(Party.is_deleted == False)

    if type_filter in ("customer", "supplier", "both"):
        query = query.filter(Party.type == type_filter)

    if search:
        query = query.filter(Party.name.ilike(f"%{search}%"))

    parties = query.order_by(Party.name).all()

    return render(request, "parties/list.html",
        parties=parties,
        search=search,
        type_filter=type_filter,
        show_deleted=show_deleted,
    )


@router.post("/add")
async def add_party(
    request: Request,
    name: str = Form(...),
    type: str = Form("customer"),
    contact: str = Form(default=""),
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    party = Party(
        name=name.strip(),
        type=PartyType(type),
        contact=contact.strip(),
    )
    db.add(party)
    db.commit()
    return RedirectResponse(url="/parties", status_code=302)


@router.post("/edit/{party_id}")
async def edit_party(
    request: Request,
    party_id: int,
    name: str = Form(...),
    type: str = Form("customer"),
    contact: str = Form(default=""),
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    party = db.query(Party).filter(Party.id == party_id).first()
    if party:
        party.name = name.strip()
        party.type = PartyType(type)
        party.contact = contact.strip()
        db.commit()

    return RedirectResponse(url="/parties", status_code=302)


@router.post("/delete/{party_id}")
async def delete_party(
    request: Request,
    party_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    party = db.query(Party).filter(Party.id == party_id).first()
    if party:
        party.is_deleted = True
        db.commit()

    return RedirectResponse(url="/parties", status_code=302)


@router.post("/restore/{party_id}")
async def restore_party(
    request: Request,
    party_id: int,
    db: Session = Depends(get_db),
):
    require_auth(getattr(request.state, "user", None))

    party = db.query(Party).filter(Party.id == party_id).first()
    if party:
        party.is_deleted = False
        db.commit()

    return RedirectResponse(url="/parties", status_code=302)


@router.get("/search")
async def search_parties(
    request: Request,
    q: str = "",
    db: Session = Depends(get_db),
):
    """HTMX endpoint for inline party search."""
    require_auth(getattr(request.state, "user", None))

    query = db.query(Party).filter(Party.is_deleted == False)
    if q:
        query = query.filter(Party.name.ilike(f"%{q}%"))
    parties = query.order_by(Party.name).limit(10).all()

    return render(request, "components/_party_list.html", parties=parties)