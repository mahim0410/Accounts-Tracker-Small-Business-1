@echo off
cd /d "%~dp0"
echo Installing dependencies...
call python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
echo Running migrations...
alembic upgrade head
echo Starting server...
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause