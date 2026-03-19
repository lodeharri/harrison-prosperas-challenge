"""Tests for WebSocket manager service."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import json

from backend.src.services.websocket_manager import (
    WebSocketManager,
    ws_manager,
    get_ws_manager,
)


class TestWebSocketManagerConnect:
    """Tests for connect() method."""

    @pytest.mark.asyncio
    async def test_connect_adds_websocket(self):
        """Test connect adds websocket to user connections."""
        manager = WebSocketManager()
        mock_ws = MagicMock()

        await manager.connect(mock_ws, "user-123")

        assert "user-123" in manager._connections
        assert mock_ws in manager._connections["user-123"]

    @pytest.mark.asyncio
    async def test_connect_multiple_websockets_same_user(self):
        """Test connect handles multiple websockets for same user."""
        manager = WebSocketManager()
        mock_ws1 = MagicMock()
        mock_ws2 = MagicMock()

        await manager.connect(mock_ws1, "user-123")
        await manager.connect(mock_ws2, "user-123")

        assert len(manager._connections["user-123"]) == 2

    @pytest.mark.asyncio
    async def test_connect_multiple_users(self):
        """Test connect handles multiple users."""
        manager = WebSocketManager()
        mock_ws1 = MagicMock()
        mock_ws2 = MagicMock()

        await manager.connect(mock_ws1, "user-123")
        await manager.connect(mock_ws2, "user-456")

        assert "user-123" in manager._connections
        assert "user-456" in manager._connections
        assert mock_ws1 in manager._connections["user-123"]
        assert mock_ws2 in manager._connections["user-456"]


class TestWebSocketManagerDisconnect:
    """Tests for disconnect() method."""

    def test_disconnect_removes_websocket(self):
        """Test disconnect removes websocket from user connections."""
        manager = WebSocketManager()
        mock_ws = MagicMock()
        manager._connections["user-123"] = [mock_ws]

        manager.disconnect(mock_ws, "user-123")

        assert (
            "user-123" not in manager._connections
            or len(manager._connections["user-123"]) == 0
        )

    def test_disconnect_removes_specific_websocket(self):
        """Test disconnect removes specific websocket when multiple exist."""
        manager = WebSocketManager()
        mock_ws1 = MagicMock()
        mock_ws2 = MagicMock()
        manager._connections["user-123"] = [mock_ws1, mock_ws2]

        manager.disconnect(mock_ws1, "user-123")

        assert mock_ws1 not in manager._connections["user-123"]
        assert mock_ws2 in manager._connections["user-123"]

    def test_disconnect_nonexistent_user(self):
        """Test disconnect handles nonexistent user gracefully."""
        manager = WebSocketManager()
        mock_ws = MagicMock()

        # Should not raise
        manager.disconnect(mock_ws, "nonexistent-user")

    def test_disconnect_cleans_up_empty_user(self):
        """Test disconnect removes user entry when no connections left."""
        manager = WebSocketManager()
        mock_ws = MagicMock()
        manager._connections["user-123"] = [mock_ws]

        manager.disconnect(mock_ws, "user-123")

        assert "user-123" not in manager._connections


class TestWebSocketManagerNotifyJobUpdate:
    """Tests for notify_job_update() method."""

    @pytest.mark.asyncio
    async def test_notify_job_update_sends_to_connected_client(self):
        """Test notify_job_update sends message to connected client."""
        manager = WebSocketManager()
        mock_ws = MagicMock()
        mock_ws.send_text = AsyncMock()
        manager._connections["user-123"] = [mock_ws]

        job_data = {
            "job_id": "test-123",
            "status": "COMPLETED",
            "result_url": "https://example.com/results/test-123.pdf",
        }
        await manager.notify_job_update("user-123", job_data)

        mock_ws.send_text.assert_called_once()
        sent_message = json.loads(mock_ws.send_text.call_args[0][0])
        assert sent_message["type"] == "job_update"
        assert sent_message["data"]["job_id"] == "test-123"
        assert sent_message["data"]["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_notify_job_update_no_connections(self):
        """Test notify_job_update does nothing when no connections."""
        manager = WebSocketManager()

        job_data = {"job_id": "test-123", "status": "COMPLETED"}

        # Should not raise
        await manager.notify_job_update("nonexistent-user", job_data)

    @pytest.mark.asyncio
    async def test_notify_job_update_cleans_disconnected_sockets(self):
        """Test notify_job_update removes disconnected sockets."""
        manager = WebSocketManager()
        mock_ws1 = MagicMock()
        mock_ws1.send_text = AsyncMock()
        mock_ws2 = MagicMock()
        mock_ws2.send_text = AsyncMock(side_effect=Exception("Connection closed"))
        manager._connections["user-123"] = [mock_ws1, mock_ws2]

        job_data = {"job_id": "test-123", "status": "PROCESSING"}
        await manager.notify_job_update("user-123", job_data)

        # mock_ws1 should have been called
        mock_ws1.send_text.assert_called_once()

        # mock_ws2 should have been removed
        assert mock_ws2 not in manager._connections.get("user-123", [])

    @pytest.mark.asyncio
    async def test_notify_job_update_all_disconnected(self):
        """Test notify_job_update cleans up when all sockets disconnected."""
        manager = WebSocketManager()
        mock_ws = MagicMock()
        mock_ws.send_text = AsyncMock(side_effect=Exception("Connection closed"))
        manager._connections["user-123"] = [mock_ws]

        job_data = {"job_id": "test-123", "status": "COMPLETED"}
        await manager.notify_job_update("user-123", job_data)

        # User should be cleaned up
        assert "user-123" not in manager._connections


class TestWebSocketManagerGetConnectionCount:
    """Tests for get_connection_count() method."""

    def test_get_connection_count_returns_count(self):
        """Test get_connection_count returns correct count."""
        manager = WebSocketManager()
        mock_ws1 = MagicMock()
        mock_ws2 = MagicMock()
        manager._connections["user-123"] = [mock_ws1, mock_ws2]

        count = manager.get_connection_count("user-123")

        assert count == 2

    def test_get_connection_count_no_connections(self):
        """Test get_connection_count returns 0 when no connections."""
        manager = WebSocketManager()

        count = manager.get_connection_count("user-123")

        assert count == 0

    def test_get_connection_count_nonexistent_user(self):
        """Test get_connection_count returns 0 for nonexistent user."""
        manager = WebSocketManager()

        count = manager.get_connection_count("nonexistent-user")

        assert count == 0


class TestGlobalWebSocketManager:
    """Tests for global ws_manager instance and get_ws_manager()."""

    def test_get_ws_manager_returns_singleton(self):
        """Test get_ws_manager returns the same instance."""
        manager1 = get_ws_manager()
        manager2 = get_ws_manager()

        assert manager1 is manager2

    def test_global_ws_manager_is_instance(self):
        """Test global ws_manager is a WebSocketManager instance."""
        assert isinstance(ws_manager, WebSocketManager)

    def test_global_ws_manager_is_same_as_get_ws_manager(self):
        """Test global ws_manager is same as get_ws_manager()."""
        assert ws_manager is get_ws_manager()


class TestWebSocketManagerMultipleClients:
    """Tests for multiple clients notification scenarios."""

    @pytest.mark.asyncio
    async def test_notify_multiple_clients_same_user(self):
        """Test notify sends to all connected clients for same user."""
        manager = WebSocketManager()
        mock_ws1 = MagicMock()
        mock_ws1.send_text = AsyncMock()
        mock_ws2 = MagicMock()
        mock_ws2.send_text = AsyncMock()
        mock_ws3 = MagicMock()
        mock_ws3.send_text = AsyncMock()
        manager._connections["user-123"] = [mock_ws1, mock_ws2, mock_ws3]

        job_data = {"job_id": "test-123", "status": "PROCESSING"}
        await manager.notify_job_update("user-123", job_data)

        assert mock_ws1.send_text.call_count == 1
        assert mock_ws2.send_text.call_count == 1
        assert mock_ws3.send_text.call_count == 1

    @pytest.mark.asyncio
    async def test_notify_only_specific_user(self):
        """Test notify only sends to specific user's clients."""
        manager = WebSocketManager()
        mock_ws1 = MagicMock()
        mock_ws1.send_text = AsyncMock()
        mock_ws2 = MagicMock()
        mock_ws2.send_text = AsyncMock()
        manager._connections["user-123"] = [mock_ws1]
        manager._connections["user-456"] = [mock_ws2]

        job_data = {"job_id": "test-123", "status": "COMPLETED"}
        await manager.notify_job_update("user-123", job_data)

        mock_ws1.send_text.assert_called_once()
        mock_ws2.send_text.assert_not_called()
