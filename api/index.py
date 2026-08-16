"""Vercel serverless entry point for FastAPI app."""
from app.main import app

# Vercel expects a variable named 'app'
handler = app