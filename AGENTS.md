# AGENTS.md - Project Root

## Project Overview

**Project Name:** Reto Prosperas - Report Job Processing System  
**Type:** Async Job Processing Platform  
**Core Functionality:** A FastAPI-based REST API that accepts report job requests, queues them via AWS SQS, processes them asynchronously with workers, and persists job state in AWS DynamoDB.

---

## Module Structure

```
harrison-prosperas-challenge/
├── docker-compose.yml           # Orchestrates all services (app + worker + localstack + frontend)
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
├── frontend/                    # React SPA (Vite + TypeScript)
│   ├── Dockerfile             # Multi-stage build (Node + Nginx)
│   ├── nginx.conf              # Nginx configuration for SPA
│   ├── package.json            # Dependencies
│   └── src/                    # React components
├── infra/                      # Docker + LocalStack configuration
└── .github/                   # CI/CD workflows
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
| `API_BASE_URL` | API base URL for worker notifications | `http://localhost:8000` |

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
- [x] **CORS:** Allow frontend origins (localhost:3000, 5173, 8080)
- [x] **New Fields:** `date_range` and `format` in job creation

### Persistence (DynamoDB)
- [x] **Data Model:** `job_id`, `user_id`, `status`, `report_type`, `date_range`, `format`, `created_at`, `updated_at`, `result_url`, `version`
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
- [x] **B3:** WebSocket notifications for real-time job status updates
- [x] **B5:** Observability - structured logging + metrics (CloudWatch integration)
- [x] **B6:** >= 70% test coverage with pytest
- [x] **B7:** Idempotency & Race Condition Handling (X-Idempotency-Key, optimistic locking)

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

### Docker Services
| Service | Port | Description |
|---------|------|-------------|
| `localstack` | 4566 | AWS SQS + DynamoDB emulation |
| `app` | 8000 | FastAPI REST API |
| `worker` | - | Async job processor (SQS consumer) |
| `frontend` | 3000 | React SPA (Vite build + Nginx)

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

### B3: WebSocket Notifications ✅
**Archivos:**
- `backend/src/services/websocket_manager.py` - Connection manager
- `backend/src/adapters/primary/fastapi/routes/websocket.py` - WS endpoint
- `backend/src/adapters/primary/fastapi/routes/notify.py` - Internal notification endpoint
- `backend/worker/http_client.py` - HTTP client for notifications

**Endpoints:**
| Path | Método | Descripción |
|------|--------|-------------|
| `/ws/jobs/{user_id}?token={jwt}` | WS | Notificaciones en tiempo real |
| `/internal/notify` | POST | Endpoint interno para worker |

**Flujo de Notificación:**
1. Worker procesa job y actualiza estado en DynamoDB
2. Worker hace HTTP POST a `/internal/notify` con datos del job
3. API reenvía notificación a clientes WebSocket conectados

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

### B7: Idempotency & Race Condition Handling ✅
**Archivos modificados:**
- `backend/src/domain/entities/job.py` - Campo `version` para optimistic locking
- `backend/src/domain/exceptions/domain_exceptions.py` - `VersionConflictException`
- `backend/src/shared/exceptions.py` - `ConflictException` para HTTP 409
- `backend/src/application/ports/job_repository.py` - Métodos para idempotency
- `backend/src/adapters/secondary/dynamodb/job_repository.py` - Conditional updates
- `backend/src/adapters/primary/fastapi/routes/jobs.py` - Header `X-Idempotency-Key`
- `backend/src/application/use_cases/create_job.py` - Lógica de idempotency
- `backend/init_db.py` - GSI para idempotency key

**Funcionalidades implementadas:**
| Feature | Descripción |
|---------|-------------|
| Idempotency Key | Header `X-Idempotency-Key` para requests seguros |
| Optimistic Locking | Campo `version` con conditional writes en DynamoDB |
| Version Conflict | `VersionConflictException` cuando hay race conditions |
| HTTP 409 Conflict | Respuesta apropiada para conflictos de versión |
| TTL para Keys | Idempotency keys expiran en 24 horas |
| GSI idempotency_key | Índice para búsquedas eficientes de keys |

