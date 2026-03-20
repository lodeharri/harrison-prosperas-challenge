"""Internal endpoint for worker to send WebSocket notifications."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.src.services.websocket_manager import get_ws_manager

router = APIRouter(prefix="/internal", tags=["internal"])


class NotifyRequest(BaseModel):
    """Request schema for job update notification."""

    user_id: str = Field(description="User to notify")
    job_id: str = Field(description="Job identifier")
    status: str = Field(description="New job status")
    result_url: str | None = Field(
        default=None,
        description="URL to download result (if completed)",
    )
    updated_at: str = Field(description="Last update timestamp (ISO format)")
    report_type: str | None = Field(
        default=None,
        description="Type of report",
    )


@router.post("/notify")
async def notify_job_update(request: NotifyRequest) -> dict:
    """
    Called by worker to notify frontend via WebSocket.

    This endpoint receives notifications from the worker after job status changes
    and forwards them to connected WebSocket clients.
    """
    ws_manager = get_ws_manager()

    await ws_manager.notify_job_update(
        user_id=request.user_id,
        job_data={
            "job_id": request.job_id,
            "status": request.status,
            "result_url": request.result_url,
            "updated_at": request.updated_at,
            "report_type": request.report_type,
        },
    )

    return {"ok": True}


@router.get("/connections/{user_id}")
async def get_connection_count(user_id: str) -> dict:
    """
    Get the number of active WebSocket connections for a user.

    Useful for debugging and monitoring.
    """
    ws_manager = get_ws_manager()
    count = ws_manager.get_connection_count(user_id)
    return {"user_id": user_id, "connections": count}
