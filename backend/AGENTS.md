# Reto Prosperas Backend Module - Hexagonal Architecture

**Module:** FastAPI REST API  
**Directory:** `/home/harri/development/projects/harrison-prosperas-challenge/backend`  
**Architecture:** Hexagonal (Ports & Adapters)  
**Status:** ✅ IMPLEMENTED

---

## Quick Start

```bash
# From project root, start with Docker
docker compose up -d

# Or run locally (from backend directory)
cd backend
pip install -r requirements.txt
PYTHONPATH=.. uvicorn src.adapters.primary.fastapi.main:app --reload --host 0.0.0.0 --port 8000
```

## Setup Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run in development mode (from backend directory)
cd backend
PYTHONPATH=.. uvicorn src.adapters.primary.fastapi.main:app --reload --host 0.0.0.0 --port 8000

# Run tests with coverage
PYTHONPATH=.. pytest tests/ -v
PYTHONPATH=.. pytest tests/ --cov=src --cov-report=term-missing

# Run specific test module
PYTHONPATH=.. pytest tests/unit/domain/ -v

# Initialize DynamoDB tables (requires LocalStack)
python init_db.py

# Run with Docker (from project root)
docker compose up backend
```

---

## Architecture Overview

The backend follows **Hexagonal Architecture** (Ports & Adapters):

```
src/
├── domain/                    # 🏛️ CORE DOMAIN (no external dependencies)
│   ├── entities/
│   │   └── job.py           # Job entity with business logic
│   ├── value_objects/
│   │   └── job_status.py    # JobStatus enum with state machine
│   └── exceptions/
│       └── domain_exceptions.py
│
├── application/              # 🏛️ APPLICATION LAYER
│   ├── ports/               # 🔌 Interfaces (contracts)
│   │   ├── job_repository.py
│   │   └── job_queue.py
│   └── use_cases/
│       ├── create_job.py
│       ├── get_job.py
│       ├── list_jobs.py
│       └── update_job_status.py
│
├── adapters/                # 🔌 ADAPTERS (implementations)
│   ├── primary/             # Primary (driving) adapters
│   │   └── fastapi/
│   │       ├── routes/     # FastAPI endpoints
│   │       └── main.py     # App factory
│   └── secondary/          # Secondary (driven) adapters
│       ├── dynamodb/       # DynamoDB implementation
│       └── sqs/           # SQS implementation
│
├── config/                  # ⚙️ CONFIGURATION
│   └── settings.py
│
└── shared/                  # 🛠️ SHARED UTILITIES
    ├── dependencies.py
    ├── exceptions.py
    ├── jwt_service.py
    ├── observability.py    # CloudWatch metrics & logging
    └── schemas.py
```

---

## SOLID Principles Applied

| Letter | Principle | Implementation |
|--------|-----------|----------------|
| **S** | Single Responsibility | Each class has one reason to change |
| **O** | Open/Closed | New adapters without modifying domain |
| **L** | Liskov Substitution | Any port implementation is interchangeable |
| **I** | Interface Segregation | Small, focused ports (JobRepository, not Repository) |
| **D** | Dependency Inversion | Domain depends on abstractions, not implementations |

### Dependency Rule

```
Domain ──────► Application ──────► Adapters
(no deps)     (depends on ports)  (implements ports)
```

- **Domain**: Pure Python, no external dependencies
- **Application**: Depends on Ports (interfaces)
- **Adapters**: Implement Ports using infrastructure (boto3, FastAPI)

---

## Ports (Interfaces)

### JobRepository Port
```python
class JobRepository(Protocol):
    async def create(self, job: Job) -> Job: ...
    async def get_by_id(self, job_id: str) -> Job | None: ...
    async def list_by_user(self, user_id: str, limit: int, last_key: str | None) -> tuple[list[Job], str | None]: ...
    async def update_status(self, job_id: str, status: JobStatus, result_url: str | None = None) -> Job: ...
```

### JobQueue Port
```python
class JobQueue(Protocol):
    async def publish(self, job: Job) -> None: ...
    async def publish_priority(self, job: Job) -> None: ...
```

---

## Tech Stack

| Component | Library | Version | Purpose |
|-----------|---------|---------|---------|
| Framework | FastAPI | >= 0.109 | REST API |
| Validation | Pydantic | v2 | Request/response validation |
| Auth | python-jose | >= 3.3 | JWT token handling |
| AWS SDK | boto3 | >= 1.34 | DynamoDB + SQS |
| Testing | pytest, pytest-asyncio | latest | Unit + integration tests |
| Coverage | pytest-cov | latest | Coverage reports |
| CloudWatch | watchtower | >= 3.0 | Observability (logs + metrics) |

---

## API Endpoints

### Authentication
| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| POST | `/auth/token` | Get JWT token (testing) | No |
| GET | `/health` | Health check | No |

### Jobs (All require JWT)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/jobs` | Create new report job |
| GET | `/jobs` | List user's jobs (paginated) |
| GET | `/jobs/{job_id}` | Get job details |

