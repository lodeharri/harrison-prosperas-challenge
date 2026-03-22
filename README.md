# Reto Prosperas - Report Job Processing System

Sistema de procesamiento asíncrono de trabajos con FastAPI, AWS SQS, DynamoDB y workers asíncronos.

---

## 1. ARQUITECTURA

### Arquitectura de Producción (AWS)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USUARIO (Navegador)                            │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
         ▼                            ▼                            │
┌─────────────────────┐    ┌─────────────────────┐                │
│   CloudFront/S3      │    │   API Gateway REST   │                │
│   (Frontend SPA)     │    │   (REST endpoints)   │                │
└─────────────────────┘    └──────────┬──────────┘                │
                                       │                            │
                                       │ HTTPS                      │
                                       ▼                            │
                         ┌─────────────────────────────────────────┐
                         │              ALB (Port 8000)            │
                         │         (API + WebSocket)              │
                         └──────────────────┬──────────────────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
            ┌───────────────┐      ┌───────────────┐      ┌──────────────┐
            │  ECS Fargate  │      │  ECS Fargate  │      │    S3        │
            │  (API)        │◄─────│  (Worker)     │      │  (Static)    │
            │  /ws/jobs     │      │  SQS Poll     │      └──────────────┘
            │  /jobs        │      │  DynamoDB     │
            │  /internal/   │      │  /internal/   │
            │    notify     │──────►│    notify     │
            └───────────────┘      └───────┬───────┘
                                           │
                                           ▼
                                   ┌───────────────┐
                                   │   DynamoDB    │
                                   │ (jobs table)  │
                                   └───────────────┘
                                           ▲
                                           │
                                   ┌───────┴───────┐
                                   │     SQS       │
                                   │ • jobs-queue  │
                                   │ • priority    │
                                   │ • dlq         │
                                   └───────────────┘
```

### URLs de Producción

| Servicio | URL | Propósito |
|----------|-----|-----------|
| Frontend | `https://<cloudfront>.cloudfront.net` | SPA React |
| REST API | `https://<api-gw>.amazonaws.com/prod` | Endpoints REST |
| WebSocket | `ws://<ALB-DNS>:8000/ws/jobs` | Notificaciones en tiempo real |

### Flujo de Notificación WebSocket

```
1. Frontend conecta WebSocket → ws://<ALB>:8000/ws/jobs?user_id=X&token=JWT
2. Worker procesa job → SQS → DynamoDB (status: PROCESSING)
3. Worker llama POST /internal/notify → ALB → API (FastAPI)
4. API WebSocketManager → Broadcast a cliente conectado
5. Frontend recibe: {"type": "job_update", "data": {...}}
```

---

## 2. STACKS CDK

| Stack | Recursos |
|-------|----------|
| **data-stack** | DynamoDB (jobs, idempotency), SQS (queue, priority, dlq), VPC, ECS Cluster |
| **compute-stack** | ECR, ECS Fargate (API + Worker), ALB, IAM Roles |
| **api-stack** | API Gateway REST, Usage Plans, API Keys |
| **cdn-stack** | S3, CloudFront, OAI |

---

## 3. VARIABLES DE ENTORNO

### Desarrollo Local

```bash
# Backend
AWS_ENDPOINT_URL=http://localhost:4566
API_BASE_URL=http://localhost:8000

# Frontend
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

### Producción (ECS)

```bash
# Worker tiene API_BASE_URL apuntando al ALB
API_BASE_URL=http://<ALB-DNS>:8000
```

---

## 4. COMANDOS

### Desarrollo Local

```bash
# Iniciar todos los servicios
docker compose -f local/docker-compose.yml up -d

# Ver logs
docker compose -f local/docker-compose.yml logs -f

# Detener
docker compose -f local/docker-compose.yml down
```

### AWS

```bash
cd infra

# Desplegar
cdk deploy --all --require-approval never

# Destruir
cdk destroy --all
```

---

## 5. VERIFICACIÓN

### Local

```bash
# Health check
curl http://localhost:8000/health

# Login
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user"}'

# Crear job
curl -X POST http://localhost:8000/jobs \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "sales_report", "date_range": "last_7_days", "format": "pdf"}'
```

---

## 6. ENDPOINTS

### REST API (via API Gateway)

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/health` | No | Health check |
| POST | `/auth/token` | No | Obtener JWT |
| POST | `/jobs` | JWT | Crear trabajo |
| GET | `/jobs` | JWT | Listar trabajos |
| GET | `/jobs/{id}` | JWT | Detalle de trabajo |

### WebSocket (via ALB directo)

```
ws://<ALB>:8000/ws/jobs?user_id={user_id}&token={jwt}
```

**Mensaje recibido:**
```json
{
  "type": "job_update",
  "data": {
    "job_id": "uuid",
    "status": "PROCESSING|COMPLETED|FAILED",
    "result_url": "...",
    "updated_at": "2026-03-22T..."
  }
}
```

---

## 7. CARACTERÍSTICAS

- FastAPI REST API con Pydantic v2
- Autenticación JWT stateless (HS256)
- DynamoDB con GSI en user_id
- SQS con Dead Letter Queue y Priority Queues
- Workers asíncronos con asyncio.gather
- Circuit Breaker + Exponential Backoff
- Structured Logging + CloudWatch metrics
- Idempotency + Optimistic Locking
- **WebSocket notifications via ALB directo**
- >= 92% test coverage
- CI/CD con GitHub Actions
- Infraestructura como código con AWS CDK

---

## 8. ESTRUCTURA

```
├── backend/              # FastAPI API + Worker
│   ├── src/
│   │   ├── domain/       # Entidades, Value Objects
│   │   ├── application/   # Use Cases, Ports
│   │   ├── adapters/      # FastAPI routes, DynamoDB, SQS
│   │   └── services/      # WebSocket Manager
│   └── worker/           # SQS Consumer
├── frontend/             # React SPA
├── infra/               # AWS CDK
│   └── stacks/          # data, compute, api, cdn
├── local/               # Docker Compose local
└── .github/            # CI/CD
```

---

## 9. COSTO ESTIMADO

~$5-10/mes (ECS Fargate + DynamoDB + SQS + CloudFront)
