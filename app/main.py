"""
FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings as app_settings
from app.database import Base, engine, SessionLocal
from app.middleware import get_current_user

# ── Template Environment ───────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR.parent / "static"

jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render(
    request: Request, template_name: str, **context
) -> HTMLResponse:
    """Render a Jinja2 template with common context variables."""
    tpl = jinja_env.get_template(template_name)
    content = tpl.render(
        request=request,
        user=getattr(request.state, "user", None),
        **context,
    )
    return HTMLResponse(content=content)


# ── Lifespan ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if they don't exist
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"WARNING: Could not create tables: {e}")
        print("The app will still serve requests. Make sure DATABASE_URL is set correctly.")
    yield
    # Shutdown: nothing to clean up


# ── App ────────────────────────────────────────────────────────────

app = FastAPI(title="Accounts Tracker", lifespan=lifespan)


# ── Static Files ───────────────────────────────────────────────────

if STATIC_DIR.exists():
    try:
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    except Exception:
        pass  # Vercel serverless doesn't support StaticFiles mount


# ── Middleware: Load user into request.state ────────────────────────

@app.middleware("http")
async def user_middleware(request: Request, call_next):
    request.state.user = await get_current_user(request)
    response: Response = await call_next(request)
    return response


# ── 401 → Redirect to Login ────────────────────────────────────────

@app.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/auth/login", status_code=302)
    return Response(content=str(exc.detail), status_code=exc.status_code)


# ── Import & Include Routers ───────────────────────────────────────

from app.routers import auth_router
from app.routers import dashboard
from app.routers import parties
from app.routers import items
from app.routers import purchases
from app.routers import sales
from app.routers import payments
from app.routers import expenses
from app.routers import reports
from app.routers import settings

app.include_router(auth_router.router)
app.include_router(dashboard.router)
app.include_router(parties.router)
app.include_router(items.router)
app.include_router(purchases.router)
app.include_router(sales.router)
app.include_router(payments.router)
app.include_router(expenses.router)
app.include_router(reports.router)
app.include_router(settings.router)


# ── Health Check ──────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "Accounts Tracker"}


# ── Root Redirect ──────────────────────────────────────────────────

@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")