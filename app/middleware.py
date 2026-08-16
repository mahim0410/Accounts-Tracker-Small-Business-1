"""
Middleware for session management.
"""
from typing import Optional

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.auth import validate_session_token
from app.database import SessionLocal
from app.models import User


async def get_current_user(request: Request) -> Optional[User]:
    """Extract the authenticated user from the session cookie."""
    token = request.cookies.get("session")
    if not token:
        return None
    user_id = validate_session_token(token)
    if user_id is None:
        return None
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        return user
    finally:
        db.close()


def require_auth(user: Optional[User]) -> User:
    """Raise 401 if user is not authenticated."""
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_owner(user: Optional[User]) -> User:
    """Raise 403 if user is not the owner."""
    from fastapi import HTTPException
    user = require_auth(user)
    if user.role.value != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    return user