"""Tests for JWT authentication."""

import pytest
from datetime import datetime, timedelta, timezone

from backend.src.shared.jwt_service import JWTService
from backend.src.shared.exceptions import UnauthorizedException


class TestJWTService:
    """Tests for JWT service."""

    def test_create_access_token(self, mock_settings):
        """Test that JWT service can create access tokens."""
        service = JWTService(settings=mock_settings)
        token_response = service.create_access_token("user-123")

        assert token_response.access_token is not None
        assert token_response.token_type == "bearer"
        assert token_response.expires_in == 30 * 60  # 30 minutes

    def test_verify_valid_token(self, mock_settings):
        """Test that JWT service can verify valid tokens."""
        service = JWTService(settings=mock_settings)
        token_response = service.create_access_token("user-123")
        user_id = service.verify_token(token_response.access_token)

        assert user_id == "user-123"

    def test_verify_invalid_token_raises_exception(self, mock_settings):
        """Test that JWT service raises exception for invalid tokens."""
        service = JWTService(settings=mock_settings)

        with pytest.raises(UnauthorizedException):
            service.verify_token("invalid-token")

    def test_verify_expired_token_raises_exception(self, mock_settings):
        """Test that JWT service raises exception for expired tokens."""
        from jose import jwt

        # Create an expired token
        payload = {
            "sub": "user-123",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        expired_token = jwt.encode(
            payload,
            mock_settings.jwt_secret_key,
            algorithm=mock_settings.jwt_algorithm,
        )

        service = JWTService(settings=mock_settings)

        with pytest.raises(UnauthorizedException):
            service.verify_token(expired_token)

    def test_verify_token_without_user_id_raises_exception(self, mock_settings):
        """Test that JWT service raises exception for token without user_id."""
        from jose import jwt

        # Create a token without 'sub' claim
        payload = {
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(
            payload,
            mock_settings.jwt_secret_key,
            algorithm=mock_settings.jwt_algorithm,
        )

        service = JWTService(settings=mock_settings)

        with pytest.raises(UnauthorizedException):
            service.verify_token(token)
