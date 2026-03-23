# SKILL.md - AI Agent Context Guide

**Purpose:** This document provides all necessary context for an AI agent to work on this codebase without reading individual files.

---

## 1. System Description

### What the System Does
**Reto Prosperas** is an async job processing platform that allows users to create report jobs via REST API. Jobs are queued in AWS SQS, processed asynchronously by workers, and status updates are delivered in real-time via WebSocket.

### Problem It Solves
- **Async Processing:** Long-running report generation doesn't block the API
- **Real-time Updates:** Users don't need to poll for job status
- **Reliability:** Circuit breaker, DLQ, and graceful shutdown ensure job completion
- **Scalability:** Serverless architecture scales with demand

### Core Flow
```
1. User POST /jobs → API stores in DynamoDB (PENDING) → SQS
2. Worker polls SQS → updates DynamoDB (PROCESSING)
3. Worker processes (5-30s) → updates DynamoDB (COMPLETED/FAILED)
4. Worker POST /internal/notify → WebSocket broadcasts to frontend
5. Frontend receives: {"type": "job_update", "data": {...}}
```

---

## 2. Repository Map

```
├── backend/                    # FastAPI REST API + Worker
│   ├── src/
│   │   ├── domain/             # Pure business logic (zero deps)
│   │   │   ├── entities/job.py           # Job entity
│   │   │   ├── value_objects/             # JobStatus enum
│   │   │   └── exceptions/                # Domain exceptions
│   │   ├── application/         # Use cases + ports
│   │   │   ├── ports/           # Interfaces (Protocol)
│   │   │   │   ├── job_repository.py     # Persistence port
│   │   │   │   └── job_queue.py          # Queue port
│   │   │   └── use_cases/      # Business orchestration
│   │   │       ├── create_job.py
│   │   │       ├── get_job.py
│   │   │       ├── list_jobs.py
│   │   │       └── update_job_status.py
│   │   ├── adapters/
│   │   │   ├── primary/fastapi/ # REST API
│   │   │   │   ├── main.py               # App entry
│   │   │   │   ├── routes/               # Endpoints
│   │   │   │   │   ├── jobs.py           # /jobs endpoints
│   │   │   │   │   ├── ws_routes.py      # /ws/jobs
│   │   │   │   │   └── notify.py         # /internal/notify
│   │   │   │   └── services/
│   │   │   │       └── websocket_manager.py
│   │   │   └── secondary/       # Infrastructure
│   │   │       ├── dynamodb/job_repository.py
│   │   │       └── sqs/job_queue.py
│   │   ├── config/settings.py  # Pydantic settings
│   │   └── shared/              # JWT, exceptions
│   ├── worker/                  # Async job processor
│   │   ├── main.py             # Entry + signal handlers
│   │   ├── processor.py        # Main processing logic
│   │   ├── circuit_breaker.py  # Failure isolation
│   │   ├── backoff.py          # Retry delays
│   │   ├── sqs_client.py      # SQS operations
│   │   └── dynamodb_client.py # DynamoDB operations
│   └── tests/                  # Unit tests
│
├── frontend/                   # React SPA
│   ├── src/
│   │   ├── components/         # UI components
│   │   ├── hooks/              # useAuth, useJobs, useWebSocket
│   │   ├── services/api.ts     # Axios client
│   │   └── pages/              # Login, Dashboard
│   └── Dockerfile              # Multi-stage build
│
├── infra/                     # AWS CDK
│   ├── app.py                 # CDK app entry
│   └── stacks/
│       ├── data_stack.py      # DynamoDB, SQS, VPC
│       ├── compute_stack.py   # ECS, ALB, IAM
│       ├── api_stack.py       # API Gateway
│       └── cdn_stack.py       # CloudFront, S3
│
├── local/                     # Docker Compose
│   └── docker-compose.yml    # LocalStack + API + Worker + Frontend
│
└── .github/workflows/
    ├── deploy.yml            # CD pipeline
    └── ci.yml                # CI pipeline
```

---

## 3. Project Patterns

### How to Add a New Route

**File:** `backend/src/adapters/primary/fastapi/routes/jobs.py`

```python
from fastapi import APIRouter, Depends

router = APIRouter()

@router.get("/new-endpoint")
async def new_endpoint(
    # Dependencies for auth, DI
    current_user: dict = Depends(get_current_user),
):
    # Business logic
    return {"data": "result"}
```

Then register in `main.py`:
```python
from .routes import jobs, ws_routes, notify

app.include_router(jobs.router, prefix="/jobs")
```

### How to Publish to SQS Queue

**File:** `backend/src/adapters/secondary/sqs/job_queue.py`

```python
import aiobotocore.session

class SQSJobQueue:
    def __init__(self, queue_url: str):
        self.queue_url = queue_url
        self.session = aiobotocore.session.get_session()
    
    async def publish(self, job: Job) -> bool:
        async with self.session.create_client('sqs') as client:
            await client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=job.model_dump_json()
            )
        return True
```

**Priority Queue (for high-priority reports like sales_report):**
```python
async def publish_priority(self, job: Job) -> bool:
    # Uses SQS_PRIORITY_QUEUE_URL
```

### How to Read Job State from DynamoDB

**File:** `backend/src/adapters/secondary/dynamodb/job_repository.py`

