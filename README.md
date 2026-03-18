# Reto Prosperas - Report Job Processing System

Sistema de procesamiento asíncrono de trabajos con FastAPI, AWS SQS, DynamoDB (LocalStack) y workers asíncronos.

## 📋 Índice

- [Arquitectura](#-arquitectura)
- [Requisitos](#-requisitos)
- [Levantar los Servicios](#-levantar-los-servicios)
- [Probar el Sistema](#-probar-el-sistema)
- [Verificar Estados y Logs](#-verificar-estados-y-logs)
- [Comandos Útiles](#-comandos-útiles)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Tarea Pospuesta](#-tarea-pospuesta)

---

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

---

## 📦 Requisitos

- Docker y Docker Compose
- AWS CLI (opcional, para verificar recursos)

---

## 🚀 Levantar los Servicios

### 1. Navegar al directorio del proyecto

```bash
cd /home/harri/development/projects/reto-prosperas2
```

### 2. Copiar variables de entorno

```bash
cp .env.example .env
```

### 3. Levantar todos los servicios

```bash
docker compose up -d
```

### 4. Esperar a que LocalStack esté listo

```bash
# Verificar que LocalStack está healthy
curl http://localhost:4566/_localstack/health
```

### 5. Inicializar recursos AWS (primera vez)

```bash
docker exec reto-prosperas-localstack /bin/bash /etc/localstack/init/ready.d/init-aws.sh
```

Deberías ver:
```
==============================================
AWS Resources initialized successfully!
==============================================

Queue URLs (for reference):
  Main Queue:     http://localhost:4566/000000000000/report-jobs-queue
  DLQ:            http://localhost:4566/000000000000/report-jobs-dlq
```

### 6. Verificar que la API está funcionando

```bash
curl http://localhost:8000/health
```

Deberías ver:
```json
{"status":"healthy","version":"1.0.0","dependencies":{"dynamodb":"ok","sqs":"ok"}}
```

---

## 🧪 Probar el Sistema

### Flujo Completo: Crear → Procesar → Verificar

#### Paso 1: Obtener un Token JWT

```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "mi-usuario-123"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "Token: $TOKEN"
```

**Respuesta:**
```
Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Paso 2: Crear un Trabajo

```bash
RESULT=$(curl -s -X POST "http://localhost:8000/jobs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"report_type": "reporte_ventas"}')

echo "$RESULT"
```

**Respuesta (Estado INICIAL):**
```json
{
  "job_id": "2351c0b8-cacd-4532-87ad-25193574b8ae",
  "status": "PENDING"
}
```

Guarda el `job_id` para los siguientes pasos.

#### Paso 3: Verificar Estado Inmediatamente (PENDING)

```bash
curl -s -X GET "http://localhost:8000/jobs" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta (PENDING):**
```json
{
  "items":[
    {
      "job_id":"2351c0b8-cacd-4532-87ad-25193574b8ae",
      "user_id":"mi-usuario-123",
      "status":"PENDING",
      "report_type":"reporte_ventas",
      "created_at":"2026-03-18T18:17:45.749686Z",
      "updated_at":"2026-03-18T18:17:45.749686Z",
      "result_url":null
    }
  ],
  "total":1,
  "page":1,
  "page_size":20
}
```

#### Paso 4: Esperar que el Worker Procese (5-30 segundos)

```bash
echo "Esperando 30 segundos para que el worker procese el trabajo..."
sleep 30
```

#### Paso 5: Verificar Estado Final (COMPLETED)

```bash
curl -s -X GET "http://localhost:8000/jobs" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta (COMPLETED):**
```json
{
  "items":[
    {
      "job_id":"2351c0b8-cacd-4532-87ad-25193574b8ae",
      "user_id":"mi-usuario-123",
      "status":"COMPLETED",
      "report_type":"reporte_ventas",
      "created_at":"2026-03-18T18:17:45.749686Z",
      "updated_at":"2026-03-18T18:18:11.213253Z",
      "result_url":"https://reports.example.com/reporte_ventas/2351c0b8-cacd-4532-87ad-25193574b8ae/bd876ede201c.pdf"
    }
  ],
  "total":1,
  "page":1,
  "page_size":20
}
```

#### Paso 6: Ver Detalle de un Trabajo Específico

```bash
curl -s -X GET "http://localhost:8000/jobs/2351c0b8-cacd-4532-87ad-25193574b8ae" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📊 Verificar Estados y Logs

### Ver Logs de la API

```bash
# Ver últimos 20 logs
docker compose logs app --tail=20

# Ver logs en tiempo real
docker compose logs app --tail=20 -f

# Ver solo logs de creación de trabajos
docker compose logs app --tail=20 | grep -E "(Created job|Published job)"
```

**Logs esperados de la API:**
```
2026-03-18 18:17:45,749 - app.services.dynamodb - INFO - Created job: 2351c0b8-cacd-4532-87ad-25193574b8ae
2026-03-18 18:17:45,751 - app.services.sqs - INFO - Published job 2351c0b8-cacd-4532-87ad-25193574b8ae to SQS queue
2026-03-18 18:17:45,751 - app.routers.jobs - INFO - Created job 2351c0b8-cacd-4532-87ad-25193574b8ae for user mi-usuario-123
```

### Ver Logs del Worker

```bash
# Ver últimos 20 logs
docker compose logs worker --tail=20

# Ver logs en tiempo real
docker compose logs worker --tail=20 -f
```

**Logs esperados del Worker:**
```
{"event": "Received 1 messages from queue", "timestamp": "2026-03-18T18:17:46.512423Z", "level": "info"}
{"job_id": "2351c0b8-cacd-4532-87ad-25193574b8ae", "report_type": "reporte_ventas", "priority": "standard", "event": "job_processing_started", "timestamp": "2026-03-18T18:17:46.512706Z", "level": "info"}
{"job_id": "2351c0b8-cacd-4532-87ad-25193574b8ae", "report_type": "reporte_ventas", "duration_seconds": 24.662, "result_url": "https://reports.example.com/reporte_ventas/...", "event": "job_processing_completed", "timestamp": "2026-03-18T18:18:11.246135Z", "level": "info"}
{"total": 1, "successful": 1, "failed": 0, "event": "batch_processed", "timestamp": "2026-03-18T18:18:11.256475Z", "level": "info"}
```

### Ver Logs de LocalStack

```bash
# Ver últimos 20 logs
docker compose logs localstack --tail=20

# Ver logs en tiempo real
docker compose logs localstack --tail=20 -f
```

### Ver Estado de los Servicios

```bash
docker compose ps
```

**Salida esperada:**
```
NAME                        IMAGE                          COMMAND                  SERVICE      STATUS          PORTS
reto-prosperas-api          reto-prosperas2-app            "uvicorn src.adapters…"   app          Up              0.0.0.0:8000->8000/tcp
reto-prosperas-localstack   localstack/localstack:latest   "docker-entrypoint.sh"   localstack   Up (healthy)    0.0.0.0:4566->4566/tcp
reto-prosperas-worker       reto-prosperas2-worker         "python -m worker.ma…"    worker       Up
```

### Verificar Recursos AWS

```bash
# Listar colas SQS
aws --endpoint-url=http://localhost:4566 sqs list-queues

# Listar tablas DynamoDB
aws --endpoint-url=http://localhost:4566 dynamodb list-tables

# Ver mensajes en la cola (si hay alguno)
aws --endpoint-url=http://localhost:4566 sqs receive-message --queue-url http://localhost:4566/000000000000/report-jobs-queue --max-number-of-messages 10
```

---

## 🔧 Comandos Útiles

### Gestión de Servicios

```bash
# Iniciar todos los servicios
docker compose up -d

# Detener todos los servicios
docker compose down

# Reiniciar un servicio específico
docker compose restart app
docker compose restart worker

# Ver estado de los servicios
docker compose ps

# Ver todos los logs
docker compose logs -f
```

### Verificación de Salud

```bash
# Health check de la API
curl http://localhost:8000/health

# Health check de LocalStack
curl http://localhost:4566/_localstack/health

# Ver métricas del worker
docker compose logs worker --tail=5 | grep health_check
```

### Limpieza

```bash
# Detener y eliminar contenedores
docker compose down

# Detener, eliminar contenedores y volúmenes (¡borra datos!)
docker compose down -v

# Eliminar imágenes
docker rmi reto-prosperas2-app reto-prosperas2-worker
```

---

## 📁 Estructura del Proyecto

```
reto-prosperas2/
├── backend/                    # FastAPI REST API
│   ├── app/
│   │   ├── main.py             # App con exception handlers globales
│   │   ├── config.py           # Configuración desde env
│   │   ├── dependencies.py     # Auth JWT
│   │   ├── exceptions.py       # Excepciones personalizadas
│   │   ├── routers/
│   │   │   └── jobs.py        # Endpoints /jobs, /auth
│   │   ├── schemas/
│   │   │   └── job.py         # Modelos Pydantic v2
│   │   └── services/
│   │       ├── dynamodb.py     # Operaciones DynamoDB
│   │       └── sqs.py          # Operaciones SQS
│   └── tests/                  # Tests con pytest
│
├── worker/                     # Procesador asíncrono
│   ├── main.py                 # Entry point
│   ├── processor.py            # Lógica de procesamiento
│   ├── sqs_client.py          # Cliente SQS async (aiobotocore)
│   ├── dynamodb_client.py     # Cliente DynamoDB async
│   ├── circuit_breaker.py     # Circuit breaker pattern
│   ├── backoff.py             # Exponential backoff
│   ├── config.py              # Configuración
│   └── tests/
│
├── infra/                     # Infraestructura
│   └── init-aws.sh            # Script de inicialización AWS
│
├── .agents/                   # Skills y documentación
│   └── skills/
│
├── Dockerfile                 # Multi-stage Python 3.11-slim
├── docker-compose.yml         # Orquestación de servicios
├── requirements.txt          # Dependencias Python
├── .env.example              # Variables de entorno template
├── .env                      # Variables de entorno (no committed)
├── AGENTS.md                 # Documentación raíz del proyecto
├── PRD.md                    # Requisitos originales
└── README.md                # Este archivo
```

---

## 🔐 Endpoints de la API

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| `GET` | `/health` | No | Health check con estado de dependencias |
| `POST` | `/auth/token` | No | Obtener token JWT para un user_id |
| `POST` | `/jobs` | JWT | Crear un nuevo trabajo |
| `GET` | `/jobs` | JWT | Listar trabajos del usuario (paginado) |
| `GET` | `/jobs/{job_id}` | JWT | Ver detalle de un trabajo |

### Modelo de Trabajo

```json
{
  "job_id": "uuid",
  "user_id": "mi-usuario-123",
  "status": "PENDING | PROCESSING | COMPLETED | FAILED",
  "report_type": "reporte_ventas",
  "created_at": "2026-03-18T18:17:45.749686Z",
  "updated_at": "2026-03-18T18:18:11.213253Z",
  "result_url": "https://reports.example.com/..."
}
```

---

## ⚙️ Variables de Entorno

| Variable | Valor por Defecto | Descripción |
|----------|-------------------|-------------|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | Endpoint de LocalStack |
| `AWS_REGION` | `us-east-1` | Región de AWS |
| `AWS_ACCESS_KEY_ID` | `test` | Credenciales LocalStack |
| `AWS_SECRET_ACCESS_KEY` | `test` | Credenciales LocalStack |
| `DYNAMODB_TABLE_JOBS` | `jobs` | Nombre de la tabla |
| `SQS_QUEUE_URL` | `report-jobs-queue` | Cola principal |
| `SQS_DLQ_URL` | `report-jobs-dlq` | Cola de mensajes fallidos |
| `JWT_SECRET_KEY` | `change-me...` | Clave secreta JWT |
| `JWT_ALGORITHM` | `HS256` | Algoritmo JWT |

---

## ⏭️ Tarea Pospuesta

El **CI/CD Pipeline y Despliegue a AWS Production** está marcado como **PENDING**.

Cuando estés listo para configurarlo, usa la skill disponible:

```
.agents/skills/cicd-aws-production/SKILL.md
```

---

## ✅ Estados Posibles de un Trabajo

```
PENDING ──────► PROCESSING ──────► COMPLETED
                      │
                      └──► FAILED ──► DLQ (Dead Letter Queue)
```

---

## 🎯 Características Implementadas

- [x] FastAPI REST API con Pydantic v2
- [x] Autenticación JWT stateless (HS256)
- [x] DynamoDB con GSI en user_id
- [x] SQS con Dead Letter Queue
- [x] Workers asíncronos con asyncio.gather
- [x] Procesamiento concurrente (mínimo 2 trabajos)
- [x] Procesamiento simulado (5-30 segundos)
- [x] Circuit Breaker pattern
- [x] Exponential Backoff
- [x] Priority Queues
- [x] Structured Logging
- [x] Health endpoint con métricas de dependencias
- [x] Exception handlers globales

---

¡El sistema está listo para desarrollo y pruebas! 🚀
