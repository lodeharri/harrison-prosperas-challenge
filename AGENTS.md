# AGENTS.md - Project Root

## Project Overview

**Project Name:** Reto Prosperas - Report Job Processing System  
**Type:** Async Job Processing Platform  
**Core Functionality:** A FastAPI-based REST API that accepts report job requests, queues them via AWS SQS, processes them asynchronously with workers, and persists job state in AWS DynamoDB.

---

## Module Structure

```
harrison-prosperas-challenge/
├── docker-compose.yml        # Orchestrates all services
├── AGENTS.md                 # This file
├── PRD.md                    # Project requirements
├── backend/                  # FastAPI REST API + Worker
│   ├── src/                  # Hexagonal Architecture
│   │   ├── domain/           # Job entity, JobStatus, exceptions
│   │   ├── application/      # Use cases + ports (interfaces)
│   │   ├── adapters/         # DynamoDB, SQS, FastAPI routes
│   │   ├── config/           # Settings (Pydantic)
│   │   └── shared/           # JWT, exceptions, observability
│   ├── worker/               # Async SQS consumer
│   ├── init_db.py            # DynamoDB table creation
│   └── tests/                # Unit + integration tests
├── frontend/                  # React SPA (Vite + TypeScript)
│   ├── src/                  # Components, hooks, services
│   ├── Dockerfile            # Multi-stage (Node + Nginx)
│   └── nginx.conf            # SPA routing, WS proxy
└── .github/                  # CI/CD workflows
```

---

## Tech Stack

| Component | Technology | Skill Reference |
|-----------|------------|------------------|
| REST API | FastAPI, Pydantic v2, JWT | `fastapi-api-core` |
| Database | AWS DynamoDB | `aws-data-modeling` |
| Queue | AWS SQS (LocalStack) | `infra-local-bootstrap` |
| Workers | Python asyncio | (This module) |
| Infrastructure | Docker, LocalStack | `infra-local-bootstrap` |
| Observability | CloudWatch Logs + Metrics | `aws-observability-bootstrap` |
| CI/CD | GitHub Actions | `cicd-aws-production` |

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AWS_ENDPOINT_URL` | LocalStack endpoint | `http://localhost:4566` |
| `AWS_REGION` | AWS region | `us-east-1` |
| `AWS_ACCESS_KEY_ID` | AWS credentials | `test` |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials | `test` |
| `DYNAMODB_TABLE_JOBS` | Jobs table name | `jobs` |
| `SQS_QUEUE_URL` | Queue URL | Auto-generated |
| `JWT_SECRET_KEY` | JWT signing key | (Generate secure) |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `API_BASE_URL` | API base URL | `http://localhost:8000` |

---

## Task List

### Completed
- [x] Local Development (Docker, LocalStack, Zero-config startup)
- [x] REST API (all endpoints: POST/GET /jobs, JWT auth, health, CORS)
- [x] Persistence (DynamoDB with GSI on user_id)
- [x] Workers (async, DLQ, circuit breaker, exponential backoff)
- [x] Bonus: Priority queues, WebSocket, CloudWatch, Tests (92%), Idempotency

### Pending
- [ ] CI/CD Pipeline (GitHub Actions + AWS)
- [ ] AWS Production deployment

---

## Deployment Status

| Environment | Status |
|-------------|--------|
| Local (Docker) | ✅ Ready |
| AWS Production | ⏳ Pending |

---

## Bonus Challenges

| ID | Feature | Status |
|----|---------|--------|
| B1 | Priority queues (high/standard by report type) | ✅ |
| B3 | WebSocket notifications for real-time updates | ✅ |
| B5 | CloudWatch observability (structured logging + metrics) | ✅ |
| B6 | Test coverage ≥70% | ✅ (92%) |
| B7 | Idempotency & race condition handling | ✅ |

---

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| localstack | 4566 | SQS + DynamoDB emulation |
| app | 8000 | FastAPI REST API |
| worker | - | Async job processor (SQS consumer) |
| frontend | 3000 | React SPA (Vite build + Nginx) |

---

## Skills Reference

- `fastapi-api-core`: REST API implementation with JWT
- `aws-data-modeling`: DynamoDB schema and queries
- `infra-local-bootstrap`: Docker + LocalStack setup
- `aws-observability-bootstrap`: CloudWatch logging and metrics
- `cicd-aws-production`: GitHub Actions + AWS deployment

---

## Module AGENTS.md Files

Each module has its own detailed AGENTS.md:
- `backend/AGENTS.md`: API, Worker, DynamoDB, SQS, tests, observability
- `frontend/AGENTS.md`: React SPA, components, hooks, WebSocket integration

---

## Dependencies

```
backend ──────┬─────> infra (Docker, LocalStack)
              │
              └─────> worker (consumes SQS, updates DynamoDB)

.github ──────> infra (references for deployment)
```

**Execution Order:**
1. ~~Implement `infra/` (Docker setup)~~ ✅ DONE
2. ~~Implement `backend/` (API + data models)~~ ✅ DONE
3. ~~Implement `worker/` (job processor)~~ ✅ DONE
4. ~~Implement `.github/` (CI/CD)~~ ⏳ PENDING
