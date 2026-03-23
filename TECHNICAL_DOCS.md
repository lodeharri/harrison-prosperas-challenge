# Technical Documentation

---

## Table of Contents
1. [CDK Stacks](#cdk-stacks)
2. [Deployment Pipeline](#deployment-pipeline)
3. [Architecture Decisions](#architecture-decisions)
4. [Environment Variables](#environment-variables)

---

## CDK Stacks

The infrastructure is deployed using AWS CDK v2 with 4 CloudFormation stacks. Each stack creates a specific layer of the architecture.

### Stack Dependency Order
```
harrison-data-stack (foundational)
        ↓
harrison-compute-stack (uses data stack)
        ↓
harrison-api-stack (uses compute stack)
        ↓
harrison-cdn-stack (uses api stack for URLs)
```

---

### 1. Data Stack (`harrison-data-stack`)

**Purpose:** Creates foundational data layer - DynamoDB tables, SQS queues, VPC, and ECS Cluster.

**AWS Resources Created:**

| Resource | Name | Type | Configuration |
|----------|------|------|----------------|
| VPC | `harrison-vpc` | VPC | 2 AZs, public subnets |
| ECS Cluster | `harrison-cluster` | ECS Fargate Cluster | - |
| DynamoDB Table | `harrison-jobs` | Partition Key: `job_id` | GSI: user_id-created_at, status-created_at |
| DynamoDB Table | `harrison-idempotency` | Partition Key: `idempotency_key` | TTL: expires_at (24h) |
| SQS Queue | `harrison-jobs-queue` | Main queue | 60s visibility, 1-day retention, DLQ after 3 failures |
| SQS Queue | `harrison-jobs-dlq` | Dead Letter Queue | 14-day retention |
| SQS Queue | `harrison-jobs-priority` | Priority queue | 30s visibility, high-priority jobs |

**Outputs:**
- `JobsTableName`, `JobsTableArn`
- `IdempotencyTableName`, `IdempotencyTableArn`
- `JobQueueUrl`, `JobQueueArn`
- `PriorityQueueUrl`, `PriorityQueueArn`
- `ECSClusterName`, `VPCId`

---

### 2. Compute Stack (`harrison-compute-stack`)

**Purpose:** Creates compute infrastructure - ECR repositories, ECS Fargate services, IAM roles, Secrets Manager.

**AWS Resources Created:**

| Resource | Name | Type | Configuration |
|----------|------|------|----------------|
| ECR Repository | `harrison-prospera-challenge` | Docker registry | Scan on push, lifecycle policy |
| Secrets Manager | `harrison-jwt-secret` | Secret | 64-char auto-generated key |
| IAM Role | `APIServiceRole` | ECS Task Role | DynamoDB + SQS + Secrets + Logs |
| IAM Role | `WorkerServiceRole` | ECS Task Role | DynamoDB + SQS + Logs + CloudWatch |
| ECS Service | `harrison-api` | Fargate | 0.5 vCPU, 1GB, ALB-enabled, port 8000 |
| ECS Service | `harrison-worker` | Fargate | 0.25 vCPU, 512MB, SQS consumer |
| ALB | (auto-created) | Application LB | Public, ports 80/8000, health check /health |

**Service Configuration:**
- **API Service**: CPU 512, Memory 1024MB, desired count 1, health check on `/health`
- **Worker Service**: CPU 256, Memory 512MB, desired count 1, command: `python -m backend.worker.main`

**Outputs:**
- `ECRRepositoryUri`, `ECRRepositoryName`
- `APIServiceUrl` (ALB DNS: `http://<alb-dns>:8000`)
- `APIRoleArn`, `WorkerRoleArn`

---

### 3. API Stack (`harrison-api-stack`)

**Purpose:** Creates REST API Gateway with rate limiting and API keys.

**AWS Resources Created:**

| Resource | Name | Type | Configuration |
|----------|------|------|----------------|
| API Gateway | `harrison-api-gw` | REST API | Regional endpoint |
| Resource | `/auth/token` | POST | Token generation (no auth) |
| Resource | `/jobs` | GET, POST | List/Create jobs (API key required) |
| Resource | `/jobs/{job_id}` | GET | Get job details (API key required) |
| Resource | `/health` | GET | Health check (no auth) |
| Usage Plan | `harrison-rate-limit` | Throttle | 100 req/sec, burst 200, 10k/month |
| API Key | `harrison-api-key` | Key | `harrison-api-key` |

**Rate Limiting:**
- Rate Limit: 100 requests/second
- Burst Limit: 200 requests
- Monthly Quota: 10,000 requests/month

**API Integration:**
- All endpoints (except `/health`) integrate with ECS Fargate ALB
- JWT validation happens in FastAPI backend (not API Gateway)
- CORS handled via mock OPTIONS responses

**Outputs:**
- `APIUrl` (e.g., `https://<api-id>.execute-api.us-east-1.amazonaws.com/prod`)
- `APIKeyId`

---

### 4. CDN Stack (`harrison-cdn-stack`)

**Purpose:** Creates frontend hosting infrastructure - S3 bucket, CloudFront distribution.

**AWS Resources Created:**

| Resource | Name | Type | Configuration |
|----------|------|------|----------------|
| S3 Bucket | `harrison-frontend` | Bucket | Static hosting, versioning, OAI-protected |
| OAI | (auto-created) | Origin Access Identity | S3 access control |
| CloudFront | `harrison-frontend-cdn` | Distribution | Price class 100 (NA+EU), HTTP→HTTPS redirect |
| CloudFront Function | `harrison-spa-routing` | Function | SPA routing for /index.html fallback |

**Cache Behavior:**
- **Default**: S3 origin, 1-day TTL, cache static assets
- **Path Pattern `/ws/*`**: ALB origin, caching disabled, WebSocket support

**Outputs:**
- `FrontendUrl` (e.g., `https://<cloudfront-id>.cloudfront.net`)
- `FrontendBucketName`
- `DistributionId`
- `WssUrl` (e.g., `wss://<cloudfront-id>.cloudfront.net`)

---

## Deployment Pipeline

### GitHub Actions Workflow: `deploy.yml`

The pipeline runs on push to `master` branch. Here's the step-by-step flow:

```
┌─────────────────┐
│   build-ecr     │ ─── Build & push Docker image to ECR
└────────┬────────┘
         │ image-tag, ecr-registry
         ▼
┌─────────────────┐
│  validate-cdk   │ ─── Synthesize CDK templates (validation)
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────────────────┐    ┌─────────────────┐
│   deploy-cdk   │    │ build-frontend  │ ← Gets API URLs from CDK outputs
│  Deploys all   │    │  Build React    │
│  CDK stacks    │    │  with VITE_     │
└────────┬────────┘    └────────┬────────┘
         │                     │
         └─────────┬───────────┘
                   ▼
         ┌─────────────────┐
         │ deploy-frontend │ ─── Upload to S3, invalidate CloudFront
         └────────┬────────┘
                  ▼
         ┌─────────────────┐
         │     verify     │ ─── Health check + smoke test
         └─────────────────┘
```

### Detailed Job Steps

#### 1. `build-ecr` (runs in parallel with `validate-cdk`)
- Checkout code
- Configure AWS credentials
- Login to ECR
- Create ECR repository (if not exists)
- Build Docker image from `backend/`
- Push with tags: `latest`, `<sha>`, `<timestamp>-<sha>`

#### 2. `validate-cdk`
- Checkout code
- Setup Python 3.11 + Node.js 20
- Install CDK dependencies
- Run `cdk synth --all` to validate templates

#### 3. `deploy-cdk` (runs after `build-ecr` + `validate-cdk`)
- Bootstrap CDK (if `CDK_BOOTSTRAPPED` variable is not `true`)
- Deploy all stacks: `cdk deploy --all --require-approval never`
- Pass `imageTag` as CDK context variable
- CloudFormation creates/updates:
  - Data stack (DynamoDB, SQS, VPC, ECS)
  - Compute stack (ECR, ECS services, ALB, IAM)
  - API stack (API Gateway, rate limiting)
  - CDN stack (S3, CloudFront)

#### 4. `build-frontend` (runs after `deploy-cdk`)
- Get deployed URLs from CloudFormation:
  - `APIUrl` from API stack
  - `WssUrl` from CDN stack
- Set environment variables:
  - `VITE_API_URL` = API Gateway URL
  - `VITE_WS_URL` = CloudFront WSS URL
- Run `npm run build`
- Upload `dist/` as artifact

#### 5. `deploy-frontend` (runs after `build-frontend` + `deploy-cdk`)
- Download frontend artifact
- Sync to S3 bucket: `aws s3 sync ./dist s3://harrison-frontend/`
- Get CloudFront distribution ID
- Invalidate cache: `aws cloudfront create-invalidation --paths "/*"`

#### 6. `verify` (runs after `deploy-cdk` + `deploy-frontend`)
- Wait 30s for stabilization
- Health check: `GET <API_URL>/health`
- Smoke test: POST to `/auth/token` to verify JWT auth
- Output deployment summary with URLs

### GitHub Secrets Required

| Secret | Purpose |
|--------|---------|
| `AWS_ACCESS_KEY_ID` | AWS credentials for all AWS operations |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials for all AWS operations |
| `AWS_ACCOUNT_ID` | AWS account ID for CDK bootstrap |
| `JWT_SECRET_KEY` | JWT signing key (passed to CDK as environment variable) |

### GitHub Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CDK_BOOTSTRAPPED` | `false` | Skip bootstrap after first run |
| `AWS_REGION` | `us-east-1` | AWS region |
| `STACK_PREFIX` | `harrison` | Resource name prefix |
| `ECR_REPOSITORY` | `harrison-prospera-challenge` | ECR repo name |

---

## Architecture Decisions

### Why ECS Fargate vs Lambda?

**Decision:** Both API and Worker run on ECS Fargate (not Lambda).

**Reasons:**

1. **WebSocket Connections**: The Worker maintains persistent WebSocket connections to broadcast job updates. Lambda has execution time limits (15 min max) and is not suitable for long-running connections.

2. **SQS Long Polling**: The Worker performs long-polling on SQS queues (60s receive timeout). Lambda's model is event-driven and doesn't support this pattern efficiently.

3. **Consistency**: Using the same compute platform (ECS) for both API and Worker simplifies:
   - Networking (both in same VPC/ALB)
   - IAM permissions (shared role structure)
   - Docker images (single Dockerfile)
   - Deployment strategy

4. **Cost Efficiency**: For this workload:
   - Worker runs continuously (not bursty)
   - API needs persistent capacity for WebSocket
   - Lambda's pay-per-invocation model doesn't save money here

**When Lambda would be better:** If jobs were short (< 3 min), bursty, and didn't require persistent connections.

---

### Why CloudFront + ALB for WebSocket (not API Gateway)?

**Decision:** Frontend WebSocket connects to CloudFront → ALB (not API Gateway).

**Reason:** **API Gateway does not support WebSocket connections.**

The architecture:
```
Frontend (browser)
    │
    │ wss://<cloudfront>.cloudfront.net/ws/jobs?user_id=...
    ▼
CloudFront Distribution
    │ (cache behavior /ws/* with caching disabled)
    ▼
ALB (port 8000)
    ▼
ECS Fargate (API container with WebSocket endpoint)
```

**Why this works:**

1. **CloudFront WebSocket Support**: CloudFront can proxy WebSocket traffic if:
   - Cache is disabled for `/ws/*` path
   - Origin protocol is HTTP (WebSocket upgrade happens at ALB)
   - Allowed methods include WebSocket

2. **ALB on port 8000**: FastAPI listens on 8000 (not 80). CDK creates:
   - Default listener on port 80 (HTTP)
   - Additional listener on port 8000 (WebSocket)

3. **Worker can notify API**: The Worker uses `API_BASE_URL` (ALB DNS) to POST to `/internal/notify` when jobs complete. This triggers WebSocket broadcasts.

**Alternative considered:**
- API Gateway WebSocket API (AWS WebSocket API) - requires different routing logic, more complex setup
- Direct ALB access (bypassing CloudFront) - works but loses CloudFront's global edge network

---

### Why DynamoDB with GSIs?

**Decision:** Jobs table has two GSIs (user_id + status).

**Reason:**
- **Primary access pattern**: Query jobs by `user_id` (user's job list)
- **Secondary access pattern**: Filter jobs by `status` (e.g., all "processing" jobs)
- On-demand billing fits variable workload

---

### Why SQS with DLQ?

**Decision:** Main queue has dead-letter queue after 3 failed receives.

**Reason:**
- Jobs can fail due to: invalid input, timeout, transient errors
- DLQ captures failed messages for debugging/retry
- 14-day retention gives time to investigate

---

## Environment Variables

### CDK-Set Variables (Automatic)

These are injected by CDK into ECS Fargate containers:

#### API Service Environment

| Variable | Source | Example |
|----------|--------|---------|
| `AWS_REGION` | CDK | `us-east-1` |
| `AWS_ENDPOINT_URL` | (empty in prod) | `` (empty) |
| `DYNAMODB_TABLE_JOBS` | Data Stack | `harrison-jobs` |
| `DYNAMODB_TABLE_IDEMPOTENCY` | Data Stack | `harrison-idempotency` |
| `SQS_QUEUE_URL` | Data Stack | `https://sqs.us-east-1.amazonaws.com/ACCOUNT/harrison-jobs-queue` |
| `SQS_QUEUE_NAME` | Data Stack | `harrison-jobs-queue` |
| `SQS_DLQ_URL` | Data Stack | `https://sqs.us-east-1.amazonaws.com/ACCOUNT/harrison-jobs-dlq` |
| `SQS_DLQ_NAME` | Data Stack | `harrison-jobs-dlq` |
| `SQS_PRIORITY_QUEUE_URL` | Data Stack | `https://sqs.us-east-1.amazonaws.com/ACCOUNT/harrison-jobs-priority` |
| `SQS_PRIORITY_QUEUE_NAME` | Data Stack | `harrison-jobs-priority` |
| `LOG_LEVEL` | CDK | `INFO` |

#### Worker Service Environment

Same as API +:

| Variable | Source | Example |
|----------|--------|---------|
| `API_BASE_URL` | Compute Stack | `http://<alb-dns>:8000` |

The Worker uses `API_BASE_URL` to call the API's `/internal/notify` endpoint when jobs complete, triggering WebSocket broadcasts.

---

### User-Provided Secrets

| Secret | Purpose | How Provided |
|--------|---------|--------------|
| `JWT_SECRET_KEY` | JWT signing key | GitHub secret → CDK context → Secrets Manager → ECS env |

**Flow:**
1. GitHub workflow passes `JWT_SECRET_KEY` as environment variable
2. CDK creates/updates Secrets Manager secret `harrison-jwt-secret`
3. ECS task role has permission to read the secret
4. Application reads secret at startup (injected as environment variable by CDK)

---

### Frontend Build Variables

These are set at build time (not runtime):

| Variable | Source | Example |
|----------|--------|---------|
| `VITE_API_URL` | GitHub workflow (from CDK output) | `https://<api-id>.execute-api.us-east-1.amazonaws.com/prod` |
| `VITE_WS_URL` | GitHub workflow (from CDK output) | `wss://<cloudfront-id>.cloudfront.net` |

These are baked into the frontend at build time via Vite's environment variable replacement.

---

### Local Development Variables

For LocalStack development:

| Variable | Value | Purpose |
|----------|-------|---------|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | Points to LocalStack |
| `LOCALSTACK` | `true` | Enables local mode in code |

---

## Summary

| Component | Technology | Notes |
|-----------|------------|-------|
| Compute | ECS Fargate | API + Worker on same platform |
| Database | DynamoDB | Jobs table with GSIs, Idempotency table with TTL |
| Queue | SQS | Main queue + priority queue + DLQ |
| API Layer | API Gateway | REST API with rate limiting |
| CDN | CloudFront + S3 | Static hosting, WebSocket proxy |
| WebSocket | CloudFront → ALB | API Gateway doesn't support WebSocket |
| CI/CD | GitHub Actions | ECR → CDK → S3 → Verify |
| Secrets | Secrets Manager | JWT signing key |
| IAM | Task Roles | Least-privilege per service |
---

## 5. Local Setup Guide

### Prerequisites

- Docker
- Docker Compose

### Steps to Start Local Environment

```bash
# 1. Navigate to the project root
cd /harrison-prosperas-challenge

# 2. Start all services with Docker Compose
docker compose -f local/docker-compose.yml up -d

# 3. Wait for services to be healthy (LocalStack takes ~30s to initialize)
docker compose -f local/docker-compose.yml ps

# 4. Verify services are running
# LocalStack: http://localhost:4566
# API:        http://localhost:8000
# Frontend:   http://localhost:3000

# 5. Run health check
curl http://localhost:8000/health
```

### Services Started

| Service | Port | Description |
|---------|------|-------------|
| `localstack` | 4566 | AWS emulator (SQS, DynamoDB, S3) |
| `app` (API) | 8000 | FastAPI REST API |
| `worker` | - | Async job processor |
| `frontend` | 3000 | React SPA with Nginx |

### Verify Local Setup

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Login (get token)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user"}' | jq -r '.access_token')

# 3. Create a job
curl -X POST http://localhost:8000/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "sales_report", "date_range": "last_7_days", "format": "pdf"}'

# 4. List jobs
curl -X GET http://localhost:8000/jobs \
  -H "Authorization: Bearer $TOKEN"
```

### Stop Services

```bash
docker compose -f local/docker-compose.yml down
```

---

## 6. Test Suite

### Running Tests

```bash
# Navigate to backend directory
cd backend

# Run all tests with coverage
pytest tests/ -v --cov=src --cov=worker

# Run specific test categories
pytest tests/unit/ -v           # Unit tests only
pytest tests/test_auth.py -v    # Auth tests
```

### Test Coverage by Suite

| Test File | Coverage Area | What It Tests |
|-----------|---------------|---------------|
| `tests/unit/domain/test_job.py` | Domain layer | Job entity, JobStatus enum, domain exceptions |
| `tests/unit/application/test_use_cases.py` | Application layer | CreateJob, GetJob, ListJobs, UpdateJobStatus use cases |
| `tests/unit/adapters/test_job_repository.py` | DynamoDB adapter | CRUD operations, conditional writes, GSI queries |
| `tests/unit/adapters/test_job_queue.py` | SQS adapter | Publish to main/priority queues |
| `tests/unit/adapters/test_main.py` | FastAPI app | App initialization, health endpoint |
| `tests/unit/adapters/test_dependencies.py` | DI | Dependency injection setup |
| `tests/unit/adapters/test_ws_routes.py` | WebSocket routes | WS connection/disconnection |
| `tests/unit/adapters/test_websocket_manager.py` | WS Manager | Connection registry, broadcast |
| `tests/unit/adapters/test_notify.py` | Internal notify | Worker notification endpoint |
| `tests/test_auth.py` | Authentication | JWT token generation and validation |
| `tests/test_schemas.py` | Pydantic schemas | Request/response validation |
| `worker/tests/test_processor.py` | Worker processor | Job processing, graceful shutdown |
| `worker/tests/test_circuit_breaker.py` | Circuit breaker | CLOSED → OPEN → HALF_OPEN states |
| `worker/tests/test_backoff.py` | Exponential backoff | Delay calculations with jitter |

### Test Coverage Summary

- **Domain**: Pure business logic (no external dependencies)
- **Application**: Use cases with mocked ports
- **Adapters**: HTTP/DynamoDB/SQS implementations with mocked AWS
- **Integration**: Full stack tests with LocalStack (future)
- **Worker**: Async processor, circuit breaker, backoff patterns

Target: ≥92% coverage on business logic
