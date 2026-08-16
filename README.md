# Accounts Tracker — Small Business Accounting System

A personalized accounts tracking system for small retail/manufacturing businesses in Bangladesh.

**Stack:** FastAPI + SQLite + Jinja2/HTMX + Pico CSS

## Features
- Inventory tracking (finished goods + raw materials)
- Sales, purchases, payments, expenses
- Accounts Receivable / Accounts Payable management
- Profit & Loss reports, inventory valuation, AR/AP aging
- Single-owner + staff accounts with invite codes
- Mobile-first responsive UI
- CSV export
- Soft delete with undo

## Quick Start

1. Create virtual environment:
```bash
python -m venv venv
source venv/Scripts/activate  # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run database migrations:
```bash
alembic upgrade head
```

4. Start the server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or double-click `start.bat`.

5. Open http://localhost:8000 and register as the owner.

## Environment Variables
Copy `.env.example` to `.env` and configure:
- `SECRET_KEY` — random string for session signing
- `DATABASE_URL` — path to SQLite file (default: `data/accounts.db`)