---

## Frontend - React SPA

### Estructura del Proyecto
```
frontend/
├── src/
│   ├── components/
│   │   ├── common/
│   │   │   └── Toast.tsx          # Notificaciones toast
│   │   ├── jobs/
│   │   │   ├── JobForm.tsx        # Formulario de solicitud
│   │   │   ├── JobList.tsx        # Lista de jobs
│   │   │   ├── JobCard.tsx        # Tarjeta individual
│   │   │   └── JobBadge.tsx       # Badge de estado
│   │   └── layout/
│   │       ├── Header.tsx          # Encabezado con estado WS
│   │       └── Layout.tsx          # Layout principal
│   ├── hooks/
│   │   ├── useAuth.ts             # Manejo de autenticación JWT
│   │   ├── useJobs.ts             # Gestión de jobs (CRUD)
│   │   └── useWebSocket.ts         # Conexión WebSocket en tiempo real
│   ├── services/
│   │   └── api.ts                 # Cliente API (axios)
│   ├── pages/
│   │   ├── Login.tsx              # Página de login
│   │   └── Dashboard.tsx          # Dashboard principal
│   ├── types/
│   │   └── index.ts               # Tipos TypeScript
│   └── App.tsx                    # Componente principal
├── Dockerfile                     # Multi-stage (Node + Nginx)
├── nginx.conf                     # Configuración Nginx
├── tailwind.config.js             # Tailwind CSS config
└── .env.example                   # Variables de entorno
```

### Funcionalidades Implementadas

| # | Requisito PRD | Estado | Descripción |
|---|---------------|--------|-------------|
| 5 | Core Setup & Technologies | ✅ | React 18+ con Vite + TypeScript + Tailwind CSS |
| 6 | Report Request Form | ✅ | Form con `report_type`, `date_range`, `format` |
| 7 | Job List & Visual Feedback | ✅ | Lista con badges de colores por estado |
| 8 | Automatic State Updates | ✅ | WebSocket para actualizaciones en tiempo real |
| 9 | Responsive Design | ✅ | Tailwind CSS con breakpoints sm/lg |
| B3 | Real-time notifications | ✅ | WebSocket para notificaciones push |

### Componentes UI

#### JobBadge
Muestra el estado del job con colores y emoji:
- ⏳ PENDING (amarillo)
- 🔄 PROCESSING (azul)
- ✅ COMPLETED (verde)
- ❌ FAILED (rojo)

#### JobForm
Formulario de solicitud de reporte:
- Selector de tipo de reporte
- Selector de rango de fechas
- Selector de formato (PDF/CSV/Excel)
- Validación y feedback de errores

#### JobList
Lista de reportes del usuario:
- Tarjetas con información del job
- Indicador de conexión WebSocket
- Botón de actualización manual
- Paginación con contador total

### Hooks Personalizados

#### useAuth
```typescript
const { isAuthenticated, isLoading, error, login, logout } = useAuth();
```

#### useJobs
```typescript
const { jobs, total, isLoading, error, createJob, updateJobLocally, fetchJobs } = useJobs();
```

#### useWebSocket
```typescript
const { isConnected, lastMessage, connect, disconnect } = useWebSocket(handleMessage);
```

### Variables de Entorno

| Variable | Valor | Descripción |
|----------|-------|-------------|
| `VITE_API_URL` | http://localhost:8000 | URL base del API |
| `VITE_WS_URL` | ws://localhost:8000 | URL del WebSocket |

### Comandos

```bash
# Desarrollo
cd frontend
npm install
npm run dev

# Producción (Docker)
docker compose up frontend

# Build standalone
npm run build
```

### Flujo de Usuario

