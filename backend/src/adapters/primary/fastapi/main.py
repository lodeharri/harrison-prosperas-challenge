"""FastAPI application entry point with global exception handlers.

This is the primary adapter that handles HTTP requests
and translates them to use cases.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.src.adapters.primary.fastapi.routes import auth_router, jobs
from backend.src.adapters.primary.fastapi.routes.dependencies import (
    get_job_queue,
    get_job_repository,
)
from backend.src.config.settings import get_settings
from backend.src.shared.exceptions import AppException
from backend.src.shared.schemas import ErrorDetail, ErrorResponse, HealthResponse

if TYPE_CHECKING:
    from backend.src.config.settings import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Health check router
router = APIRouter()


def create_app(settings: "Settings | None" = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        settings: Optional settings instance (defaults to environment config)

    Returns:
        Configured FastAPI application instance
    """
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Report Job Processing System API",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Include routers
    app.include_router(jobs.router)
    app.include_router(auth_router)
    app.include_router(router)  # Health check router

    # Register exception handlers
    register_exception_handlers(app)

    # Register startup/shutdown events
    register_events(app)

    return app


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for the application."""

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        """
        Handle custom application exceptions.

        Returns consistent error response format for all AppException types.
        """
        logger.warning(
            f"AppException: {exc.error_code} - {exc.message} (path: {request.url.path})"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """
        Handle Pydantic validation errors.

        Returns detailed validation error information.
        """
        logger.warning(f"ValidationError: {exc.errors()} (path: {request.url.path})")
        errors = exc.errors()
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="VALIDATION_ERROR",
                    message="Request validation failed",
                    details={"errors": errors},
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """
        Handle unexpected exceptions.

        Logs the error and returns a generic 500 response.
        """
        logger.exception(f"Unexpected error: {exc} (path: {request.url.path})")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_SERVER_ERROR",
                    message="An unexpected error occurred",
                )
            ).model_dump(),
        )


def register_events(app: FastAPI) -> None:
    """Register startup and shutdown events."""

    @app.on_event("startup")
    async def startup_event() -> None:
        """Run on application startup."""
        logger.info("Starting Reto Prosperas API...")

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        """Run on application shutdown."""
        logger.info("Shutting down Reto Prosperas API...")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the health status of the API and its dependencies.",
    tags=["health"],
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Checks connectivity to DynamoDB and SQS.
    Returns overall status and individual dependency statuses.
    """
    settings = get_settings()
    repository = get_job_repository()
    queue = get_job_queue()

    dependencies: dict[str, str] = {}

    # Check DynamoDB
    try:
        dynamodb_healthy = await repository.health_check()
        dependencies["dynamodb"] = "ok" if dynamodb_healthy else "error"
    except Exception as e:
        logger.error(f"DynamoDB health check failed: {e}")
        dependencies["dynamodb"] = "error"

    # Check SQS
    try:
        sqs_healthy = queue.health_check()
        dependencies["sqs"] = "ok" if sqs_healthy else "error"
    except Exception as e:
        logger.error(f"SQS health check failed: {e}")
        dependencies["sqs"] = "error"

    # Determine overall status
    all_healthy = all(s == "ok" for s in dependencies.values())
    overall_status = "healthy" if all_healthy else "degraded"

    return HealthResponse(
        status=overall_status,
        version=settings.app_version,
        dependencies=dependencies,
    )


# Application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.src.adapters.primary.fastapi.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
