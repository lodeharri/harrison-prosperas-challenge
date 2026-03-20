# AGENTS.md - Project Root

## Project Overview

**Project Name:** Reto Prosperas - Report Job Processing System  
**Type:** Async Job Processing Platform  
**Core Functionality:** A FastAPI-based REST API that accepts report job requests, queues them via AWS SQS, processes them asynchronously with workers, and persists job state in AWS DynamoDB.

---

## Module Structure

```
harrison-prosperas-challenge/
├── infra/                     # AWS CDK Infrastructure
│   ├── app.py               # CDK entry point
│   ├── requirements.txt     # aws-cdk-lib>=2.150.0
│   ├── cdk.json            # CDK configuration
│   ├── stacks/
│   │   ├── data_stack.py   # DynamoDB + SQS
│   │   ├── compute_stack.py # App Runner (API + Worker)
│   │   ├── api_stack.py    # API Gateway + Rate Limiting
│   │   └── cdn_stack.py    # S3 + CloudFront
│   └── README.md           # CDK deployment guide
├── backend/                  # FastAPI REST API + Worker
│   ├── src/                # Hexagonal Architecture
│   │   ├── domain/         # Job entity, JobStatus, exceptions
│   │   ├── application/    # Use cases + ports (interfaces)
│   │   ├── adapters/       # DynamoDB, SQS, FastAPI routes
│   │   ├── config/         # Settings (Pydantic)
│   │   └── shared/         # JWT, exceptions, observability
│   ├── worker/             # Async SQS consumer
│   ├── init_db.py         # DynamoDB table creation
│   ├── Dockerfile         # Multi-stage Python build
│   └── tests/             # Unit + integration tests
├── frontend/              # React SPA (Vite + TypeScript)
│   ├── src/              # Components, hooks, services
│   ├── Dockerfile        # Multi-stage (Node + Nginx)
│   └── nginx.conf        # SPA routing, WS proxy
├── .github/              # CI/CD workflows
├── docker-compose.yml   # Local development orchestration
└── AGENTS.md           # This file
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

## Environment Detection

The application automatically detects the environment based on `AWS_ENDPOINT_URL`:

| Environment | `AWS_ENDPOINT_URL` | Behavior |
|-------------|-------------------|----------|
| LocalStack (dev) | Defined | Creates resources, uses local endpoints |
| AWS Production | NOT defined | Uses native AWS, CDK handles provisioning |

---

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

### JWT & Application

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | `super-secret-key...` | JWT signing key (use Secrets Manager in prod) |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `API_BASE_URL` | `http://localhost:8000` | For worker notifications |

### AWS Production Resource Names (CDK)

| Resource | Name |
|----------|------|
| DynamoDB Table | `harrison-jobs` |
| DynamoDB Table | `harrison-idempotency` |
| SQS Queue | `harrison-jobs-queue` |
| SQS DLQ | `harrison-jobs-dlq` |
| SQS Priority Queue | `harrison-jobs-priority` |

---

## Task List

### Completed
- [x] Local Development (Docker, LocalStack, Zero-config startup)
- [x] REST API (all endpoints: POST/GET /jobs, JWT auth, health, CORS)
- [x] Persistence (DynamoDB with GSI on user_id)
- [x] Workers (async, DLQ, circuit breaker, exponential backoff)
- [x] Bonus: Priority queues, WebSocket, CloudWatch, Tests (92%), Idempotency
- [x] CI/CD Pipeline (GitHub Actions + AWS deployment via CDK)
- [x] CDK v2 Compatibility (CloudFront API fixes, enum conversions, synth working)

### Pending
- [ ] AWS Production deployment (requires GitHub Actions trigger with configured secrets)

---

## Deployment Status

| Environment | Status |
|-------------|--------|
| Local (Docker) | ✅ Ready |
| AWS Production | ✅ CDK Synth Working (4 stacks) |

---

## Project Status
Docker Compose environment ready with LocalStack. CDK infrastructure fixed for CDK v2 compatibility (CloudFront API, enums as strings). All 4 stacks synthesize successfully: Data, Compute, API, and CDN. GitHub Actions CI/CD pipeline ready for AWS deployment.

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
- `infra/AGENTS.md`: CDK stacks, AWS resources, deployment guide
- `backend/AGENTS.md`: API, Worker, DynamoDB, SQS, tests, observability
- `frontend/AGENTS.md`: React SPA, components, hooks, WebSocket integration

---

## Dependencies

```
infra ──────> backend (references Dockerfile for App Runner)
backend ──────┬─────> infra (Docker, LocalStack)
              │
              └─────> worker (consumes SQS, updates DynamoDB)

.github ──────> infra (CDK deployment)
```

**Execution Order:**
1. ~~Implement `infra/` (Docker setup)~~ ✅ DONE
2. ~~Implement `backend/` (API + data models)~~ ✅ DONE
3. ~~Implement `worker/` (job processor)~~ ✅ DONE
4. ~~Implement `.github/` (CI/CD)~~ ✅ DONE

---

## CI/CD Workflows

### CI Pipeline (`.github/workflows/ci.yml`)
- **Trigger:** PR to `main` + push to `main`
- **Jobs:** lint-backend, typecheck-backend, test-backend, lint-frontend, test-frontend, build-frontend

### Deploy Pipeline (`.github/workflows/deploy.yml`)
- **Trigger:** Push to `main` only
- **Jobs:** build-ecr → cdk-synth → build-frontend → deploy-cdk → deploy-frontend → verify

### Required Secrets
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ACCOUNT_ID`, `JWT_SECRET_KEY`

### Required Variables
- `CDK_BOOTSTRAPPED`, `CLOUDFRONT_DISTRIBUTION_ID`

---

## 🔬 Pruebas Pendientes

### Testing Checklist

- [ ] **Prueba Local:** Verificar docker-compose funciona correctamente
  - Status: ✅ Completado (verificado por @infra-devops)
  - Nota: init_db.py tiene bug corregido con `KeyType` vs `AttributeType`

- [ ] **CDK Bootstrap:** Preparar entorno AWS
  - Status: ✅ Completado (profile `harrison-cicd` configurado)
  - Bucket: `cdk-hnb659fds-assets-216890067629-us-east-1`

- [ ] **GitHub Secrets:** Configurar secrets en repositorio
  - Status: ✅ Listos para configurar
  - Secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ACCOUNT_ID`, `JWT_SECRET_KEY`
  - Variables: `CDK_BOOTSTRAPPED`

- [ ] **CI/CD Workflow - PR a rama feature:**
  - Status: ⏳ Pendiente
  - Flujo: Push a rama → CI se ejecuta → Revisar resultados
  - Archivos: `.github/workflows/ci.yml` (ya actualizado para cualquier push)

- [ ] **CDK Deploy - Prueba manual:**
  - Status: ⏳ Pendiente
  - Comando: `cdk deploy --all --profile harrison-cicd`
  - Esperado: 4 stacks desplegadas en AWS

- [ ] **CDK Deploy - Via GitHub Actions:**
  - Status: ⏳ Pendiente
  - Trigger: Merge a main
  - Flujo: build-ecr → cdk-synth → build-frontend → deploy-cdk → deploy-frontend → verify

- [ ] **Verificación final:**
  - Status: ⏳ Pendiente
  - Checks:
    - [ ] API Gateway responde en `/health`
    - [ ] Frontend accesible via CloudFront
    - [ ] DynamoDB tablas creadas
    - [ ] SQS colas activas
    - [ ] App Runner servicios corriendo
