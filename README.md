# Reto Prosperas - Report Job Processing System

Sistema de procesamiento asíncrono de trabajos con FastAPI, AWS SQS, DynamoDB (LocalStack) y workers asíncronos.

---

## 1. ARQUITECTURA DEL SISTEMA

### Diagrama de flujo completo:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USUARIO (Navegador)                                │
└──────────────────────────────────┬────────────────────────────────────────────┘
                                   │ HTTPS
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLOUDFRONT                                      │
│                         (CDN - Static Hosting)                                │
│                    ┌────────────────────────────┐                           │
│                    │     Frontend React SPA     │                           │
│                    │   (Vite Build - Nginx)     │                           │
│                    └────────────────────────────┘                           │
└──────────────────────────────────┬────────────────────────────────────────────┘
                                   │
                                   │ HTTPS (API calls)
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            API GATEWAY                                       │
│                    (Rate Limiting: 100 req/min)                              │
│              ┌─────────────────────────────────────┐                        │
│              │  /auth/token  - JWT Generation       │                        │
│              │  /jobs        - Create/List Jobs     │                        │
│              │  /jobs/{id}   - Get Job Details     │                        │
│              │  /health      - Health Check        │                        │
│              └─────────────────────────────────────┘                        │
└──────────────────────────────────┬────────────────────────────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
           ┌────────────┐  ┌────────────┐  ┌────────────┐
           │  App       │  │  App       │  │  App       │
           │  Runner    │  │  Runner    │  │  Runner    │
           │  (API)     │  │  (Worker)  │  │  (WS)      │
           │  Port 8000 │  │  SQS Poll  │  │  Events    │
           └─────┬──────┘  └──────┬─────┘  └────────────┘
                 │                │
        ┌────────┴────────┐       │
        │                 │       │
        ▼                 ▼       ▼
   ┌─────────┐      ┌─────────┐
   │ DynamoDB│      │   SQS   │
   │ (Jobs)  │      │ (Queue) │
   │(Idempot)│      │         │
   └─────────┘      └────┬────┘
                         │
                         ▼
                   ┌───────────┐
                   │  Worker   │
                   │ (Process) │
                   └───────────┘
```

---

## 2. FLUJO DE DATOS

### 2.1 Creación de Job (Usuario → Backend → Queue → Worker)

```
1. Usuario → POST /auth/token → Recibe JWT
2. Usuario → POST /jobs (con JWT) → API crea job en DynamoDB
3. API → Publish a SQS (cola de prioridad si es sales_report)
4. Worker → Poll SQS → Recibe mensaje
5. Worker → Update DynamoDB (status: PROCESSING)
6. Worker → Procesa job (5-30 segundos)
7. Worker → Update DynamoDB (status: COMPLETED)
8. Worker → POST /internal/notify → API
9. API → WebSocket → Usuario ve actualización en tiempo real
```

### 2.2 Frontend → API Gateway → ECS Fargate → DynamoDB

```
┌─────────┐     ┌────────────┐     ┌─────────────┐     ┌─────────┐
│Frontend │────▶│CloudFront  │────▶│API Gateway  │────▶│ECS      │
│(React)  │◀────│(Cache)     │◀────│(Rate Limit) │◀────│Fargate  │
└─────────┘     └────────────┘     └─────────────┘     └────┬────┘
                                                            │
                                                            ▼
                                                       ┌─────────┐
                                                       │DynamoDB │
                                                       └─────────┘
```

---

## 3. PROCESO CI/CD CON GITHUB ACTIONS

### 3.1 Flujo de ramas

```
feat/mi-rama ──▶ PR ──▶ CI ──▶ Review ──▶ Merge ──▶ CI + DEPLOY
                      │                        │
                      ▼                        ▼
                  lint, test               cdk deploy
                  build                    ecr push
                                           s3 sync
```

### 3.2 Pipeline CI (.github/workflows/ci.yml)

Se ejecuta en: Push a cualquier rama + PRs

```
┌─────────────────────────────────────────────────────────────┐
│                        CI PIPELINE                          │
│  ┌───────────┐  ┌───────────┐  ┌───────────────────┐      │
│  │   lint    │  │ typecheck │  │  test-backend     │      │
│  │  (ruff)   │──▶│  (mypy)  │──▶│  (pytest + cov)  │      │
│  └───────────┘  └───────────┘  └─────────┬─────────┘      │
│                                          │                  │
│  ┌───────────┐  ┌───────────┐  ┌────────▼─────────┐      │
│  │   lint    │  │   test    │  │  build-frontend  │      │
│  │(eslint)   │──▶│(Jest)    │──▶│   (Vite)        │      │
│  └───────────┘  └───────────┘  └──────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Pipeline Deploy (.github/workflows/deploy.yml)

