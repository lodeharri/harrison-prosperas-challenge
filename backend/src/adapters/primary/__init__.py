"""Primary (driving) adapters - FastAPI routes and application."""

from backend.src.adapters.primary.fastapi.routes import jobs
from backend.src.adapters.primary.fastapi.main import create_app

__all__ = ["jobs", "create_app"]
