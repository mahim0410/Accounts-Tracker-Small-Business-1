"""
Application configuration loaded from environment variables.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    # Support Vercel Postgres env vars (POSTGRES_URL) and custom DATABASE_URL
    DATABASE_URL: str = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or "data/accounts.db"
    )
    # Resolve relative DB path to absolute under BASE_DIR (for local SQLite)
    if not DATABASE_URL.startswith("postgresql://") and not os.path.isabs(DATABASE_URL):
        DATABASE_URL = str(BASE_DIR / DATABASE_URL)
    SESSION_MAX_AGE: int = 7 * 24 * 3600  # 7 days


settings = Settings()