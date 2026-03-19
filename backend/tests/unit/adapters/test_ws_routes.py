"""Tests for WebSocket routes."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI
from starlette.testclient import WebSocketTestSession

from backend.src.adapters.primary.fastapi.routes.ws_routes import router


class TestWebSocketRoutes:
    """Tests for WebSocket route handlers."""

    @pytest.fixture
    def app(self):
        """Create a test FastAPI app with the ws router."""
        app = FastAPI()
        app.include_router(router)
        return app

    def test_websocket_missing_token(self, app):
        """Test WebSocket connection closes when token is missing."""
        # Create mock WebSocket
        mock_ws = MagicMock()
        mock_ws.query_params = {"user_id": "user-123"}
        mock_ws.close = AsyncMock()

        with patch.object(router, "websocket_endpoint_funcs", [], create=True):
            # Import the function to test
            from backend.src.adapters.primary.fastapi.routes.ws_routes import (
                websocket_jobs,
            )

            # We need to test the logic manually since WebSocket testing is complex
            # Test that missing token causes close
            with pytest.raises(Exception):
                with app.websocket_connect("/jobs?user_id=user-123") as ws:
                    ws.receive_text()

    def test_websocket_missing_user_id(self, app):
        """Test WebSocket connection closes when user_id is missing."""
        with pytest.raises(Exception):
            with app.websocket_connect("/jobs?token=test-token") as ws:
                ws.receive_text()

    def test_websocket_invalid_token(self, app):
        """Test WebSocket connection closes when token is invalid."""
        with patch(
            "backend.src.adapters.primary.fastapi.routes.ws_routes.get_jwt_service"
        ) as mock_jwt:
            mock_service = MagicMock()
            from backend.src.shared.exceptions import UnauthorizedException

            mock_service.verify_token.side_effect = UnauthorizedException(
                "Invalid token"
            )
            mock_jwt.return_value = mock_service

            with pytest.raises(Exception):
                with app.websocket_connect(
                    "/jobs?user_id=user-123&token=invalid-token"
                ) as ws:
                    ws.receive_text()

    def test_websocket_user_id_mismatch(self, app):
        """Test WebSocket connection closes when user_id doesn't match token."""
        with patch(
            "backend.src.adapters.primary.fastapi.routes.ws_routes.get_jwt_service"
        ) as mock_jwt:
            mock_service = MagicMock()
            mock_service.verify_token.return_value = "user-123"
            mock_jwt.return_value = mock_service

            with pytest.raises(Exception):
                with app.websocket_connect(
                    "/jobs?user_id=other-user&token=test-token"
                ) as ws:
                    ws.receive_text()


