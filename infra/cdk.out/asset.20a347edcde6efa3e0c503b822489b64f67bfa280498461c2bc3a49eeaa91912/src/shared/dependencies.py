"""Shared dependencies for dependency injection."""

from backend.src.shared.jwt_service import get_current_user

__all__ = ["get_current_user"]
