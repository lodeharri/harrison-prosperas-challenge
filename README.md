# Reto Prosperas - Report Job Processing System

Sistema de procesamiento asíncrono de trabajos con FastAPI, AWS SQS, DynamoDB y workers asíncronos con notificaciones en tiempo real via WebSocket.

---

## Tabla de Contenidos

1. [Arquitectura](#1-arquitectura)
2. [Estructura del Proyecto](#2-estructura-del-proyecto)
3. [Endpoints del Backend](#3-endpoints-del-backend)
4. [Desarrollo Local con Docker Compose](#4-desarrollo-local-con-docker-compose)
5. [Despliegue a Producción](#5-despliegue-a-producción)
6. [Credenciales Requeridas](#6-credenciales-requeridas)
7. [Estrategias Implementadas](#7-estrategias-implementadas)
8. [Verificación](#8-verificación)

---

## 1. Arquitectura

### Arquitectura de Producción (AWS)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USUARIO (Navegador)                            │
│                  ┌──────────────────────┐                                  │
│                  │  React SPA + WebSocket │                                 │
│                  │  (Conexión WS activa)  │                                 │
└──────────────────┴──────────┬─────────────┴──────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  CloudFront     │  │  API Gateway   │  │   S3 Bucket    │
│  (Frontend SPA) │  │  (REST API)    │  │  (Static)      │
│  Puerto: 443    │  │  Rate Limit    │  │                │
│                 │  │  100 req/s     │  │                │
└────────┬────────┘  └────────┬────────┘  └─────────────────┘
         │                    │
         │                    │ HTTPS (JWT + API Key)
         │                    ▼
         │         ┌─────────────────────────────────┐
         │         │       ALB (Port 8000)          │
         │         │   (API + WebSocket)            │
         │         └──────────────┬──────────────────┘
         │                        │
         │    ┌───────────────────┼───────────────────┐
         │    │                   │                   │
         ▼    ▼                   ▼                   ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  ECS Fargate    │    │  ECS Fargate    │    │    S3 (Static)  │
│  (API)          │    │  (Worker)       │    │                  │
│  /ws/jobs       │◄───│  SQS Poll       │    │  Frontend HTML   │
│  /jobs          │    │  DynamoDB       │    │  JS/CSS          │
│  /auth/token    │    │  POST /internal │───▶│                  │
│  /health        │    │    /notify     │    └─────────────────┘
└─────────────────┘    └────────┬────────┘
                                │
                                ▼
                    ┌─────────────────────┐
                    │     DynamoDB         │
                    │  • jobs (PK: job_id) │
                    │  • idempotency      │
                    │    (GSI: user_id)    │
                    └─────────────────────┘
                                ▲
                                │
                    ┌───────────┴───────────┐
                    │         SQS            │
                    │ • harrison-jobs-queue │
                    │ • harrison-jobs-      │
                    │   priority            │
                    │ • harrison-jobs-dlq   │
                    └───────────────────────┘
```

### Flujo de Datos Completo

```
1. Usuario se loguea → POST /auth/token → Recibe JWT
2. Usuario crea job → POST /jobs (JWT) → DynamoDB (PENDING) → SQS
3. Worker detecta job → Poll SQS → DynamoDB (PROCESSING)
4. Worker notifica API → POST /internal/notify
5. API WebSocket → Broadcast a cliente
6. Usuario recibe notificación tiempo real
7. Worker procesa (5-30s) → DynamoDB (COMPLETED/FAILED)
8. Worker notifica API → POST /internal/notify
9. Usuario recibe actualización final
```

### URLs de Producción

| Servicio | URL | Propósito |
|----------|-----|-----------|
| Frontend (Pruebas) | `https://d1n3v8uwwdhhlr.cloudfront.net/` | SPA React - Entorno de pruebas |
| Frontend (Producción) | `https://<cloudfront>.cloudfront.net` | SPA React - Producción |
| REST API | `https://<api-gw>.amazonaws.com/prod` | Endpoints REST |
| WebSocket | `wss://<cloudfront>.cloudfront.net/ws/jobs` | Notificaciones en tiempo real |

---

## 2. Estructura del Proyecto

```
reto-prosperas/
├── backend/                    # FastAPI API + Worker
│   ├── src/
│   │   ├── domain/             # Entidades, Value Objects, Excepciones
│   │   │   ├── entities/       # Job entity
│   │   │   ├── value_objects/ # JobStatus enum
│   │   │   └── exceptions/    # Domain exceptions
│   │   ├── application/       # Casos de uso + Puertos (Hexagonal)
│   │   │   ├── ports/         # JobRepository, JobQueue interfaces
│   │   │   └── use_cases/     # CreateJob, GetJob, ListJobs, UpdateJobStatus
│   │   ├── adapters/          # Implementaciones concretas
│   │   │   ├── primary/fastapi/ # Routes, WebSocket, Main
│   │   │   └── secondary/     # DynamoDB, SQS implementaciones
│   │   ├── config/            # Pydantic settings
│   │   ├── services/          # WebSocketManager
│   │   └── shared/            # JWT, Excepciones, Observabilidad
│   └── worker/                # Consola SQS (async processor)
│       ├── main.py            # Entry point + signal handlers
│       ├── processor.py       # Lógica principal de procesamiento
│       ├── config.py          # Configuración worker
│       ├── circuit_breaker.py # Circuit breaker pattern
│       ├── backoff.py         # Exponential backoff
│       ├── sqs_client.py     # SQS operations
│       └── dynamodb_client.py # DynamoDB operations
├── frontend/                  # React SPA
│   ├── src/
│   │   ├── components/        # Componentes React
│   │   ├── hooks/             # useAuth, useJobs, useWebSocket
│   │   ├── services/          # Axios API client
│   │   ├── pages/             # Login, Dashboard
│   │   └── types/             # TypeScript interfaces
│   ├── Dockerfile            # Multi-stage (Node → Nginx)
│   └── nginx.conf            # Configuración Nginx
├── infra/                     # AWS CDK
│   ├── app.py                # CDK app entry
│   └── stacks/               # AWS stacks
│       ├── data_stack.py     # DynamoDB, SQS, VPC, ECS Cluster
│       ├── compute_stack.py  # ECR, ECS Fargate, ALB
│       ├── api_stack.py      # API Gateway, Rate Limiting
│       └── cdn_stack.py      # S3, CloudFront, OAI
├── local/                     # Docker Compose local
│   ├── docker-compose.yml   # Servicios locales
│   └── init-aws.sh          # Scripts de inicialización
├── .github/
│   └── workflows/
│       ├── ci.yml            # CI pipeline
│       └── deploy.yml        # Deployment pipeline
├── README.md
└── AGENTS.md                # Configuración de agentes IA
```

---

## 3. Endpoints del Backend

### API REST (Base URL: `http://localhost:8000` o producción)

| Método | Ruta | Auth | Descripción | Rate Limit |
|--------|------|------|-------------|------------|
| GET | `/health` | No | Health check de la API y dependencias | Sin límite |
| POST | `/auth/token` | No | Obtener JWT con user_id | 100 req/sec |
| POST | `/jobs` | JWT | Crear trabajo de reporte | 100 req/sec |
| GET | `/jobs` | JWT | Listar trabajos del usuario (paginado) | 100 req/sec |
| GET | `/jobs/{job_id}` | JWT | Obtener detalles de un trabajo | 100 req/sec |
| POST | `/internal/notify` | Interno | Endpoint para notificaciones del worker | Rate limit ALB |

**Producción:** Todos los endpoints (excepto `/health`) requieren API Key en el header `x-api-key`.

### WebSocket

| Path | Query Params | Descripción |
|------|--------------|-------------|
| `/ws/jobs` | `user_id`, `token` | Conexión WebSocket para notificaciones |

**URL completa:** `ws://localhost:8000/ws/jobs?user_id={id}&token={jwt}`

### Ejemplos de Uso

#### 1. Obtener Token (Login)

```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user"}'

# Respuesta:
# {"access_token": "eyJ...", "token_type": "bearer", "expires_in": 1800}
```

#### 2. Crear un Job

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "sales_report",
    "date_range": "last_7_days",
    "format": "pdf"
  }'

# Respuesta:
# {"job_id": "uuid", "status": "PENDING", "idempotent": false}
```

#### 3. Listar Jobs

```bash
curl -X GET "http://localhost:8000/jobs?page=1&page_size=20" \
  -H "Authorization: Bearer <TOKEN>"

# Respuesta:
# {
#   "items": [...],
#   "total": 10,
#   "page": 1,
#   "page_size": 20
# }
```

#### 4. Ver Detalle de un Job

```bash
curl -X GET http://localhost:8000/jobs/<job_id> \
  -H "Authorization: Bearer <TOKEN>"

# Respuesta:
# {
#   "job_id": "uuid",
#   "user_id": "test-user",
#   "status": "COMPLETED",
#   "report_type": "sales_report",
#   "date_range": "last_7_days",
#   "format": "pdf",
#   "result_url": "https://...",
#   "created_at": "2026-03-22T...",
#   "updated_at": "2026-03-22T..."
# }
```

#### 5. Idempotencia (retry seguro)

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Idempotency-Key: unique-key-123" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "sales_report", "date_range": "last_7_days", "format": "pdf"}'
```

### Mensajes WebSocket

El servidor envía mensajes cuando cambia el estado de un job:

```json
{
  "type": "job_update",
  "data": {
    "job_id": "uuid",
    "status": "PROCESSING",
    "result_url": null,
    "updated_at": "2026-03-22T10:30:00Z",
    "report_type": "sales_report"
  }
}
```

Estados posibles: `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`

---

## 4. Desarrollo Local con Docker Compose

```bash
cd /local && docker compose up -d
```
---

## 5. Despliegue a Producción

### Pipeline de GitHub Actions

El workflow `.github/workflows/deploy.yml` ejecuta:

```
build-ecr → cdk-synth → build-frontend → deploy-cdk → deploy-frontend → verify
```

| Paso | Descripción |
|------|-------------|
| build-ecr | Construye imágenes Docker y sube a ECR |
| cdk-synth | Sintetiza CloudFormation, obtiene outputs |
| build-frontend | Build React con variables de entorno |
| deploy-cdk | Despliega infraestructura AWS |
| deploy-frontend | Sube assets a S3 e invalida CloudFront |
| verify | Verifica que el health check funcione |

### Configuración de Secrets

En el repositorio GitHub, ve a **Settings → Secrets and variables → Actions** y configura:

| Secret | Descripción | Ejemplo |
|--------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | ID de clave de acceso AWS | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | Clave de acceso secreta | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_ACCOUNT_ID` | ID de cuenta AWS | `123456789012` |
| `JWT_SECRET_KEY` | Clave para firmar JWT (genera con: `openssl rand -hex 32`) | `a1b2c3d4...` |

### Variables (públicas)

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `AWS_REGION` | `us-east-1` | Región AWS |

### Despliegue Manual (opcional)

```bash
# 1. Configurar credenciales AWS
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_ACCOUNT_ID=...

# 2. Instalar dependencias
npm install
pip install -r backend/requirements.txt

# 3. Desplegar infraestructura CDK
cd infra
cdk deploy --all --require-approval never

# 4. Construir y empujar imágenes ECR (manual)
# (El workflow de GitHub lo hace automáticamente)
```

---

## 6. Credenciales Requeridas

### Desarrollo Local

No se requiere configuración adicional. Docker Compose usa credenciales de prueba de LocalStack.

### Producción (GitHub Actions)

| Secret | Cómo obtenerlo |
|--------|----------------|
| `AWS_ACCESS_KEY_ID` | AWS IAM → Users → Security credentials |
| `AWS_SECRET_ACCESS_KEY` | Mismo que arriba al crear Access Key |
| `AWS_ACCOUNT_ID` | AWS Console → Account ID (12 dígitos) |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` |

### Permisos IAM Requeridos

El usuario/rol de AWS debe tener:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:*",
        "ecs:*",
        "dynamodb:*",
        "sqs:*",
        "s3:*",
        "apigateway:*",
        "cloudfront:*",
        "iam:*",
        "logs:*",
        "cloudwatch:*"
      ]
    }
  ]
}
```

---

## 7. Estrategias Implementadas

### 7.1 Rate Limiting (API Gateway)

**Por qué:** Limitar el tráfico para proteger la API de abusos y garantizar QoS.

| Configuración | Valor |
|---------------|-------|
| Rate Limit | 100 req/segundo |
| Burst Limit | 200 |
| Monthly Quota | 10,000 req/mes |

**Implementación:** AWS API Gateway Usage Plans + API Keys.

**Impacto:** Previene DDoS y garantiza que la API funcione bajo load.

---

### 7.2 Graceful Shutdown (Worker)

**Por qué:** Cuando ECS envía SIGTERM, el worker debe terminar de procesar jobs activos antes de cerrarse, evitando pérdida de trabajo.

**Estrategia:**

```
1. Recibir SIGTERM/SIGINT
2. signal.alarm(30s) - timeout de seguridad
3. self.running = False (dejar de aceptar nuevos jobs)
4. asyncio.wait(tareas_activas, timeout=10s)
5. Cerrar conexiones (SQS, DynamoDB, HTTP)
6. signal.alarm(0) - cancelar timeout
```

| Timeout | Valor | Propósito |
|---------|-------|-----------|
| Shutdown total | 30 segundos | Timeout de seguridad |
| Espera jobs activos | 10 segundos | jobs activos pueden terminar |

**Archivos:** `backend/worker/main.py`, `backend/worker/processor.py`

---

### 7.3 Priority Queues (SQS)

**Por qué:** Algunos reportes (ventas, financieros) son más urgentes que otros.

**Estrategia:**

```
• Cola PRIORITY: sales_report, financial_report (poll cada 0.5s)
• Cola STANDARD: otros tipos (poll cada 2s)
• Worker siempre verifica PRIORITY primero
```

**Colas:**
- `harrison-jobs-queue` (estándar)
- `harrison-jobs-priority` (alta prioridad)
- `harrison-jobs-dlq` (Dead Letter Queue)

---

### 7.4 Circuit Breaker

**Por qué:** Si un tipo de reporte falla repetidamente, no tiene sentido seguir intentando (ej: servicio externo caído).

**Estrategia:**

```
• Si 5 fallos consecutivos de un report_type
• "Abrir" circuit (bloquear nuevos intentos)
• Esperar 300 segundos (recovery timeout)
• Permitir 1 intento ("half-open")
• Si falla de nuevo, abrir de nuevo
```

**Archivo:** `backend/worker/circuit_breaker.py`

---

### 7.5 Exponential Backoff

**Por qué:** En reintentos, esperar cada vez más tiempo reduce load en servicios temporalmente no disponibles.

**Estrategia:**
```
Intento 1: esperar 1s
Intento 2: esperar 2s
Intento 3: esperar 4s
...
Máximo: 60s
```

**Archivo:** `backend/worker/backoff.py`

---

### 7.6 Idempotency

**Por qué:** Si el cliente reintenta una request (network timeout), no crear jobs duplicados.

**Estrategia:**

```
• Header: X-Idempotency-Key
• Guardar en DynamoDB (TTL 24h)
• Si existe, devolver job existente
• Si no, crear nuevo job
```

**Tabla:** `harrison-idempotency` (key: idempotency_key, TTL: 24h)

---

### 7.7 Optimistic Locking

**Por qué:** Prevenir race conditions cuando worker procesa y actualiza el mismo job concurrentemente.

**Estrategia:**

```
• Campo "version" en DynamoDB
• En update: WHERE job_id = :id AND version = :expected
• Si version no coincide → HTTP 409 Conflict
• Worker re-intenta con nueva versión
```

---

### 7.8 WebSocket via ALB

**Por qué:** API Gateway no soporta WebSocket directamente. CloudFront + ALB sí.

**Arquitectura:**
```
Frontend → CloudFront (443) → ALB (8000) → ECS API
                              → WebSocket upgrade
```

**Nota:** El Worker necesita `API_BASE_URL` apuntando al ALB para poder notificar cambios.

---

### 7.9 Observabilidad

**Por qué:** Necesario para debug y monitoreo en producción.

**Implementaciones:**
- **Logging:** structlog con JSON output
- **Métricas CloudWatch:** JobsProcessed, JobsFailed, ProcessingDuration
- **Health Checks:** /health endpoint verifica DynamoDB + SQS

---

## 8. Verificación

### Verificación Local

```bash
# Health check
curl http://localhost:8000/health
# {"status": "healthy", "version": "1.0.0", "dependencies": {"dynamodb": "ok", "sqs": "ok"}}

# Login
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user"}'

# Crear job
curl -X POST http://localhost:8000/jobs \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "sales_report", "date_range": "last_7_days", "format": "pdf"}'

# Listar jobs
curl -X GET http://localhost:8000/jobs \
  -H "Authorization: Bearer <TOKEN>"
```

### Verificación Producción

```bash
# Obtener API URL desde CloudFormation
API_URL=$(aws cloudformation describe-stacks \
  --stack-name harrison-api-stack \
  --query 'Stacks[0].Outputs[?OutputKey==`APIUrl`].OutputValue' \
  --output text)

# Health check
curl ${API_URL}/health

# Login
TOKEN=$(curl -s -X POST ${API_URL}/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test"}' | jq -r '.access_token')

# Crear job (con API Key)
curl -X POST ${API_URL}/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-api-key: harrison-api-key" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "sales_report", "date_range": "last_7_days", "format": "pdf"}'
```

---

## Características Técnicas

- ✅ FastAPI REST API con Pydantic v2
- ✅ Autenticación JWT stateless (HS256)
- ✅ DynamoDB con GSI en user_id
- ✅ SQS con Dead Letter Queue y Priority Queues
- ✅ Workers asíncronos con asyncio.gather
- ✅ Circuit Breaker + Exponential Backoff
- ✅ Structured Logging + CloudWatch metrics
- ✅ Idempotency + Optimistic Locking
- ✅ API Gateway Rate Limiting (100 req/sec, burst 200)
- ✅ WebSocket notifications via CloudFront + ALB
- ✅ Graceful Shutdown con timeout de seguridad (30s)
- ✅ >= 92% test coverage
- ✅ CI/CD con GitHub Actions
- ✅ Infraestructura como código con AWS CDK

---

## Contacto

Para dudas o problemas, revisar los logs de CloudWatch en `/reto-prosperas/`.