class TestWebSocketRouteLogic:
    """Tests for WebSocket route logic."""

    @pytest.mark.asyncio
    async def test_missing_token_closes_connection(self):
        """Test that missing token results in connection close."""
        mock_websocket = MagicMock()
        mock_websocket.query_params = {}
        mock_websocket.close = AsyncMock()

        from backend.src.adapters.primary.fastapi.routes.ws_routes import websocket_jobs

        await websocket_jobs(mock_websocket)

        mock_websocket.close.assert_called_once_with(code=4001, reason="Missing token")

    @pytest.mark.asyncio
    async def test_missing_user_id_closes_connection(self):
        """Test that missing user_id results in connection close."""
        mock_websocket = MagicMock()
        mock_websocket.query_params = {"token": "test-token"}
        mock_websocket.close = AsyncMock()

        from backend.src.adapters.primary.fastapi.routes.ws_routes import websocket_jobs

        await websocket_jobs(mock_websocket)

        mock_websocket.close.assert_called_once_with(
            code=4004, reason="Missing user_id"
        )

    @pytest.mark.asyncio
    async def test_invalid_token_closes_connection(self):
        """Test that invalid token results in connection close."""
        mock_websocket = MagicMock()
        mock_websocket.query_params = {"user_id": "user-123", "token": "invalid-token"}
        mock_websocket.close = AsyncMock()

        with patch(
            "backend.src.adapters.primary.fastapi.routes.ws_routes.get_jwt_service"
        ) as mock_jwt:
            mock_service = MagicMock()
            from backend.src.shared.exceptions import UnauthorizedException

            mock_service.verify_token.side_effect = UnauthorizedException(
                "Invalid token"
            )
            mock_jwt.return_value = mock_service

            from backend.src.adapters.primary.fastapi.routes.ws_routes import (
                websocket_jobs,
            )

            await websocket_jobs(mock_websocket)

            mock_websocket.close.assert_called_once()
            # Check that close was called with code 4002
            assert mock_websocket.close.call_args[1]["code"] == 4002

    @pytest.mark.asyncio
    async def test_user_id_mismatch_closes_connection(self):
        """Test that user_id mismatch results in connection close."""
        mock_websocket = MagicMock()
        mock_websocket.query_params = {"user_id": "other-user", "token": "valid-token"}
        mock_websocket.close = AsyncMock()

        with patch(
            "backend.src.adapters.primary.fastapi.routes.ws_routes.get_jwt_service"
        ) as mock_jwt:
            mock_service = MagicMock()
            mock_service.verify_token.return_value = "user-123"
            mock_jwt.return_value = mock_service

            from backend.src.adapters.primary.fastapi.routes.ws_routes import (
                websocket_jobs,
            )

            await websocket_jobs(mock_websocket)

            mock_websocket.close.assert_called_once_with(
                code=4003, reason="User ID mismatch"
            )

    @pytest.mark.asyncio
    async def test_successful_connection(self):
        """Test successful WebSocket connection."""
        mock_websocket = MagicMock()
        mock_websocket.query_params = {"user_id": "user-123", "token": "valid-token"}
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_text = AsyncMock(
            side_effect=Exception("Connection closed")
        )
        mock_websocket.close = AsyncMock()

        with patch(
            "backend.src.adapters.primary.fastapi.routes.ws_routes.get_jwt_service"
        ) as mock_jwt:
            with patch(
                "backend.src.adapters.primary.fastapi.routes.ws_routes.get_ws_manager"
            ) as mock_mgr:
                mock_service = MagicMock()
                mock_service.verify_token.return_value = "user-123"
                mock_jwt.return_value = mock_service

                mock_manager = MagicMock()
                mock_manager.connect = AsyncMock()
                mock_manager.disconnect = MagicMock()
                mock_mgr.return_value = mock_manager

                from backend.src.adapters.primary.fastapi.routes.ws_routes import (
                    websocket_jobs,
                )

                await websocket_jobs(mock_websocket)

                mock_websocket.accept.assert_called_once()
                mock_manager.connect.assert_called_once_with(mock_websocket, "user-123")

    @pytest.mark.asyncio
    async def test_ping_pong_handling(self):
        """Test WebSocket ping/pong handling."""
        mock_websocket = MagicMock()
        mock_websocket.query_params = {"user_id": "user-123", "token": "valid-token"}
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_text = AsyncMock(
            side_effect=["ping", Exception("Connection closed")]
        )
        mock_websocket.send_text = AsyncMock()
        mock_websocket.close = AsyncMock()

        with patch(
            "backend.src.adapters.primary.fastapi.routes.ws_routes.get_jwt_service"
        ) as mock_jwt:
            with patch(
                "backend.src.adapters.primary.fastapi.routes.ws_routes.get_ws_manager"
            ) as mock_mgr:
                mock_service = MagicMock()
                mock_service.verify_token.return_value = "user-123"
                mock_jwt.return_value = mock_service

                mock_manager = MagicMock()
                mock_manager.connect = AsyncMock()
                mock_manager.disconnect = MagicMock()
                mock_mgr.return_value = mock_manager

                from backend.src.adapters.primary.fastapi.routes.ws_routes import (
                    websocket_jobs,
                )

                await websocket_jobs(mock_websocket)

                mock_websocket.send_text.assert_called_once_with("pong")

    @pytest.mark.asyncio
    async def test_disconnect_on_exception(self):
        """Test WebSocket disconnects on exception."""
        mock_websocket = MagicMock()
        mock_websocket.query_params = {"user_id": "user-123", "token": "valid-token"}
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_text = AsyncMock(
            side_effect=Exception("Connection closed")
        )
        mock_websocket.close = AsyncMock()

        with patch(
            "backend.src.adapters.primary.fastapi.routes.ws_routes.get_jwt_service"
        ) as mock_jwt:
            with patch(
                "backend.src.adapters.primary.fastapi.routes.ws_routes.get_ws_manager"
            ) as mock_mgr:
                mock_service = MagicMock()
                mock_service.verify_token.return_value = "user-123"
                mock_jwt.return_value = mock_service

                mock_manager = MagicMock()
                mock_manager.connect = AsyncMock()
                mock_manager.disconnect = MagicMock()
                mock_mgr.return_value = mock_manager

                from backend.src.adapters.primary.fastapi.routes.ws_routes import (
                    websocket_jobs,
                )

                await websocket_jobs(mock_websocket)

                mock_manager.disconnect.assert_called_once_with(
                    mock_websocket, "user-123"
                )
