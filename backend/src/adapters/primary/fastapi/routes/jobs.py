"""FastAPI routes for job management.

This adapter translates HTTP requests to use case invocations
and HTTP responses back to the client.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from starlette.responses import Response

from backend.src.adapters.primary.fastapi.routes.dependencies import (
    get_current_user,
    get_create_job_use_case,
    get_get_job_use_case,
    get_list_jobs_use_case,
)
from backend.src.application.use_cases.create_job import CreateJobUseCase
from backend.src.application.use_cases.get_job import GetJobUseCase
from backend.src.application.use_cases.list_jobs import ListJobsUseCase
from backend.src.domain.exceptions.domain_exceptions import (
    JobAccessDeniedException,
    JobNotFoundException,
)
from backend.src.shared.exceptions import ForbiddenException, NotFoundException
from backend.src.shared.schemas import (
    JobCreate,
    JobCreateResponse,
    JobListResponse,
    JobResponse,
    TokenRequest,
    TokenResponse,
)
from backend.src.shared.jwt_service import get_jwt_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=201,
    summary="Create a new report job",
    description="Creates a new report job, stores it in DynamoDB, and publishes to SQS queue.",
    responses={
        200: {
            "description": "Job created (or existing job returned for idempotent request)",
        },
    },
)
async def create_job(
    job_create: JobCreate,
    current_user: Annotated[str, Depends(get_current_user)],
    create_job_use_case: Annotated[CreateJobUseCase, Depends(get_create_job_use_case)],
    x_idempotency_key: Annotated[
        str | None,
        Header(
            alias="X-Idempotency-Key",
            description="Optional idempotency key for safe request retries",
        ),
    ] = None,
) -> JobCreateResponse:
    """
    Create a new report job.

    - Generates a unique job_id
    - Stores job in DynamoDB with PENDING status
    - Publishes job message to SQS for async processing
    - Returns job_id and status

    Idempotency:
    - If X-Idempotency-Key header is provided and a job with that key exists,
      returns the existing job instead of creating a new one
    - The idempotent field in the response indicates if this was a cached response
    """
    result = await create_job_use_case.execute(
        user_id=current_user,
        report_type=job_create.report_type,
        date_range=job_create.date_range,
        format=job_create.format,
        idempotency_key=x_idempotency_key,
    )

    if result.idempotent:
        logger.info(
            f"Returned existing job {result.job.job_id} for idempotency key "
            f"{x_idempotency_key} (user: {current_user})"
        )
    else:
        logger.info(f"Created job {result.job.job_id} for user {current_user}")

    return JobCreateResponse(
        job_id=result.job.job_id,
        status=result.job.status,
        idempotent=result.idempotent,
    )


@router.get(
    "",
    response_model=JobListResponse,
    summary="List user's jobs",
    description="Returns a paginated list of jobs for the authenticated user.",
)
async def list_jobs(
    current_user: Annotated[str, Depends(get_current_user)],
    list_jobs_use_case: Annotated[ListJobsUseCase, Depends(get_list_jobs_use_case)],
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    page_size: Annotated[
        int,
        Query(ge=20, le=100, description="Number of items per page (minimum 20)"),
    ] = 20,
) -> JobListResponse:
    """
    List jobs for the authenticated user with pagination.

    - Enforces minimum page size of 20 items
    - Returns jobs sorted by creation date (newest first)
    - Includes total count for pagination
    """
    jobs, total = await list_jobs_use_case.execute(
        user_id=current_user,
        page=page,
        page_size=page_size,
    )

    return JobListResponse(
        items=[JobResponse.from_entity(job) for job in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job by ID",
    description="Returns the details of a specific job by its ID.",
)
async def get_job(
    job_id: str,
    current_user: Annotated[str, Depends(get_current_user)],
    get_job_use_case: Annotated[GetJobUseCase, Depends(get_get_job_use_case)],
) -> JobResponse:
    """
    Get a job by its ID.

    - Verifies the job belongs to the authenticated user
    - Returns full job details including result_url if completed
    """
    try:
        job = await get_job_use_case.execute(
            job_id=job_id,
            requesting_user_id=current_user,
        )
        return JobResponse.from_entity(job)

    except JobNotFoundException:
        raise NotFoundException(resource="Job", identifier=job_id)

    except JobAccessDeniedException:
        raise ForbiddenException("You don't have access to this job")


# Authentication router for testing purposes
auth_router = APIRouter(prefix="/auth", tags=["authentication"])


@auth_router.options(
    "/token",
    summary="CORS preflight",
    description="Handle CORS preflight requests for the token endpoint.",
    include_in_schema=False,
)
async def options_token() -> Response:
    """Handle CORS preflight requests."""
    return Response(
        content="",
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Allow-Credentials": "true",
        },
    )


@auth_router.post(
    "/token",
    response_model=TokenResponse,
    summary="Get access token",
    description="Generate a JWT access token for testing (in production, use proper auth).",
)
async def get_token(
    token_request: TokenRequest,
) -> TokenResponse:
    """
    Get an access token for testing purposes.

    In production, this would be replaced with proper authentication
    (e.g., OAuth2, LDAP, etc.)
    """
    jwt_service = get_jwt_service()
    return jwt_service.create_access_token(token_request.user_id)