1. **Login**: Usuario ingresa su ID → Obtiene JWT token
2. **Solicitar Reporte**: Completa formulario → API crea job → Se muestra en lista
3. **Ver Estado**: Badges muestran estado en tiempo real
4. **Notificaciones**: WebSocket actualiza automáticamente cuando el job cambia de estado
5. **Descargar**: Si COMPLETED, botón para descargar resultado

### WebSocket Integration (B3)

El frontend se conecta al WebSocket del backend para recibir notificaciones en tiempo real:

```typescript
// URL: ws://localhost:8000/ws/jobs/{user_id}?token={jwt}
const ws = new WebSocket(`${WS_URL}/ws/jobs/${userId}?token=${token}`);

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === 'job_update') {
    // Actualizar UI con nuevos datos del job
    updateJobLocally(message.data.job_id, message.data);
    showToast(`Job actualizado: ${message.data.status}`);
  }
};
```

### Responsive Design

El layout es completamente responsive:
- **Desktop**: Grid 2 columnas (formulario + lista)
- **Mobile**: Stack vertical

Tailwind breakpoints:
- `sm:` (640px+) - Ajustes menores
- `lg:` (1024px+) - Grid columns

---

## Project Completion Summary

### ✅ All Local Development Tasks Completed
- **Infrastructure:** Docker, LocalStack (SQS + DynamoDB emulation)
- **REST API:** FastAPI with JWT authentication, all endpoints implemented
- **Workers:** Async processing with priority queues, DLQ, circuit breaker, exponential backoff
- **Frontend:** React SPA with Vite + Nginx (Dockerized)
- **Testing:** >= 70% test coverage with pytest
- **Observability:** Structured logging + CloudWatch metrics
- **New Features:**
  - `date_range` and `format` fields for report jobs
  - CORS configuration for frontend integration
  - WebSocket notifications for real-time job updates

### 🔧 Docker Configuration Fixes (2026-03-18)
- Fixed PYTHONPATH from `/app/backend/src` to `/app/backend` for correct module resolution
- Fixed worker command from `python -m worker.main` to `python -m backend.worker.main`

### 🔧 WebSocket Fixes (2026-03-19)
- Fixed `ws_routes.py`: `verify_token()` returns `str` (user_id), not dict
- Fixed `websocket_manager.py`: Removed duplicate `websocket.accept()` call
- Fixed `docker-compose.yml`: Added `API_BASE_URL=http://app:8000` for worker notifications

### 🔧 Frontend Docker Configuration (2026-03-18)
- Created multi-stage Dockerfile (Node 18 + Nginx alpine)
- Added nginx.conf with SPA routing, WebSocket proxy, and security headers
- Integrated frontend service with healthcheck and dependency on app service

### 🔧 Worker Bug Fix - Jobs Always FAILED (2026-03-19)
**Problem:** Jobs were always ending with status FAILED instead of COMPLETED.

**Root Cause:** Multiple issues with structured logging (structlog) configuration:
1. `structlog.make_filtering_bound_logger()` in `main.py` and `processor.py` doesn't handle keyword arguments correctly in structlog 25.x
2. Module files (`http_client.py`, `dynamodb_client.py`, `circuit_breaker.py`) used `logging.getLogger()` (stdlib) instead of `structlog.get_logger()`, causing `Logger._log() got an unexpected keyword argument 'job_id'` errors

**Solution:**
1. Changed structlog configuration in `main.py` and `processor.py`:
   ```python
   structlog.configure(
       processors=[...],
       wrapper_class=structlog.BoundLogger,  # Changed from make_filtering_bound_logger()
       ...
   )
   ```
2. Changed all worker modules to use `structlog.get_logger()` instead of `logging.getLogger()`:
   - `http_client.py`
   - `dynamodb_client.py`
   - `circuit_breaker.py`

**Files Modified:**
- `backend/worker/main.py`
- `backend/worker/processor.py`
- `backend/worker/http_client.py`
- `backend/worker/dynamodb_client.py`
- `backend/worker/circuit_breaker.py`

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
