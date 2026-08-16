"""
Database engine and session configuration.
- Uses PostgreSQL for Vercel deployment.
- Falls back to SQLite for local development if DATABASE_URL is a file path.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

DATABASE_URL = settings.DATABASE_URL

# Detect if URL is PostgreSQL (starts with postgresql://) or SQLite (file path)
if DATABASE_URL.startswith("postgresql://"):
    # PostgreSQL — for Vercel/Neon
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
else:
    # SQLite fallback — for local development
    engine = create_engine(
        f"sqlite:///{DATABASE_URL}",
        connect_args={"check_same_thread": False},
        echo=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()