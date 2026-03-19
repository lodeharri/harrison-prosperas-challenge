"""FastAPI routes module."""

from backend.src.adapters.primary.fastapi.routes.jobs import router, auth_router
from backend.src.adapters.primary.fastapi.routes.notify import router as notify_router
from backend.src.adapters.primary.fastapi.routes.ws_routes import router as ws_router

__all__ = ["router", "auth_router", "notify_router", "ws_router"]