Se ejecuta en: Solo push a `main`

```
┌─────────────────────────────────────────────────────────────┐
│                     DEPLOY PIPELINE                         │
│                                                              │
│  ┌───────────┐                                               │
│  │ build-ecr │  (Build Docker → Push a ECR)                 │
│  └─────┬─────┘                                               │
│        │                                                     │
│  ┌─────▼─────┐     ┌───────────────┐                        │
│  │ cdk-synth │────▶│build-frontend│  (Build con API URL)    │
│  └─────┬─────┘     └───────┬───────┘                        │
│        │                    │                                │
│        └────────┬───────────┘                                │
│                 ▼                                            │
│        ┌───────────────┐                                     │
│        │  deploy-cdk  │  (CDK Deploy: DynamoDB, SQS,        │
│        │              │   ECS Fargate, API Gateway, S3)       │
│        └───────┬──────┘                                     │
│                │                                            │
│    ┌───────────┴───────────┐                                │
│    ▼                       ▼                                │
│ ┌─────────────┐    ┌─────────────┐                         │
│ │deploy-frontend│   │   verify   │  (Health check)         │
│ │ (S3 + CF)    │    └─────────────┘                         │
│ └─────────────┘                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. VARIABLES DE ENTORNO PARA DESARROLLO LOCAL

### 4.1 Backend (.env en /backend o raíz)

```bash
# ===========================================
# AWS Configuration (LocalStack)
# ===========================================
AWS_ENDPOINT_URL=http://localhost:4566
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test

# ===========================================
# DynamoDB Configuration
# ===========================================
DYNAMODB_TABLE_JOBS=harrison-jobs

# ===========================================
# SQS Configuration
# ===========================================
SQS_QUEUE_URL=http://localhost:4566/000000000000/harrison-jobs-queue
SQS_DLQ_URL=http://localhost:4566/000000000000/harrison-jobs-dlq
SQS_PRIORITY_QUEUE_URL=http://localhost:4566/000000000000/harrison-jobs-priority

# ===========================================
# JWT Authentication
# ===========================================
JWT_SECRET_KEY=super-secret-key-change-in-production-use-openssl-rand-hex-32
JWT_ALGORITHM=HS256

# ===========================================
# API Configuration
# ===========================================
API_HOST=0.0.0.0
API_PORT=8000
```

### 4.2 Frontend (.env en /frontend)

```bash
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

### 4.3 Docker Compose (local/docker-compose.yml)

Ya configurado con todas las variables necesarias.

---

## 5. COMANDOS PARA INICIAR DESARROLLO LOCAL

### 5.1 Opción 1: Docker Compose (Recomendado)

```bash
# Clonar repo y entrar al directorio
cd harrison-prosperas-challenge

# Copiar variables de entorno
cp .env.example .env

# Levantar todos los servicios
docker compose -f local/docker-compose.yml up --build -d

# Ver logs
docker compose -f local/docker-compose.yml logs -f

# Detener
docker compose -f local/docker-compose.yml down
```

### 5.2 Opción 2: Desarrollo local (sin Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
python init_db.py  # Crear tablas en LocalStack
uvicorn src.adapters.primary.fastapi.main:app --reload

# Worker (en otra terminal)
cd backend
python -m backend.worker.main

# Frontend
cd frontend
npm install
npm run dev
```

---

## 6. VERIFICACIÓN DE FUNCIONAMIENTO

### 6.1 Health Check

```bash
curl http://localhost:8000/health
# Respuesta esperada:
# {"status":"healthy","version":"1.0.0","dynamodb":"ok","sqs":"ok"}
```

### 6.2 Login (Obtener JWT)

```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user-001"}'

# Respuesta:
# {"access_token":"eyJ...","token_type":"bearer"}
```

### 6.3 Crear Job

```bash
TOKEN="tu-token-aqui"

curl -X POST http://localhost:8000/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "sales_report",
    "date_range": "last_7_days",
    "format": "pdf"
  }'

# Respuesta:
# {"job_id":"uuid-...","status":"PENDING","created_at":"..."}
```

### 6.4 Listar Jobs

```bash
TOKEN="tu-token-aqui"
curl http://localhost:8000/jobs \
  -H "Authorization: Bearer $TOKEN"
```

### 6.5 Verificar Worker procesando

```bash
# Esperar unos segundos y consultar el job
curl http://localhost:8000/jobs/{job_id} \
  -H "Authorization: Bearer $TOKEN"

