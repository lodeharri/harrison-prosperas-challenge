"""Tests for main FastAPI application."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI

from backend.src.adapters.primary.fastapi.main import (
    create_app,
    register_exception_handlers,
    health_check,
)


class TestCreateApp:
    """Tests for create_app() function."""

    def test_create_app_returns_fastapi_instance(self, mock_settings):
        """Test create_app returns a FastAPI instance."""
        with patch(
            "backend.src.adapters.primary.fastapi.main.get_settings"
        ) as mock_settings_fn:
            mock_settings_fn.return_value = mock_settings

            app = create_app()

            assert isinstance(app, FastAPI)
            assert app.title == mock_settings.app_name

    def test_create_app_includes_routers(self, mock_settings):
        """Test create_app includes all required routers."""
        with patch(
            "backend.src.adapters.primary.fastapi.main.get_settings"
        ) as mock_settings_fn:
            mock_settings_fn.return_value = mock_settings

            app = create_app()

            # Check routers are included
            route_paths = [route.path for route in app.routes]

            # Jobs routes
            assert any("/jobs" in path for path in route_paths)
            # Auth routes
            assert any("/auth" in path for path in route_paths)
            # WebSocket routes
            assert any("/ws/jobs" in path for path in route_paths)
            # Internal routes
            assert any("/internal" in path for path in route_paths)
            # Health check
            assert any("/health" in path for path in route_paths)


class TestRegisterExceptionHandlers:
    """Tests for register_exception_handlers() function."""

    def test_register_exception_handlers_adds_handlers(self, mock_settings):
        """Test register_exception_handlers adds exception handlers to app."""
        app = FastAPI()

        # This should not raise
        register_exception_handlers(app)

        # Verify handlers are registered
        assert len(app.exception_handlers) > 0


class TestExceptionHandlers:
    """Tests for individual exception handlers."""

    def test_conflict_exception_returns_409(self, mock_settings):
        """Test ConflictException has correct status code."""
        from backend.src.shared.exceptions import ConflictException

        exc = ConflictException(
            resource="Job",
            message="Resource conflict",
        )

        # Verify exception has correct status code
        assert exc.status_code == 409

    def test_app_exception_can_be_created(self, mock_settings):
        """Test AppException can be created with status code."""
        from backend.src.shared.exceptions import AppException

        exc = AppException(
            status_code=400,
            message="Test error",
            error_code="TEST_ERROR",
        )

        assert exc.status_code == 400


class TestHealthCheck:
    """Tests for health_check() endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self, mock_settings):
        """Test health_check returns healthy when all dependencies are up."""
        with patch(
            "backend.src.adapters.primary.fastapi.main.get_settings"
        ) as mock_settings_fn:
            with patch(
                "backend.src.adapters.primary.fastapi.main.get_job_repository"
            ) as mock_repo_fn:
                with patch(
                    "backend.src.adapters.primary.fastapi.main.get_job_queue"
                ) as mock_queue_fn:
                    mock_settings_fn.return_value = mock_settings

                    mock_repo = MagicMock()
                    mock_repo.health_check = AsyncMock(return_value=True)
                    mock_repo_fn.return_value = mock_repo

                    mock_queue = MagicMock()
                    mock_queue.health_check = MagicMock(return_value=True)
                    mock_queue_fn.return_value = mock_queue

                    result = await health_check()

                    assert result.status == "healthy"
                    assert result.dependencies["dynamodb"] == "ok"
                    assert result.dependencies["sqs"] == "ok"
                    assert result.version == mock_settings.app_version

    @pytest.mark.asyncio
    async def test_health_check_degraded_dynamodb(self, mock_settings):
        """Test health_check returns degraded when DynamoDB is down."""
        with patch(
            "backend.src.adapters.primary.fastapi.main.get_settings"
        ) as mock_settings_fn:
            with patch(
                "backend.src.adapters.primary.fastapi.main.get_job_repository"
            ) as mock_repo_fn:
                with patch(
                    "backend.src.adapters.primary.fastapi.main.get_job_queue"
                ) as mock_queue_fn:
                    mock_settings_fn.return_value = mock_settings

                    mock_repo = MagicMock()
                    mock_repo.health_check = AsyncMock(return_value=False)
                    mock_repo_fn.return_value = mock_repo

                    mock_queue = MagicMock()
                    mock_queue.health_check = MagicMock(return_value=True)
                    mock_queue_fn.return_value = mock_queue

                    result = await health_check()

                    assert result.status == "degraded"
                    assert result.dependencies["dynamodb"] == "error"
                    assert result.dependencies["sqs"] == "ok"

    @pytest.mark.asyncio
    async def test_health_check_degraded_sqs(self, mock_settings):
        """Test health_check returns degraded when SQS is down."""
        with patch(
            "backend.src.adapters.primary.fastapi.main.get_settings"
        ) as mock_settings_fn:
            with patch(
                "backend.src.adapters.primary.fastapi.main.get_job_repository"
            ) as mock_repo_fn:
                with patch(
                    "backend.src.adapters.primary.fastapi.main.get_job_queue"
                ) as mock_queue_fn:
                    mock_settings_fn.return_value = mock_settings

                    mock_repo = MagicMock()
                    mock_repo.health_check = AsyncMock(return_value=True)
                    mock_repo_fn.return_value = mock_repo

                    mock_queue = MagicMock()
                    mock_queue.health_check = MagicMock(return_value=False)
                    mock_queue_fn.return_value = mock_queue

                    result = await health_check()

                    assert result.status == "degraded"
                    assert result.dependencies["dynamodb"] == "ok"
                    assert result.dependencies["sqs"] == "error"

    @pytest.mark.asyncio
    async def test_health_check_exception_handling(self, mock_settings):
        """Test health_check handles exceptions gracefully."""
        with patch(
            "backend.src.adapters.primary.fastapi.main.get_settings"
        ) as mock_settings_fn:
            with patch(
                "backend.src.adapters.primary.fastapi.main.get_job_repository"
            ) as mock_repo_fn:
                with patch(
                    "backend.src.adapters.primary.fastapi.main.get_job_queue"
                ) as mock_queue_fn:
                    mock_settings_fn.return_value = mock_settings

                    mock_repo = MagicMock()
                    mock_repo.health_check = AsyncMock(
                        side_effect=Exception("DynamoDB error")
                    )
                    mock_repo_fn.return_value = mock_repo

                    mock_queue = MagicMock()
                    mock_queue.health_check = MagicMock(
                        side_effect=Exception("SQS error")
                    )
                    mock_queue_fn.return_value = mock_queue

                    result = await health_check()

                    assert result.status == "degraded"
                    assert result.dependencies["dynamodb"] == "error"
                    assert result.dependencies["sqs"] == "error"


class TestCorsConfiguration:
    """Tests for CORS configuration."""

    def test_cors_middleware_added(self, mock_settings):
        """Test CORS middleware is added to app."""
        with patch(
            "backend.src.adapters.primary.fastapi.main.get_settings"
        ) as mock_settings_fn:
            mock_settings_fn.return_value = mock_settings

            app = create_app()

            # Verify CORS middleware is present
            middleware = [m for m in app.user_middleware if "CORSMiddleware" in str(m)]
            assert len(middleware) > 0


class TestAppInstance:
    """Tests for default app instance."""

    def test_app_instance_created(self):
        """Test default app instance is created."""
        # Import the app instance
        from backend.src.adapters.primary.fastapi.main import app

        assert isinstance(app, FastAPI)
