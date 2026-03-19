# Backend - FastAPI REST API + Worker

## Overview
FastAPI-based REST API that accepts report job requests, queues them via AWS SQS, processes them asynchronously with workers, and persists job state in AWS DynamoDB.

## Tech Stack
| Component | Technology |
|-----------|------------|
| API | FastAPI + Pydantic v2 + JWT (HS256) |
| Database | AWS DynamoDB (LocalStack) |
| Queue | AWS SQS (LocalStack) |
| Worker | Python asyncio + aiobotocore |
| Observability | CloudWatch Logs/Metrics (watchtower) |

## Architecture: Hexagonal

```
src/
├── domain/              # Pure business logic (no deps)
│   ├── entities/        # Job entity
│   ├── value_objects/    # JobStatus enum
│   └── exceptions/       # Domain exceptions
├── application/         # Use cases + ports
│   ├── ports/           # JobRepository, JobQueue interfaces
│   └── use_cases/       # CreateJob, GetJob, ListJobs, UpdateJobStatus
├── adapters/
│   ├── primary/fastapi/ # REST routes, WebSocket
│   └── secondary/       # DynamoDB, SQS implementations
├── config/              # Pydantic settings
└── shared/              # JWT, exceptions, observability

worker/                  # SQS consumer (async processor)
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /auth/token | No | Login with user_id → JWT |
| POST | /jobs | JWT | Create report job |
| GET | /jobs | JWT | List user's jobs (paginated) |
| GET | /jobs/{job_id} | JWT | Get job details |
| GET | /health | No | Health check |
| WS | /ws/jobs/{user_id} | JWT | Real-time updates |
| POST | /internal/notify | Internal | Worker notification endpoint |

## Data Model (DynamoDB)

**Table: jobs**
| Attribute | Type | Key |
|-----------|------|-----|
| job_id | String | PK |
| user_id | String | GSI |
| status | String | - |
| report_type | String | - |
| date_range | String | - |
| format | String | - |
| result_url | String | - |
| version | Number | - |
| created_at | String | - |
| updated_at | String | - |

**GSI:** user_id-created_at-index (for user queries)

**Table: idempotency_keys** (TTL: 24h)
| Attribute | Type | Key |
|-----------|------|-----|
| idempotency_key | String | PK |
| job_id | String | - |
| expires_at | Number | TTL |

## Worker

- **Concurrency:** asyncio.gather (2+ concurrent jobs)
- **Processing:** 5-30s random sleep + dummy result
- **Status Flow:** PENDING → PROCESSING → COMPLETED/FAILED
- **Features:** Dead Letter Queue, Circuit Breaker, Exponential Back-off
- **Priority Queues:** HIGH (sales_report, financial_report) → `report-jobs-priority`
- **Notifications:** POST /internal/notify after status change

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| AWS_ENDPOINT_URL | http://localhost:4566 | LocalStack |
| AWS_REGION | us-east-1 | AWS region |
| AWS_ACCESS_KEY_ID | test | Credentials |
| AWS_SECRET_ACCESS_KEY | test | Credentials |
| DYNAMODB_TABLE_JOBS | jobs | Table name |
| JWT_SECRET_KEY | (required) | JWT signing key |
| JWT_ALGORITHM | HS256 | Algorithm |
| API_BASE_URL | http://localhost:8000 | For worker notifications |

## Commands

```bash
# Initialize DynamoDB tables
python init_db.py

# Run tests
pytest tests/ -v --cov=src

# Run locally (requires Docker for LocalStack)
cd backend && PYTHONPATH=.. uvicorn src.adapters.primary.fastapi.main:app --reload
```

## Key Files

| File | Purpose |
|------|---------|
| src/adapters/primary/fastapi/main.py | FastAPI app entry point |
| src/adapters/primary/fastapi/routes/jobs.py | /jobs endpoints |
| src/adapters/primary/fastapi/routes/ws_routes.py | WebSocket endpoint |
| src/adapters/secondary/dynamodb/job_repository.py | DynamoDB implementation |
| src/adapters/secondary/sqs/job_queue.py | SQS implementation + priority |
| worker/main.py | Worker entry point |
| worker/processor.py | Job processing logic |

## Observability

- Structured logging (structlog) → JSON logs
- CloudWatch metrics: JobsProcessed, JobsFailed, ProcessingDuration
- CloudWatch logs via watchtower

## Idempotency & Concurrency

- Header: X-Idempotency-Key (TTL: 24h)
- Optimistic locking: version field with conditional writes
- HTTP 409 on version conflict
