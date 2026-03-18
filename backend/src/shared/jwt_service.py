"""JWT authentication service."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.src.config.settings import Settings, get_settings
from backend.src.shared.exceptions import UnauthorizedException
from backend.src.shared.schemas import TokenResponse

# HTTP Bearer scheme
security = HTTPBearer()


class JWTService:
    """Service for JWT token operations."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize JWT service."""
        self._settings = settings or get_settings()

    def create_access_token(self, user_id: str) -> TokenResponse:
        """
        Create a new JWT access token.

        Args:
            user_id: The user identifier to encode in the token

        Returns:
            TokenResponse with access token and metadata
        """
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.jwt_access_token_expire_minutes
        )

        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }

        token = jwt.encode(
            payload,
            self._settings.jwt_secret_key,
            algorithm=self._settings.jwt_algorithm,
        )

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=self._settings.jwt_access_token_expire_minutes * 60,
        )

    def verify_token(self, token: str) -> str:
        """
        Verify a JWT token and return the user_id.

        Args:
            token: The JWT token to verify

        Returns:
            The user_id from the verified token

        Raises:
            UnauthorizedException: If the token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret_key,
                algorithms=[self._settings.jwt_algorithm],
            )
            user_id = payload.get("sub")
            if user_id is None:
                raise UnauthorizedException("Invalid token: missing user_id")
            return user_id
        except JWTError as e:
            raise UnauthorizedException(f"Invalid token: {e}")


# Singleton instance
_jwt_service: JWTService | None = None


def get_jwt_service() -> JWTService:
    """Get the JWT service singleton."""
    global _jwt_service
    if _jwt_service is None:
        _jwt_service = JWTService()
    return _jwt_service


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
) -> str:
    """
    Dependency to get the current authenticated user from JWT token.

    Args:
        credentials: The HTTP Bearer credentials
        jwt_service: The JWT service

    Returns:
        The user_id from the verified token

    Raises:
        UnauthorizedException: If authentication fails
    """
    return jwt_service.verify_token(credentials.credentials)
