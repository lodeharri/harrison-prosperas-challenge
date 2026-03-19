"""WebSocket connection manager for real-time job notifications."""

import json
import logging
from typing import Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections per user for real-time notifications.

    When a job status changes, the worker calls this manager to notify
    all connected clients for that user.
    """

    def __init__(self) -> None:
        # user_id -> list of WebSocket connections
        self._connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """
        Accept a new WebSocket connection for a user.

        Note: The websocket.accept() is called in the route handler before
        calling this method, so we don't call it here.

        Args:
            websocket: The WebSocket connection
            user_id: User identifier
        """
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
        logger.info(f"WebSocket connected for user {user_id}")

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """
        Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove
            user_id: User identifier
        """
        if user_id in self._connections:
            if websocket in self._connections[user_id]:
                self._connections[user_id].remove(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]
        logger.info(f"WebSocket disconnected for user {user_id}")

    async def notify_job_update(self, user_id: str, job_data: dict) -> None:
        """
        Send job update notification to all connected clients for a user.

        Args:
            user_id: User to notify
            job_data: Job data to send (job_id, status, result_url, etc.)
        """
        if user_id not in self._connections:
            return

        message = json.dumps(
            {
                "type": "job_update",
                "data": job_data,
            }
        )

        disconnected = []
        for websocket in self._connections[user_id]:
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.append(websocket)

        # Clean up disconnected sockets
        for ws in disconnected:
            self.disconnect(ws, user_id)

    def get_connection_count(self, user_id: str) -> int:
        """
        Get the number of active connections for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of active connections
        """
        return len(self._connections.get(user_id, []))


# Global instance
ws_manager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    return ws_manager
