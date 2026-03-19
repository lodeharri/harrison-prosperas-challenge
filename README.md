# Reto Prosperas - Report Job Processing System

Sistema de procesamiento asíncrono de trabajos con FastAPI, AWS SQS, DynamoDB (LocalStack) y workers asíncronos.

## 🏗️ Arquitectura

```
┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│   Cliente    │────▶│  FastAPI    │────▶│   DynamoDB   │
│   (JWT)     │     │  (REST)     │     │   (jobs)     │
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

## 🚀 Quick Start

1. `cp .env.example .env`
2. `docker compose -f local/docker-compose.yml up -d`
3. `docker exec harrison-prosperas-localstack /bin/bash /etc/localstack/init/ready.d/init-aws.sh`
4. `curl http://localhost:8000/health`

## 🧪 Probar el Sistema (Complete Flow)

### Flujo: Crear → Procesar → Verificar

**Paso 1: Obtener Token**
```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user"}' | jq -r '.access_token')
```

**Paso 2: Crear Job**
```bash
curl -s -X POST "http://localhost:8000/jobs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "sales_report", "date_range": "2024-01-01 to 2024-01-31", "format": "pdf"}' | jq .
```

**Paso 3: Verificar (espera 30s para que worker procese)**
```bash
# Ver todos los jobs
curl -s -X GET "http://localhost:8000/jobs" -H "Authorization: Bearer $TOKEN" | jq .

# Ver un job específico
curl -s -X GET "http://localhost:8000/jobs/{job_id}" -H "Authorization: Bearer $TOKEN" | jq .
```

### Estados del Job

```
PENDING → PROCESSING → COMPLETED
                     → FAILED → DLQ
```

## 📡 Endpoints

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/health` | No | Health check |
| POST | `/auth/token` | No | Obtener JWT |
| POST | `/jobs` | JWT | Crear trabajo |
| GET | `/jobs` | JWT | Listar trabajos |
| GET | `/jobs/{id}` | JWT | Detalle de trabajo |

## 🔧 Comandos Útiles

```bash
docker compose -f local/docker-compose.yml up -d          # Iniciar
docker compose -f local/docker-compose.yml logs -f         # Ver logs
docker compose -f local/docker-compose.yml logs app        # Logs API
docker compose -f local/docker-compose.yml logs worker     # Logs worker
docker compose -f local/docker-compose.yml ps              # Estado servicios
docker compose -f local/docker-compose.yml down            # Detener
```

## 📁 Estructura

```
harrison-prosperas-challenge/
├── backend/                    # FastAPI REST API + Worker
├── frontend/                   # React SPA (opcional)
├── infra/                      # Scripts de inicialización
├── docker-compose.yml
├── .env.example
└── AGENTS.md                  # Documentación completa
```

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