### JWT Authentication
- Token in Authorization header: `Bearer <token>`
- Payload: `{ "sub": user_id, "exp": expiration, "iat": issued_at }`
- Algorithm: HS256
- Default expiration: 30 minutes

---

## AWS Configuration

### LocalStack (Development)
```python
AWS_ENDPOINT_URL = "http://localhost:4566"
AWS_REGION = "us-east-1"
AWS_ACCESS_KEY_ID = "test"
AWS_SECRET_ACCESS_KEY = "test"
```

### DynamoDB
- **Table Name:** `jobs`
- **Primary Key:** `job_id` (String, Partition Key)
- **GSI:** `user_id-created_at-index`
  - Partition Key: `user_id`
  - Sort Key: `created_at`

### SQS
- **Standard Queue Name:** `report-jobs-queue`
- **Priority Queue Name:** `report-jobs-priority`
- **DLQ Name:** `report-jobs-dlq`
- **Redrive Policy:** maxReceiveCount: 3

### Priority Queues (B1)
The system implements priority-based job routing:

| Report Type | Priority | Queue |
|-------------|----------|-------|
| `sales_report` | HIGH | `report-jobs-priority` |
| `financial_report` | HIGH | `report-jobs-priority` |
| Others | STANDARD | `report-jobs-queue` |

**Worker Priority Logic:**
1. Poll priority queue first (every 0.5s)
2. Process all priority messages before checking standard queue
3. Only poll standard queue when priority is empty
4. Delete messages from the correct queue based on priority

### CloudWatch
- **Log Group:** `/reto-prosperas/jobs`
- **Stream Name:** `worker`
- **Metrics Namespace:** `RetoProsperas`

---

## Observability

### CloudWatch Metrics

The system publishes the following custom metrics to CloudWatch:

| Metric | Type | Dimensions | Description |
|--------|------|------------|-------------|
| `JobsProcessed` | Count | ReportType | Successful job completions |
| `JobsFailed` | Count | ReportType | Failed job completions |
| `ProcessingDuration` | Seconds | ReportType | Time to process each job |
| `BatchTotal` | Count | - | Total jobs in batch |
| `BatchSuccessful` | Count | - | Successful jobs in batch |
| `BatchFailed` | Count | - | Failed jobs in batch |

### CloudWatch Logging

Structured JSON logs are sent to CloudWatch Logs via watchtower:

```python
from backend.src.shared.observability import setup_cloudwatch_logging

# Initialize at application startup
cw_handler = setup_cloudwatch_logging()

# Logs are automatically formatted as JSON with:
# - timestamp (ISO format)
# - log level
# - event data (job_id, report_type, etc.)
```

### Backwards Compatibility

CloudWatch integration is **optional** and backwards-compatible:
- If CloudWatch credentials are not configured, the worker continues normally
- All CloudWatch calls are wrapped in try/except blocks
- Metrics and logs are also stored locally in memory

---

## Testing

### Running Tests
```bash
# Run all tests
PYTHONPATH=.. pytest tests/ -v

# Run with coverage
PYTHONPATH=.. pytest tests/ --cov=src --cov-report=term-missing

# Run specific test module
PYTHONPATH=.. pytest tests/unit/domain/ -v
```

### Test Coverage Target
- Minimum 70% line coverage
- All endpoints covered
- Error paths covered
- Authentication covered

### Test Structure
```
tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── domain/             # Domain entity tests
│   ├── application/        # Use case tests
│   └── adapters/          # Adapter tests
└── integration/
    └── test_routes.py      # API integration tests
```

---

## Key Design Decisions

1. **Domain Independence**: The `Job` entity has no imports from outside the domain layer
2. **Ports as Protocols**: `JobRepository` and `JobQueue` are Protocol classes for easy mocking
3. **Factory Pattern**: Use cases accept dependencies via constructor for DI
4. **FastAPI Integration**: Routes only handle HTTP concerns, delegating to use cases
5. **Async/Await**: Repository operations are async, queue operations can be sync
6. **Value Objects**: `JobStatus` is an enum with state machine transitions

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_ENDPOINT_URL` | http://localhost:4566 | LocalStack endpoint |
| `AWS_REGION` | us-east-1 | AWS region |
| `AWS_ACCESS_KEY_ID` | test | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | test | AWS credentials |
| `DYNAMODB_TABLE_JOBS` | jobs | DynamoDB table name |
| `SQS_QUEUE_URL` | (local) | SQS queue URL |
| `JWT_SECRET_KEY` | (change in prod) | JWT signing key |
| `JWT_ALGORITHM` | HS256 | JWT algorithm |
| `CLOUDWATCH_LOG_GROUP` | /reto-prosperas/jobs | CloudWatch log group |
| `CLOUDWATCH_STREAM_NAME` | worker | CloudWatch stream name |

---

## References

- FastAPI Skill: `../../.agents/skills/fastapi-api-core/SKILL.md`
- AWS Data Modeling Skill: `../../.agents/skills/aws-data-modeling/SKILL.md`
- Root AGENTS.md: `../../AGENTS.md`
