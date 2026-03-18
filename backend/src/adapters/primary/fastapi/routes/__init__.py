"""FastAPI routes module."""

from backend.src.adapters.primary.fastapi.routes.jobs import router, auth_router

__all__ = ["router", "auth_router"]
