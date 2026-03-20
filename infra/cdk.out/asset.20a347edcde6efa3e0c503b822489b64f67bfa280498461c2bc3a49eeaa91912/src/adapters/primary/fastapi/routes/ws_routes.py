"""WebSocket routes for real-time notifications."""

import logging
from fastapi import APIRouter, WebSocket

from backend.src.services.websocket_manager import get_ws_manager
from backend.src.shared.jwt_service import get_jwt_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/jobs")
async def websocket_jobs(websocket: WebSocket):
    """WebSocket endpoint for real-time job updates.

    Connect: ws://localhost:8000/ws/jobs?user_id={user_id}&token={jwt_token}
    """
    # Get raw query params
    raw_params = dict(websocket.query_params)
    logger.info(f"WebSocket connection attempt - raw params keys: {list(raw_params.keys())}")
    
    # Decode values if needed
    user_id = raw_params.get("user_id", "")
    token = raw_params.get("token", "")
    
    logger.info(f"WebSocket params - user_id: {user_id[:20] if user_id else 'None'}..., token present: {bool(token)}")

    if not token:
        logger.warning("WebSocket rejected: Missing token")
        await websocket.close(code=4001, reason="Missing token")
        return

    if not user_id:
        logger.warning("WebSocket rejected: Missing user_id")
        await websocket.close(code=4004, reason="Missing user_id")
        return

    # Validate token and verify user_id matches
    try:
        jwt_svc = get_jwt_service()
        token_user_id = jwt_svc.verify_token(token)
        logger.info(f"Token validated - token_user_id: {token_user_id}, param_user_id: {user_id}")

        if token_user_id != user_id:
            logger.warning(f"WebSocket rejected: User ID mismatch - token: {token_user_id}, param: {user_id}")
            await websocket.close(code=4003, reason="User ID mismatch")
            return
    except Exception as e:
        logger.error(f"WebSocket rejected: Invalid token - {type(e).__name__}: {e}")
        await websocket.close(code=4002, reason=f"Invalid token: {e}")
        return

    # Accept connection and connect to manager
    await websocket.accept()
    ws_mgr = get_ws_manager()
    await ws_mgr.connect(websocket, user_id)
    logger.info(f"WebSocket connected successfully for user: {user_id}")

    try:
        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except Exception as e:
        logger.info(f"WebSocket closed for user {user_id}: {type(e).__name__}: {e}")
        ws_mgr.disconnect(websocket, user_id)
