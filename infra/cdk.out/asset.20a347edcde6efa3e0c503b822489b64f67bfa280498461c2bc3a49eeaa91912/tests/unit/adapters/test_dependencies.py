"""Tests for dependencies module."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.security import HTTPAuthorizationCredentials

from backend.src.adapters.primary.fastapi.routes.dependencies import (
    get_current_user,
    get_job_repository,
    get_job_queue,
    get_create_job_use_case,
    get_get_job_use_case,
    get_list_jobs_use_case,
)


class TestGetJobRepository:
    """Tests for get_job_repository() dependency."""

    def test_get_job_repository_returns_dynamodb_repository(self):
        """Test get_job_repository returns DynamoDB repository instance."""
        with patch(
            "backend.src.adapters.primary.fastapi.routes.dependencies.DynamoDBJobRepository"
        ) as mock:
            mock.return_value = MagicMock()
            result = get_job_repository()

            mock.assert_called_once()
            assert result is mock.return_value


class TestGetJobQueue:
    """Tests for get_job_queue() dependency."""

    def test_get_job_queue_returns_sqs_queue(self):
        """Test get_job_queue returns SQS queue instance."""
        with patch(
            "backend.src.adapters.primary.fastapi.routes.dependencies.SQSJobQueue"
        ) as mock:
            mock.return_value = MagicMock()
            result = get_job_queue()

            mock.assert_called_once()
            assert result is mock.return_value


class TestGetCreateJobUseCase:
    """Tests for get_create_job_use_case() dependency."""

    def test_get_create_job_use_case_creates_use_case(self):
        """Test get_create_job_use_case creates use case with dependencies."""
        with patch(
            "backend.src.adapters.primary.fastapi.routes.dependencies.CreateJobUseCase"
        ) as mock_use_case:
            mock_repo = MagicMock()
            mock_queue = MagicMock()
            mock_use_case.return_value = MagicMock()

            result = get_create_job_use_case(
                repository=mock_repo,
                queue=mock_queue,
            )

            mock_use_case.assert_called_once_with(
                job_repository=mock_repo,
                job_queue=mock_queue,
            )
            assert result is mock_use_case.return_value


class TestGetGetJobUseCase:
    """Tests for get_get_job_use_case() dependency."""

    def test_get_get_job_use_case_creates_use_case(self):
        """Test get_get_job_use_case creates use case with dependencies."""
        with patch(
            "backend.src.adapters.primary.fastapi.routes.dependencies.GetJobUseCase"
        ) as mock_use_case:
            mock_repo = MagicMock()
            mock_use_case.return_value = MagicMock()

            result = get_get_job_use_case(repository=mock_repo)

            mock_use_case.assert_called_once_with(job_repository=mock_repo)
            assert result is mock_use_case.return_value


class TestGetListJobsUseCase:
    """Tests for get_list_jobs_use_case() dependency."""

    def test_get_list_jobs_use_case_creates_use_case(self):
        """Test get_list_jobs_use_case creates use case with dependencies."""
        with patch(
            "backend.src.adapters.primary.fastapi.routes.dependencies.ListJobsUseCase"
        ) as mock_use_case:
            mock_repo = MagicMock()
            mock_use_case.return_value = MagicMock()

            result = get_list_jobs_use_case(repository=mock_repo)

            mock_use_case.assert_called_once_with(job_repository=mock_repo)
            assert result is mock_use_case.return_value


class TestGetCurrentUser:
    """Tests for get_current_user() dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, mock_settings):
        """Test get_current_user returns user_id for valid token."""
        with patch(
            "backend.src.adapters.primary.fastapi.routes.dependencies.get_jwt_service"
        ) as mock_jwt:
            mock_service = MagicMock()
            mock_service.verify_token.return_value = "user-123"
            mock_jwt.return_value = mock_service

            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="valid-token",
            )

            result = await get_current_user(
                credentials=credentials,
                jwt_service=mock_service,
            )

            assert result == "user-123"
            mock_service.verify_token.assert_called_once_with("valid-token")

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, mock_settings):
        """Test get_current_user raises UnauthorizedException for invalid token."""
        from backend.src.shared.exceptions import UnauthorizedException

        with patch(
            "backend.src.adapters.primary.fastapi.routes.dependencies.get_jwt_service"
        ) as mock_jwt:
            mock_service = MagicMock()
            mock_service.verify_token.side_effect = UnauthorizedException(
                "Invalid token"
            )
            mock_jwt.return_value = mock_service

            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="invalid-token",
            )

            with pytest.raises(UnauthorizedException):
                await get_current_user(
                    credentials=credentials,
                    jwt_service=mock_service,
                )


class TestExports:
    """Tests for module exports."""

    def test_all_exports_defined(self):
        """Test all expected exports are defined."""
        from backend.src.adapters.primary.fastapi.routes import dependencies

        expected_exports = [
            "get_current_user",
            "get_job_repository",
            "get_job_queue",
            "get_create_job_use_case",
            "get_get_job_use_case",
            "get_list_jobs_use_case",
            "get_jwt_service",
        ]

        for export in expected_exports:
            assert hasattr(dependencies, export)
