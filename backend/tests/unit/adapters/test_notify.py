"""Tests for notify routes."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.src.adapters.primary.fastapi.routes.notify import NotifyRequest


class TestNotifyRoutes:
    """Tests for notify route handlers using direct function calls."""

    @pytest.mark.asyncio
    async def test_notify_job_update_calls_ws_manager(self):
        """Test notify_job_update calls WebSocket manager correctly."""
        from backend.src.adapters.primary.fastapi.routes.notify import notify_job_update

        with patch(
            "backend.src.adapters.primary.fastapi.routes.notify.get_ws_manager"
        ) as mock:
            mock_manager = MagicMock()
            mock_manager.notify_job_update = AsyncMock()
            mock.return_value = mock_manager

            request = NotifyRequest(
                user_id="user-123",
                job_id="job-456",
                status="COMPLETED",
                result_url="https://example.com/results/job-456.pdf",
                updated_at="2024-01-01T12:00:00Z",
                report_type="sales_report",
            )

            result = await notify_job_update(request)

            assert result == {"ok": True}
            mock_manager.notify_job_update.assert_called_once()

            call_kwargs = mock_manager.notify_job_update.call_args.kwargs
            assert call_kwargs["user_id"] == "user-123"
            assert call_kwargs["job_data"]["job_id"] == "job-456"
            assert call_kwargs["job_data"]["status"] == "COMPLETED"
            assert (
                call_kwargs["job_data"]["result_url"]
                == "https://example.com/results/job-456.pdf"
            )

    @pytest.mark.asyncio
    async def test_notify_job_update_minimal_data(self):
        """Test notify_job_update with minimal data."""
        from backend.src.adapters.primary.fastapi.routes.notify import notify_job_update

        with patch(
            "backend.src.adapters.primary.fastapi.routes.notify.get_ws_manager"
        ) as mock:
            mock_manager = MagicMock()
            mock_manager.notify_job_update = AsyncMock()
            mock.return_value = mock_manager

            request = NotifyRequest(
                user_id="user-123",
                job_id="job-456",
                status="PROCESSING",
                updated_at="2024-01-01T12:00:00Z",
            )

            result = await notify_job_update(request)

            assert result == {"ok": True}
            call_kwargs = mock_manager.notify_job_update.call_args.kwargs
            assert call_kwargs["job_data"]["result_url"] is None
            assert call_kwargs["job_data"]["report_type"] is None

    @pytest.mark.asyncio
    async def test_get_connection_count_returns_count(self):
        """Test get_connection_count returns correct count."""
        from backend.src.adapters.primary.fastapi.routes.notify import (
            get_connection_count,
        )

        with patch(
            "backend.src.adapters.primary.fastapi.routes.notify.get_ws_manager"
        ) as mock:
            mock_manager = MagicMock()
            mock_manager.get_connection_count = MagicMock(return_value=2)
            mock.return_value = mock_manager

            result = await get_connection_count("user-123")

            assert result == {"user_id": "user-123", "connections": 2}
            mock_manager.get_connection_count.assert_called_once_with("user-123")

    @pytest.mark.asyncio
    async def test_get_connection_count_zero(self):
        """Test get_connection_count returns 0 when no connections."""
        from backend.src.adapters.primary.fastapi.routes.notify import (
            get_connection_count,
        )

        with patch(
            "backend.src.adapters.primary.fastapi.routes.notify.get_ws_manager"
        ) as mock:
            mock_manager = MagicMock()
            mock_manager.get_connection_count = MagicMock(return_value=0)
            mock.return_value = mock_manager

            result = await get_connection_count("user-456")

            assert result == {"user_id": "user-456", "connections": 0}


class TestNotifyRequestSchema:
    """Tests for NotifyRequest schema."""

    def test_notify_request_valid(self):
        """Test NotifyRequest with all fields."""
        request = NotifyRequest(
            user_id="user-123",
            job_id="job-456",
            status="COMPLETED",
            result_url="https://example.com/results/job-456.pdf",
            updated_at="2024-01-01T12:00:00Z",
            report_type="sales_report",
        )

        assert request.user_id == "user-123"
        assert request.job_id == "job-456"
        assert request.status == "COMPLETED"
        assert request.result_url == "https://example.com/results/job-456.pdf"

    def test_notify_request_minimal(self):
        """Test NotifyRequest with only required fields."""
        request = NotifyRequest(
            user_id="user-123",
            job_id="job-456",
            status="PROCESSING",
            updated_at="2024-01-01T12:00:00Z",
        )

        assert request.user_id == "user-123"
        assert request.result_url is None
        assert request.report_type is None

    def test_notify_request_invalid(self):
        """Test NotifyRequest raises validation error for invalid data."""
        with pytest.raises(Exception):
            NotifyRequest(
                # Missing required fields
                user_id="user-123",
            )
