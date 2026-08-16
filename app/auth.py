"""
Authentication — registration, login, logout, invite codes.
"""
from datetime import date, datetime, timedelta
from typing import Optional

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models import InviteCode, User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
serializer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="auth")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_session_token(user_id: int) -> str:
    """Create a signed session token valid for SESSION_MAX_AGE seconds."""
    expires = datetime.utcnow() + timedelta(seconds=settings.SESSION_MAX_AGE)
    return serializer.dumps({"user_id": user_id, "expires": expires.isoformat()})


def validate_session_token(token: str) -> Optional[int]:
    """Validate a session token and return user_id, or None if invalid/expired."""
    try:
        data = serializer.loads(token, max_age=settings.SESSION_MAX_AGE)
        return data["user_id"]
    except (BadSignature, SignatureExpired):
        return None


def register_user(db: Session, name: str, password: str, invite_code: Optional[str] = None) -> tuple[bool, str, Optional[User]]:
    """
    Register a new user.
    - First user becomes owner (no invite code needed).
    - Subsequent users need a valid invite code.
    Returns: (success, message, user_or_none)
    """
    # Check if name already taken
    existing = db.query(User).filter(User.name == name).first()
    if existing:
        return False, "Name already taken", None

    # Check if this is the first user
    user_count = db.query(User).count()
    if user_count == 0:
        # First user — becomes owner
        user = User(
            name=name,
            password_hash=hash_password(password),
            role=UserRole.owner,
        )
        db.add(user)
        db.commit()
        return True, "Owner account created", user

    # Subsequent users need invite code
    if not invite_code:
        return False, "Invite code required", None

    code = db.query(InviteCode).filter(
        InviteCode.code == invite_code.upper().strip(),
    ).first()
    if not code:
        return False, "Invalid invite code", None
    if code.expires_at and code.expires_at < date.today():
        return False, "Invite code has expired", None
    if code.max_uses > 0 and code.uses >= code.max_uses:
        return False, "Invite code has been used too many times", None

    # Valid code — create staff user
    user = User(
        name=name,
        password_hash=hash_password(password),
        role=UserRole.staff,
    )
    db.add(user)
    code.uses += 1
    db.commit()
    return True, "Staff account created", user


def authenticate_user(db: Session, name: str, password: str) -> Optional[User]:
    """Authenticate by name + password. Returns user or None."""
    user = db.query(User).filter(User.name == name, User.is_active == True).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None


def create_invite_code(db: Session, created_by: int, max_uses: int = 0, expires_days: Optional[int] = None) -> InviteCode:
    """Generate a new invite code."""
    import secrets
    import string
    code_str = "INV-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

    expires_at = None
    if expires_days:
        expires_at = date.today() + timedelta(days=expires_days)

    code = InviteCode(
        code=code_str,
        max_uses=max_uses,
        expires_at=expires_at,
        created_by=created_by,
    )
    db.add(code)
    db.commit()
    db.refresh(code)
    return code


def change_password(db: Session, user_id: int, old_password: str, new_password: str) -> tuple[bool, str]:
    """Change a user's password."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False, "User not found"
    if not verify_password(old_password, user.password_hash):
        return False, "Current password is incorrect"
    user.password_hash = hash_password(new_password)
    db.commit()
    return True, "Password changed"