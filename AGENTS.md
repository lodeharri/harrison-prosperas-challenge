# AGENTS.md - Project Root

## Project Overview

**Project Name:** Reto Prosperas - Report Job Processing System  
**Type:** Async Job Processing Platform  
**Core Functionality:** A FastAPI-based REST API that accepts report job requests, queues them via AWS SQS, processes them asynchronously with workers, and persists job state in AWS DynamoDB.

---

## Module Structure

```
harrison-prosperas-challenge/
├── docker-compose.yml           # Orchestrates all services (app + worker + localstack)
├── .gitignore                    # Git ignore (excludes .env files)
├── AGENTS.md                    # This file
├── PRD.md                       # Project requirements
├── backend/                      # FastAPI REST API + Worker
│   ├── Dockerfile               # Multi-stage Python 3.11 build
│   ├── .env                     # Environment variables (NEVER commit)
│   ├── .env.example             # Template for .env
│   ├── requirements.txt         # Python dependencies
│   ├── src/                     # 🏛️ Hexagonal Architecture
│   │   ├── domain/             # Core business logic (no external deps)
│   │   │   ├── entities/       # Job entity with business rules
│   │   │   ├── value_objects/  # JobStatus enum, state machine
│   │   │   └── exceptions/    # Domain-specific exceptions
│   │   ├── application/        # Use cases + ports (interfaces)
│   │   │   ├── ports/          # JobRepository, JobQueue protocols
│   │   │   └── use_cases/      # CreateJob, GetJob, ListJobs, UpdateJobStatus
│   │   ├── adapters/          # Infrastructure implementations
│   │   │   ├── primary/fastapi/  # REST endpoints, routes
│   │   │   └── secondary/      # DynamoDB, SQS implementations
│   │   ├── config/            # Settings (Pydantic)
│   │   └── shared/            # JWT, exceptions, dependencies
│   ├── worker/                # Async job processor (SQS consumer)
│   ├── init_db.py             # DynamoDB table initialization
│   └── tests/                  # Unit + integration tests (>=70% coverage)
├── infra/                      # Docker + LocalStack configuration
├── .github/                   # CI/CD workflows
└── frontend/                  # (Future: Web UI)
```

### Architecture: Hexagonal (Ports & Adapters)

