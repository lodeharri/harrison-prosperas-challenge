# Backend - FastAPI REST API + Worker

**Project:** Reto Prosperas - Report Job Processing System  
**Directory:** `backend/`

## Context

This is the **Backend Module** of the Reto Prosperas project. The full project context is documented in the root `AGENTS.md`.

### What is Reto Prosperas?
A system that allows users to create report jobs, processes them asynchronously via AWS SQS workers, and receives real-time notifications via WebSocket when jobs complete.

### Architecture Overview
```
Frontend (React SPA)
      │
      ▼ (REST + WebSocket)
Backend (FastAPI) ◄──────────────┐
      │                         │
      ▼ (SQS + DynamoDB)         │
Worker (SQS Consumer)           │
      │                         │
      ▼ (POST /internal/notify)─┘
```

## Scope

| Component | Responsibility |
|-----------|----------------|
| **API** | Accept job requests, store in DynamoDB, send to SQS |
| **WebSocket** | Real-time notifications to connected frontend clients |
| **/internal/notify** | Endpoint called by Worker to broadcast job status changes |
| **NOT** | Does NOT process jobs - that's the Worker's job |

## Complete Flow

```
1. User creates job (Frontend POST /jobs)
         │
2. API: saves to DynamoDB → sends to SQS → returns job_id
         │
3. Worker: receives from SQS → processes (5-30s) → updates DynamoDB
         │
4. Worker: POST /internal/notify {job_id, status, result_url}
         │
5. API: WebSocketManager broadcasts to user's connection
         │
6. Frontend: receives {"type":"job_update", "data":{...}} → updates UI
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| API | FastAPI + Pydantic v2 + JWT (HS256) |
| Database | AWS DynamoDB (LocalStack for dev, AWS for prod) |
| Queue | AWS SQS (LocalStack for dev, AWS for prod) |
| Worker | Python asyncio + aiobotocore |
| Observability | CloudWatch Logs/Metrics (watchtower) |

## Environment Detection

The app detects environment via `AWS_ENDPOINT_URL`:

| Environment | AWS_ENDPOINT_URL | Behavior |
|-------------|------------------|----------|
| LocalStack (dev) | `http://localhost:4566` | Creates resources locally |
| Production | NOT set | Uses real AWS |

```python
settings.is_localstack  # True if AWS_ENDPOINT_URL is set
settings.is_production # True if AWS_ENDPOINT_URL is NOT set
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

## Worker Integration

The Worker processes jobs and notifies the API via `/internal/notify`:

```python
# Worker calls this after status change
POST /internal/notify
{
    "user_id": "user-123",
    "job_id": "job-456",
    "status": "COMPLETED",
    "result_url": "https://...",
    "updated_at": "2026-03-24T10:00:00Z",
    "report_type": "sales_report"
}
```

**Environment Variable:** `API_BASE_URL` in Worker must point to the API (ALB in production).

## Architecture: Hexagonal

```
src/
├── domain/              # Pure business logic (no deps)
│   ├── entities/        # Job entity
│   ├── value_objects/   # JobStatus enum
│   └── exceptions/     # Domain exceptions
├── application/        # Use cases + ports
│   ├── ports/          # JobRepository, JobQueue interfaces
│   └── use_cases/      # CreateJob, GetJob, ListJobs
├── adapters/
│   ├── primary/fastapi/ # REST routes, WebSocket
│   └── secondary/      # DynamoDB, SQS implementations
├── config/             # Pydantic settings
└── shared/             # JWT, exceptions, observability

worker/                  # SQS consumer (async processor)
```

## If You Need To...

| Task | Go To |
|------|-------|
| Modify REST endpoints | `src/adapters/primary/fastapi/routes/jobs.py` |
| Modify WebSocket | `src/adapters/primary/fastapi/routes/ws_routes.py` |
| Modify notification endpoint | `src/adapters/primary/fastapi/routes/notify.py` |
| Change data model | `src/domain/entities/job.py` |
| Change job status logic | `src/domain/value_objects/job_status.py` |
| Modify DynamoDB logic | `src/adapters/secondary/dynamodb/job_repository.py` |
| Modify SQS logic | `src/adapters/secondary/sqs/job_queue.py` |
| Change API settings | `src/config/settings.py` |
| Modify worker (different module) | `worker/` |
| Modify worker settings | `worker/config.py` |
| Modify worker processing | `worker/processor.py` |
| Run tests | `pytest tests/ -v` or `pytest worker/tests/ -v` |

## Data Model (DynamoDB)

**Table: jobs** (`harrison-jobs` in production)
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

**GSI:** user_id-created_at-index

**Table: idempotency_keys** (`harrison-idempotency`, TTL: 24h)
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
- **Priority Queues:** HIGH (sales_report, financial_report) → `harrison-jobs-priority`
- **Notifications:** POST /internal/notify after status change

## Environment Variables

### AWS Configuration

| Variable | LocalStack (Dev) | Production (AWS) | Description |
|----------|------------------|------------------|-------------|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | NOT SET | LocalStack endpoint |
| `AWS_REGION` | `us-east-1` | `us-east-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | `test` | From IRSA/CDK | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | `test` | From IRSA/CDK | AWS credentials |

