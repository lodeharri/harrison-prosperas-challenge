"""WebSocket routes for real-time notifications."""

from fastapi import APIRouter, WebSocket

from backend.src.services.websocket_manager import get_ws_manager
from backend.src.shared.jwt_service import get_jwt_service

router = APIRouter(tags=["websocket"])


@router.websocket("/jobs")
async def websocket_jobs(websocket: WebSocket):
    """WebSocket endpoint for real-time job updates.

    Connect: ws://localhost:8000/ws/jobs?user_id={user_id}&token={jwt_token}
    """
    # Get query params
    params = dict(websocket.query_params)
    user_id = params.get("user_id")
    token = params.get("token")

    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    if not user_id:
        await websocket.close(code=4004, reason="Missing user_id")
        return

    # Validate token and verify user_id matches
    try:
        jwt_svc = get_jwt_service()
        # verify_token returns the user_id (str) from the token
        token_user_id = jwt_svc.verify_token(token)

        if token_user_id != user_id:
            await websocket.close(code=4003, reason="User ID mismatch")
            return
    except Exception as e:
        await websocket.close(code=4002, reason=f"Invalid token: {e}")
        return

    # Accept connection and connect to manager
    await websocket.accept()
    ws_mgr = get_ws_manager()
    await ws_mgr.connect(websocket, user_id)

    try:
        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except Exception as e:
        # Log the exception but don't re-raise (normal disconnection)
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"WebSocket closed for user {user_id}: {type(e).__name__}: {e}")
        ws_mgr.disconnect(websocket, user_id)
