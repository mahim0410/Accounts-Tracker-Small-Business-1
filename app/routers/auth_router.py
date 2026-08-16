"""
Authentication routes — login, register, logout.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import create_session_token, register_user, authenticate_user
from app.database import get_db
from app.main import render

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login_page(request: Request):
    if getattr(request.state, "user", None):
        return RedirectResponse(url="/dashboard", status_code=302)
    return render(request, "auth/login.html")


@router.post("/login")
async def login(
    request: Request,
    name: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, name, password)
    if not user:
        return render(
            request, "auth/login.html",
            error="Invalid name or password",
        )
    token = create_session_token(user.id)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="session",
        value=token,
        max_age=7 * 24 * 3600,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/register")
async def register_page(request: Request):
    if getattr(request.state, "user", None):
        return RedirectResponse(url="/dashboard", status_code=302)
    return render(request, "auth/register.html")


@router.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    password: str = Form(...),
    invite_code: str = Form(default=""),
    db: Session = Depends(get_db),
):
    success, message, user = register_user(
        db, name, password,
        invite_code=invite_code.strip() or None,
    )
    if not success:
        from app.database import SessionLocal
        db.close()
        return render(request, "auth/register.html", error=message)

    token = create_session_token(user.id)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="session",
        value=token,
        max_age=7 * 24 * 3600,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("session")
    return response