### DynamoDB Tables

| Variable | LocalStack (Dev) | Production (AWS) | Description |
|----------|------------------|------------------|-------------|
| `DYNAMODB_TABLE_JOBS` | `jobs` | `harrison-jobs` | Jobs table name |
| `DYNAMODB_TABLE_IDEMPOTENCY` | `idempotency_keys` | `harrison-idempotency` | Idempotency table |

### SQS Queues

| Variable | LocalStack (Dev) | Production (AWS) | Description |
|----------|------------------|------------------|-------------|
| `SQS_QUEUE_URL` | `http://localhost:4566/.../harrison-jobs-queue` | Full SQS URL | Main queue URL |
| `SQS_DLQ_URL` | `http://localhost:4566/.../harrison-jobs-dlq` | Full SQS URL | DLQ URL |
| `SQS_PRIORITY_QUEUE_URL` | `http://localhost:4566/.../harrison-jobs-priority` | Full SQS URL | Priority queue URL |

### JWT Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | `super-secret-key...` | JWT signing key |
| `JWT_ALGORITHM` | `HS256` | Algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token expiration |

### Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Debug mode |
| `API_BASE_URL` | `http://localhost:8000` | For worker notifications |
| `CLOUDWATCH_LOG_GROUP` | `/reto-prosperas/jobs` | CloudWatch log group |

### Worker Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_CONCURRENT_JOBS` | `10` | Max parallel jobs |
| `MIN_CONCURRENT_JOBS` | `2` | Min parallel jobs |
| `POLL_INTERVAL_SECONDS` | `1.0` | SQS poll interval |
| `MAX_RECEIVE_MESSAGES` | `10` | Max messages per poll |
| `VISIBILITY_TIMEOUT` | `60` | SQS visibility timeout |
| `MAX_RETRIES` | `3` | Max job retries |
| `MIN_PROCESSING_TIME` | `5.0` | Min job processing time (s) |
| `MAX_PROCESSING_TIME` | `30.0` | Max job processing time (s) |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Circuit breaker threshold |
| `BACKOFF_BASE_DELAY` | `1.0` | Backoff base delay (s) |
| `LOG_LEVEL` | `INFO` | Log level |

## AWS Production Resource Names

| Resource | Name |
|----------|------|
| DynamoDB Table | `harrison-jobs` |
| DynamoDB Table | `harrison-idempotency` |
| SQS Queue | `harrison-jobs-queue` |
| SQS DLQ | `harrison-jobs-dlq` |
| SQS Priority Queue | `harrison-jobs-priority` |

## Commands

```bash
# Initialize DynamoDB tables and SQS queues (creates locally, verifies in prod)
python init_db.py

# Run API locally (requires Docker for LocalStack)
cd backend
PYTHONPATH=.. uvicorn src.adapters.primary.fastapi.main:app --reload

# Run worker locally (requires LocalStack running)
cd backend
PYTHONPATH=.. python -m worker.main

# Run tests
pytest tests/ -v --cov=src
pytest worker/tests/ -v

# Docker compose (from project root)
docker compose up localstack -d
docker compose up api
docker compose up worker
```

## Key Files

| File | Purpose |
|------|---------|
| src/adapters/primary/fastapi/main.py | FastAPI app entry point, routers, exception handlers |
| src/adapters/primary/fastapi/routes/jobs.py | /jobs endpoints (create, list, get) |
| src/adapters/primary/fastapi/routes/ws_routes.py | WebSocket endpoint /ws/jobs |
| src/adapters/primary/fastapi/routes/notify.py | /internal/notify endpoint |
| src/adapters/secondary/dynamodb/job_repository.py | DynamoDB implementation |
| src/adapters/secondary/sqs/job_queue.py | SQS implementation |
| src/domain/entities/job.py | Job entity |
| src/domain/value_objects/job_status.py | JobStatus enum |
| src/config/settings.py | API settings |
| src/services/websocket_manager.py | WebSocket connection manager |
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