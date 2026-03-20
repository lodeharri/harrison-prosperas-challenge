# Backend - FastAPI REST API + Worker

## Overview
FastAPI-based REST API that accepts report job requests, queues them via AWS SQS, processes them asynchronously with workers, and persists job state in AWS DynamoDB.

## Tech Stack
| Component | Technology |
|-----------|------------|
| API | FastAPI + Pydantic v2 + JWT (HS256) |
| Database | AWS DynamoDB (LocalStack for dev, AWS for prod) |
| Queue | AWS SQS (LocalStack for dev, AWS for prod) |
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

## Environment Detection Logic

The application automatically detects the environment based on `AWS_ENDPOINT_URL`:

| Environment | `AWS_ENDPOINT_URL` | Behavior |
|-------------|-------------------|----------|
| LocalStack (dev) | Defined (e.g., `http://localhost:4566`) | Creates resources, uses local endpoints |
| AWS Production | NOT defined | Uses native AWS, CDK handles provisioning |

**Computed Properties:**
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

**GSI:** user_id-created_at-index (for user queries)

**Table: idempotency_keys** (`harrison-idempotency` in production, TTL: 24h)
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
|----------|-----------------|------------------|-------------|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | NOT SET | LocalStack endpoint |
| `AWS_REGION` | `us-east-1` | `us-east-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | `test` | From IRSA/CDK | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | `test` | From IRSA/CDK | AWS credentials |

### DynamoDB Tables

| Variable | LocalStack (Dev) | Production (AWS) | Description |
|----------|-----------------|------------------|-------------|
| `DYNAMODB_TABLE_JOBS` | `jobs` | `harrison-jobs` | Jobs table name |
| `DYNAMODB_TABLE_IDEMPOTENCY` | `idempotency_keys` | `harrison-idempotency` | Idempotency table |

### SQS Queues

| Variable | LocalStack (Dev) | Production (AWS) | Description |
|----------|-----------------|------------------|-------------|
| `SQS_QUEUE_URL` | `http://localhost:4566/.../harrison-jobs-queue` | Full SQS URL | Main queue URL |
| `SQS_DLQ_URL` | `http://localhost:4566/.../harrison-jobs-dlq` | Full SQS URL | DLQ URL |
| `SQS_PRIORITY_QUEUE_URL` | `http://localhost:4566/.../harrison-jobs-priority` | Full SQS URL | Priority queue URL |
| `SQS_QUEUE_NAME` | `harrison-jobs-queue` | `harrison-jobs-queue` | Queue name |
| `SQS_DLQ_NAME` | `harrison-jobs-dlq` | `harrison-jobs-dlq` | DLQ name |
| `SQS_PRIORITY_QUEUE_NAME` | `harrison-jobs-priority` | `harrison-jobs-priority` | Priority queue name |

### JWT Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | `super-secret-key...` | JWT signing key (use Secrets Manager in prod) |
| `JWT_ALGORITHM` | `HS256` | Algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token expiration |

### Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Debug mode |
| `API_BASE_URL` | `http://localhost:8000` | For worker notifications |
| `CLOUDWATCH_LOG_GROUP` | `/reto-prosperas/jobs` | CloudWatch log group |
| `CLOUDWATCH_STREAM_NAME` | `worker` | CloudWatch stream name |

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
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | `300` | Circuit breaker recovery (s) |
| `BACKOFF_BASE_DELAY` | `1.0` | Backoff base delay (s) |
| `BACKOFF_MAX_DELAY` | `60.0` | Backoff max delay (s) |
| `LOG_LEVEL` | `INFO` | Log level |

## AWS Production Resource Names

CDK creates these resources in AWS:

| Resource | Name |
|----------|------|
| DynamoDB Table | `harrison-jobs` |
| DynamoDB Table | `harrison-idempotency` |
| SQS Queue | `harrison-jobs-queue` |
| SQS DLQ | `harrison-jobs-dlq` |
| SQS Priority Queue | `harrison-jobs-priority` |

## Commands

```bash
# Initialize DynamoDB tables and SQS queues
# LocalStack: Creates resources
python init_db.py

# AWS Production: Verifies resources exist (CDK should have provisioned them)
python init_db.py

# Run tests
pytest tests/ -v --cov=src

# Run locally (requires Docker for LocalStack)
cd backend && PYTHONPATH=.. uvicorn src.adapters.primary.fastapi.main:app --reload

# Run worker locally
cd backend && PYTHONPATH=.. python -m worker.main
```

## Key Files

| File | Purpose |
|------|---------|
| src/config/settings.py | API settings with LocalStack/AWS detection |
| worker/config.py | Worker settings with LocalStack/AWS detection |
| init_db.py | Database initialization (creates or verifies) |
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
