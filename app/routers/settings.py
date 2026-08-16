"""
Settings routes — profile, invite codes, user management, backup.
"""
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import change_password, create_invite_code
from app.config import settings as app_settings
from app.database import get_db
from app.main import render
from app.middleware import require_owner
from app.models import InviteCode, User, UserRole

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
@router.get("/")
async def settings_page(request: Request, db: Session = Depends(get_db)):
    user = require_owner(getattr(request.state, "user", None))

    invite_codes = db.query(InviteCode).order_by(InviteCode.created_at.desc()).all()
    staff_users = db.query(User).filter(User.role == UserRole.staff).all()

    return render(request, "settings/index.html",
        invite_codes=invite_codes,
        staff_users=staff_users,
    )


@router.post("/change-password")
async def change_password_route(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = require_owner(getattr(request.state, "user", None))
    success, message = change_password(db, user.id, old_password, new_password)
    return render(request, "settings/index.html",
        password_message=message,
        password_success=success,
        invite_codes=db.query(InviteCode).order_by(InviteCode.created_at.desc()).all(),
        staff_users=db.query(User).filter(User.role == UserRole.staff).all(),
    )


@router.post("/generate-invite")
async def generate_invite(
    request: Request,
    max_uses: int = Form(0),
    expires_days: int = Form(0),
    db: Session = Depends(get_db),
):
    user = require_owner(getattr(request.state, "user", None))
    create_invite_code(
        db,
        created_by=user.id,
        max_uses=max_uses,
        expires_days=expires_days if expires_days > 0 else None,
    )
    return RedirectResponse(url="/settings", status_code=302)


@router.post("/revoke-invite/{code_id}")
async def revoke_invite(
    request: Request,
    code_id: int,
    db: Session = Depends(get_db),
):
    require_owner(getattr(request.state, "user", None))
    code = db.query(InviteCode).filter(InviteCode.id == code_id).first()
    if code:
        db.delete(code)
        db.commit()
    return RedirectResponse(url="/settings", status_code=302)


@router.post("/remove-user/{user_id}")
async def remove_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
):
    user = require_owner(getattr(request.state, "user", None))
    if user_id == user.id:
        return RedirectResponse(url="/settings", status_code=302)

    target = db.query(User).filter(User.id == user_id).first()
    if target:
        target.is_active = False
        db.commit()

    return RedirectResponse(url="/settings", status_code=302)


@router.get("/download-backup")
async def download_backup(db: Session = Depends(get_db)):
    """Download the SQLite database file."""
    db_path = app_settings.DATABASE_URL
    if not Path(db_path).exists():
        return RedirectResponse(url="/settings", status_code=302)
    return FileResponse(
        db_path,
        media_type="application/octet-stream",
        filename="accounts_tracker_backup.db",
    )