```python
import aiobotocore.session

class DynamoDBJobRepository:
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.session = aiobotocore.session.get_session()
    
    async def get_by_id(self, job_id: str) -> Job | None:
        async with self.session.create_client('dynamodb') as client:
            response = await client.get_item(
                TableName=self.table_name,
                Key={'job_id': {'S': job_id}}
            )
            item = response.get('Item')
            if not item:
                return None
            return self._item_to_job(item)
    
    async def list_by_user(self, user_id: str, page: int = 1, page_size: int = 20) -> tuple[list[Job], int]:
        # Uses GSI: user_id-created_at-index
```

### How Worker Processes Jobs

**File:** `backend/worker/processor.py`

```python
class JobProcessor:
    async def process(self, job: Job) -> Job:
        # 1. Update to PROCESSING
        job = await self.repo.update_status_with_version(job_id, JobStatus.PROCESSING)
        
        # 2. Simulate report generation (5-30s)
        await asyncio.sleep(random.uniform(5, 30))
        
        # 3. Update to COMPLETED or FAILED
        status = JobStatus.COMPLETED if random.random() > 0.1 else JobStatus.FAILED
        job = await self.repo.update_status_with_version(job_id, status)
        
        # 4. Notify API for WebSocket broadcast
        await self.http_client.notify(job)
        
        return job
```

### How WebSocket Broadcast Works

**File:** `backend/src/services/websocket_manager.py`

```python
class WebSocketManager:
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)
```

**Message format:**
```json
{"type": "job_update", "data": {"job_id": "...", "status": "PROCESSING", "updated_at": "..."}}
```

---

## 4. Frequent Commands

### Start Local Environment
```bash
cd /local && docker compose up -d
# Services: LocalStack (4566), API (8000), Worker, Frontend (3000)
```

### Run Tests
```bash
cd backend && pytest tests/ -v --cov=src --cov=worker
```

### Manual Deploy to AWS
```bash
cd infra
npm install
cdk bootstrap aws://ACCOUNT/REGION
cdk deploy --all --require-approval never
```

### View Logs
```bash
# API (CloudWatch)
aws logs tail /reto-prosperas/api --follow

# Worker (CloudWatch)
aws logs tail /reto-prosperas/worker --follow

# Local
docker compose -f local/docker-compose.yml logs -f app
```

### Health Check
```bash
# Local
curl http://localhost:8000/health

# Production
curl https://<api-gw>.amazonaws.com/prod/health
```

---

## 5. Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `ValidationError` on job creation | Missing required field in request | Check Pydantic schema in `jobs.py` |
| WebSocket connection fails | Invalid token or user_id | Ensure token is valid JWT with `sub=user_id` |
| Worker not picking up jobs | SQS visibility timeout too short | Increase `VISIBILITY_TIMEOUT` in worker config |
| Jobs going to DLQ | 3 failures on processing | Check worker logs, fix circuit breaker |
| Rate limit exceeded (429) | >100 req/sec | Wait and retry, check API key |
| LocalStack not ready | Container not healthy | Wait 30s after `docker compose up -d` |
| JWT token expired | >30 min since creation | Re-authenticate via `/auth/token` |
| DynamoDB conditional write failed | Version conflict (optimistic locking) | Retry with new version from DB |

---

## 6. How to Extend: Add New Report Type

### Step 1: Add Report Type to Enum (if needed)
**File:** `backend/src/domain/value_objects/job_status.py`

```python
class ReportType(str, Enum):
    SALES_REPORT = "sales_report"
    FINANCIAL_REPORT = "financial_report"
    NEW_REPORT_TYPE = "new_report_type"  # Add here
```

### Step 2: Update Frontend Form
**File:** `frontend/src/components/jobs/JobForm.tsx`

```typescript
<select name="report_type">
  <option value="sales_report">Sales Report</option>
  <option value="financial_report">Financial Report</option>
  <option value="new_report_type">New Report Type</option>  // Add here
</select>
```

### Step 3: Add Processing Logic (if special handling needed)
**File:** `backend/worker/processor.py`

```python
async def _generate_report(self, job: Job) -> str:
    if job.report_type == "new_report_type":
        # Special handling
        return await self._handle_new_type(job)
    else:
        # Default: random result URL
        return f"https://storage.example.com/{job.job_id}.pdf"
```

### Step 4: Add to Priority Queue (if high priority)
**File:** `backend/worker/processor.py`

```python
PRIORITY_REPORT_TYPES = {"sales_report", "financial_report", "new_report_type"}

async def _publish_to_queue(self, job: Job):
    if job.report_type in self.PRIORITY_REPORT_TYPES:
        await self.priority_queue.publish(job)
    else:
        await self.main_queue.publish(job)
```

### Step 5: Add Tests
```bash
cd backend
pytest worker/tests/test_processor.py -k "new_report_type" -v
```

---

## 7. Key Environment Variables

| Variable | Where Used | Description |
|----------|-----------|-------------|
| `AWS_ENDPOINT_URL` | Backend | LocalStack URL (dev only) |
| `DYNAMODB_TABLE_JOBS` | Backend | Jobs table name |
| `SQS_QUEUE_URL` | Backend | Main queue URL |
| `JWT_SECRET_KEY` | Backend | Token signing key |
| `API_BASE_URL` | Worker | For `/internal/notify` calls |
| `VITE_API_URL` | Frontend | Built at compile time |
| `VITE_WS_URL` | Frontend | Built at compile time |

---

## 8. Architecture: Hexagonal

```
DOMAIN (pure, no deps)
    ↓
APPLICATION (use cases + ports)
    ↓
ADAPTERS (primary: FastAPI routes; secondary: DynamoDB, SQS)
```

**Rule:** Domain never imports from adapters. Dependencies flow inward.

---

This document enables AI agents to operate on the codebase without reading individual files. Use it as the primary context when working on this project.