# Debería cambiar de PENDING → PROCESSING → COMPLETED
```

---

## 7. RECURSOS AWS CREADOS POR CDK

| Servicio | Nombre | Propósito |
|----------|--------|-----------|
| DynamoDB | `harrison-jobs` | Tabla de jobs |
| DynamoDB | `harrison-idempotency` | Tabla de idempotencia |
| SQS | `harrison-jobs-queue` | Cola principal |
| SQS | `harrison-jobs-dlq` | Dead Letter Queue |
| SQS | `harrison-jobs-priority` | Cola de prioridad |
| ECR | `harrison-prospera-challenge` | Imágenes Docker |
| ECS Fargate | `harrison-api` | API REST con ALB |
| ECS Fargate | `harrison-worker` | Worker asíncrono |
| API Gateway | `harrison-api-gw` | Proxy + Rate Limiting |
| S3 | `harrison-frontend` | Hosting estático |
| CloudFront | `harrison-frontend-cdn` | CDN del frontend |

---

## 8. COSTO ESTIMADO AWS

| Servicio | Costo/mes |
|----------|-----------|
| ECS Fargate (API + Worker) | $5-7 |
| DynamoDB | $0-1 |
| SQS | $0 |
| API Gateway | $0 |
| S3 + CloudFront | $0.01 |
| **Total** | **~$6-8/mes** |

---

## 9. LIMPIEZA (Eliminar recursos AWS)

```bash
cd infra
cdk destroy --all
```

**Advertencia:** Esto elimina todos los datos.

---

## 📡 Endpoints

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/health` | No | Health check |
| POST | `/auth/token` | No | Obtener JWT |
| POST | `/jobs` | JWT | Crear trabajo |
| GET | `/jobs` | JWT | Listar trabajos |
| GET | `/jobs/{id}` | JWT | Detalle de trabajo |

### Estados del Job

```
PENDING → PROCESSING → COMPLETED
                     → FAILED → DLQ
```

---

## 🔧 Comandos Útiles

```bash
docker compose -f local/docker-compose.yml up -d          # Iniciar
docker compose -f local/docker-compose.yml logs -f         # Ver logs
docker compose -f local/docker-compose.yml logs app        # Logs API
docker compose -f local/docker-compose.yml logs worker     # Logs worker
docker compose -f local/docker-compose.yml ps              # Estado servicios
docker compose -f local/docker-compose.yml down            # Detener
```

---

## 📁 Estructura

```
harrison-prosperas-challenge/
├── backend/                    # FastAPI REST API + Worker
├── frontend/                   # React SPA
├── infra/                      # AWS CDK Infrastructure
├── .github/                    # GitHub Actions CI/CD
├── local/                      # Docker Compose local
├── docker-compose.yml          # Root compose file
├── .env.example
└── AGENTS.md                  # Documentación completa
```

---

## 🎯 Características

- FastAPI REST API con Pydantic v2
- Autenticación JWT stateless (HS256)
- DynamoDB con GSI en user_id
- SQS con Dead Letter Queue y Priority Queues
- Workers asíncronos con asyncio.gather
- Circuit Breaker + Exponential Backoff
- Structured Logging + CloudWatch metrics
- Idempotency + Optimistic Locking
- WebSocket notifications (real-time updates)
- >= 92% test coverage
- CI/CD completo con GitHub Actions
- Infraestructura como código con AWS CDK

---

## 🏗️ Arquitectura Simplificada

```
┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│   Cliente    │────▶│  FastAPI    │────▶│   DynamoDB   │
│   (JWT)      │     │  (REST)     │     │   (jobs)     │
└──────────────┘     └──────┬──────┘     └──────────────┘
                            │
                            ▼
                     ┌─────────────┐
                     │    SQS      │
                     │  (cola)     │
                     └──────┬──────┘
                            │
                            ▼
                     ┌─────────────┐     ┌──────────────┐
                     │   Worker    │────▶│   DynamoDB   │
                     │ (async)     │     │  (update)   │
                     └─────────────┘     └──────────────┘
```

### Servicios

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| **LocalStack** | `4566` | Emulación de AWS (SQS + DynamoDB) |
| **API (FastAPI)** | `8000` | REST API con endpoints JWT |
| **Worker** | - | Procesador asíncrono de trabajos |

---

## 🚀 Quick Start

1. `cp .env.example .env`
2. `docker compose -f local/docker-compose.yml up -d`
3. `docker exec harrison-prosperas-localstack /bin/bash /etc/localstack/init/ready.d/init-aws.sh`
4. `curl http://localhost:8000/health`