```
┌─────────────────────────────────────────────────────────────────┐
│                        DRIVING ADAPTERS                         │
│  ┌─────────────────┐    ┌─────────────────────────────────┐   │
│  │   FastAPI        │    │   Worker (SQS Consumer)          │   │
│  │   REST Routes    │    │   Async Job Processor            │   │
│  └────────┬────────┘    └──────────────┬──────────────────┘   │
│           │                            │                        │
└───────────┼────────────────────────────┼────────────────────────┘
            │                            │
            ▼                            ▼
┌───────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                            │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                        USE CASES                             │  │
│  │  CreateJob  │  GetJob  │  ListJobs  │  UpdateJobStatus       │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│  ┌───────────────────────────┴───────────────────────────────┐    │
│  │                        PORTS (Interfaces)                  │    │
│  │              JobRepository         JobQueue               │    │
│  └───────────────────────────┬───────────────────────────────┘    │
└──────────────────────────────┼────────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│                      DRIVEN ADAPTERS                              │
│  ┌─────────────────┐                           ┌───────────────┐ │
│  │    DynamoDB     │                           │      SQS      │ │
│  │   Repository    │                           │    Publisher  │ │
│  └─────────────────┘                           └───────────────┘ │
└───────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│                        DOMAIN (Pure Core)                         │
│  ┌─────────────┐  ┌────────────────┐  ┌────────────────────────┐  │
│  │  Job Entity │  │  JobStatus VO  │  │  Domain Exceptions     │  │
│  │  (no deps!) │  │  (state flow)  │  │  (JobNotFound, etc)    │  │
│  └─────────────┘  └────────────────┘  └────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

#### Dependency Rule
```
Domain (innermost) ──► Application ──► Adapters
(no dependencies)     (ports only)    (implements ports)
```

#### SOLID Principles
| Letter | Principle | Application in this Project |
|--------|-----------|------------------------------|
| **S** | Single Responsibility | Each use case does one thing; entities encapsulate business logic |
| **O** | Open/Closed | Add new adapters without modifying domain/application |
| **L** | Liskov Substitution | Any `JobRepository` implementation works interchangeably |
| **I** | Interface Segregation | Small, focused ports (`JobRepository`, `JobQueue`) |
| **D** | Dependency Inversion | Domain depends on abstractions, not implementations |

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
| `AWS_ACCESS_KEY_ID` | AWS credentials | `test` (local) |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials | `test` (local) |
| `DYNAMODB_TABLE_JOBS` | Jobs table name | `jobs` |
| `SQS_QUEUE_URL` | Queue URL | Auto-generated |
| `JWT_SECRET_KEY` | JWT signing key | (Generate secure) |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `CLOUDWATCH_LOG_GROUP` | CloudWatch log group | `/reto-prosperas/jobs` |
| `CLOUDWATCH_STREAM_NAME` | CloudWatch stream name | `worker` |

---

## Task List (from PRD.md)

### Local Development Environment
- [x] **Dockerfile:** Create optimized Python 3.11 Dockerfile for backend
- [x] **docker-compose.yml:** Integrate LocalStack for SQS + DynamoDB emulation
- [x] **Zero-Config Startup:** `docker compose up` must start everything
- [x] **.env.example:** Document all required environment variables
- [x] **Docker Fixes:** Corrected PYTHONPATH (`/app/backend`) and worker module path (`backend.worker.main`)

### REST API (Backend)
- [x] **POST /jobs:** Create job, publish to SQS, return `{ job_id, status: PENDING }`
- [x] **GET /jobs/{job_id}:** Return job status and result_url (if completed)
- [x] **GET /jobs:** List jobs for authenticated user, paginated (min 20/page)
- [x] **JWT Authentication:** Stateless JWT (HS256) for all `/jobs` endpoints
- [x] **Error Handling:** Global exception handlers, no scattered try/except
- [x] **Health Endpoint:** `GET /health` reporting dependency status

### Persistence (DynamoDB)
- [x] **Data Model:** `job_id`, `user_id`, `status`, `report_type`, `created_at`, `updated_at`, `result_url`
- [x] **GSI on user_id:** Efficient queries for `GET /jobs`
- [x] **init_db.py:** Script to create tables from scratch

### Workers
- [x] **Async Processing:** Use `asyncio.gather` for 2+ concurrent jobs
- [x] **Simulated Processing:** Random sleep 5-30 seconds + dummy data
- [x] **Status Updates:** Transition `PENDING` -> `PROCESSING` -> `COMPLETED`/`FAILED`
- [x] **Dead Letter Queue:** Handle failed messages without blocking
- [x] **Circuit Breaker:** (Bonus) Pause report type after N failures
- [x] **Exponential Back-off:** (Bonus) Retry with increasing delays

### Senior Bonus Challenges
- [x] **B1:** Priority queues (high/standard priority by report type)
- [x] **B5:** Observability - structured logging + metrics (CloudWatch integration)
- [x] **B6:** >= 70% test coverage with pytest

### CI/CD Pipeline
> **Note:** CI/CD and AWS deployment can be configured later using the `cicd-aws-production` skill.

- [ ] **GitHub Actions Workflow:** Auto-deploy on push to `main` (PENDING)
- [ ] **AWS Deployment:** App accessible via public URL (PENDING)
- [ ] **Cost Optimization:** Target < $10 USD/month (PENDING)
- [ ] **Reviewer IAM:** AdminAccess user for reviewers (PENDING)

---

## Deployment Status

| Environment | Status | Notes |
|-------------|--------|-------|
| Local (Docker) | ✅ VERIFIED (2026-03-18) | All services healthy, job flow tested end-to-end |
| AWS Production | ⏳ PENDING | Can be configured later via `cicd-aws-production` skill |

---

## Bonus Challenges Implementation Details

### B1: Priority Queues ✅
**Archivo:** `backend/src/adapters/secondary/sqs/job_queue.py`

Implementa enrutamiento de trabajos por prioridad basado en el tipo de reporte:

| Tipo de Reporte | Prioridad | Cola SQS |
|-----------------|-----------|----------|
| `sales_report` | HIGH | `report-jobs-priority` |
| `financial_report` | HIGH | `report-jobs-priority` |
| Otros | STANDARD | `report-jobs-queue` |

**Lógica del Worker:**
1. Sondea la cola prioritaria cada 0.5 segundos
2. Procesa todos los mensajes de prioridad antes de verificar la cola estándar
3. Solo consulta la cola estándar cuando la prioritaria está vacía
4. Elimina mensajes de la cola correcta según la prioridad

### B5: Observability - CloudWatch ✅
**Archivos:**
- `backend/src/shared/observability.py` - Métricas y logging
- `backend/src/config/settings.py` - Configuración de CloudWatch

**Métricas CloudWatch (Namespace: `RetoProsperas`):**
| Métrica | Tipo | Dimensiones |
|---------|------|-------------|
| `JobsProcessed` | Count | ReportType |
| `JobsFailed` | Count | ReportType |
| `ProcessingDuration` | Seconds | ReportType |
| `BatchTotal` | Count | - |
| `BatchSuccessful` | Count | - |
| `BatchFailed` | Count | - |

**Logging Estructurado:**
- Logs JSON con timestamp ISO, nivel, y datos de evento
- Integración con CloudWatch Logs vía `watchtower`
- Retrocompatibilidad: si CloudWatch no está disponible, continúa normalmente

### B6: Test Coverage ✅
- **43 tests implementados** covering:
  - Unit tests: Domain, Application, Adapters
  - Auth: JWT creation and verification
  - Schemas: Pydantic validation
- **Cobertura objetivo:** >= 70% (verificable con `pytest --cov`)

---

## Project Completion Summary

### ✅ All Local Development Tasks Completed
- **Infrastructure:** Docker, LocalStack (SQS + DynamoDB emulation)
- **REST API:** FastAPI with JWT authentication, all endpoints implemented
- **Workers:** Async processing with priority queues, DLQ, circuit breaker, exponential backoff
- **Testing:** >= 70% test coverage with pytest
- **Observability:** Structured logging + CloudWatch metrics

### 🔧 Docker Configuration Fixes (2026-03-18)
- Fixed PYTHONPATH from `/app/backend/src` to `/app/backend` for correct module resolution
- Fixed worker command from `python -m worker.main` to `python -m backend.worker.main`

### ⏳ Pending Tasks
- **CI/CD Pipeline & AWS Deployment:** Can be configured later using the `cicd-aws-production` skill

---

## Skills Reference

Specialized skills available for specific modules:

- **`fastapi-api-core`**: REST API implementation with JWT
- **`aws-data-modeling`**: DynamoDB schema and queries
- **`infra-local-bootstrap`**: Docker + LocalStack setup
- **`aws-observability-bootstrap`**: CloudWatch logging and metrics setup
- **`cicd-aws-production`**: GitHub Actions + AWS deployment

---

## Dependencies

```
backend ──────┬─────> infra (Docker, LocalStack)
              │
              └─────> worker (consumes SQS, updates DynamoDB)

.github ──────> infra (references for deployment)
```

**Execution Order:**
1. ~~Implement `infra/` (Docker setup) first~~ ✅ DONE
2. ~~Implement `backend/` (API + data models)~~ ✅ DONE
3. ~~Implement `worker/` (job processor)~~ ✅ DONE
4. ~~Implement `.github/` (CI/CD)~~ ⏳ PENDING (can be done later)
