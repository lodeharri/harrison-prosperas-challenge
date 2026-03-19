"""HTTP client for worker to communicate with the API.

Used for sending WebSocket notifications after job status changes.
"""

from typing import Any

import httpx
import structlog

from backend.worker.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class HttpClient:
    """HTTP client for making requests to the API."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize HTTP client."""
        self._settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.api_base_url,
                timeout=10.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def notify_job_update(
        self,
        user_id: str,
        job_id: str,
        status: str,
        result_url: str | None = None,
        updated_at: str | None = None,
        report_type: str | None = None,
    ) -> bool:
        """
        Send job update notification to the API.

        The API will forward this to connected WebSocket clients.

        Args:
            user_id: User who owns the job
            job_id: Job identifier
            status: New job status
            result_url: Optional result URL
            updated_at: ISO timestamp of the update
            report_type: Type of report

        Returns:
            True if notification was sent successfully
        """
        payload: dict[str, Any] = {
            "user_id": user_id,
            "job_id": job_id,
            "status": status,
        }

        if result_url is not None:
            payload["result_url"] = result_url
        if updated_at is not None:
            payload["updated_at"] = updated_at
        if report_type is not None:
            payload["report_type"] = report_type

        try:
            response = await self.client.post("/internal/notify", json=payload)
            if response.status_code == 200:
                logger.info(
                    "notification_sent",
                    job_id=job_id,
                    user_id=user_id,
                    status=status,
                )
                return True
            else:
                logger.warning(
                    "notification_failed",
                    job_id=job_id,
                    status_code=response.status_code,
                    response=response.text,
                )
                return False
        except httpx.RequestError as e:
            logger.warning(
                "notification_error",
                job_id=job_id,
                error=str(e),
            )
            return False
        except Exception as e:
            logger.error(
                "notification_unexpected_error",
                job_id=job_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return False


# Global instance
_http_client: HttpClient | None = None


def get_http_client() -> HttpClient:
    """Get the global HTTP client instance."""
    global _http_client
    if _http_client is None:
        _http_client = HttpClient()
    return _http_client
