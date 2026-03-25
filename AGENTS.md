# AGENTS.md - Project Root
## PROJECT OVERVIEW
**Name:** Reto Prosperas - Report Job Processing System  
**Type:** Async Job Processing Platform  
**Core:** FastAPI REST API + SQS Workers + DynamoDB + WebSocket Notifications
---
## ARCHITECTURE
### Production (AWS)
```
CloudFront/S3 (Frontend SPA)
    │
    ├──► REST API ──► API Gateway ──► ALB ──► ECS Fargate (FastAPI)
    │      │ Rate Limit: 100 req/sec
    │      │ Burst: 200
    │      │ Monthly: 10k req
    │
    └──► WebSocket ──► CloudFront ──► ALB ──► ECS Fargate (FastAPI WebSocket Manager)
                                                       ▲
                                                       │
                                                  Worker (ECS Fargate)
                                                       │
                                               SQS ──► DynamoDB
```
### Key URLs
| Component | Production URL |
|------------|----------------|
| Frontend | `https://<cloudfront>.cloudfront.net` |
| REST API | `https://<api-gw>.amazonaws.com/prod/jobs` |
| WebSocket | `wss://<cloudfront>.cloudfront.net/ws/jobs` |
### Rate Limiting Configuration
| Setting | Value | Description |
|---------|-------|-------------|
| **Rate Limit** | 100 req/sec | Requests per second |
| **Burst Limit** | 200 | Burst capacity |
| **Monthly Quota** | 10,000 req/month | Monthly request limit |
| **API Key** | `harrison-api-key` | Required for all REST endpoints (except `/health`) |
---
## MODULE STRUCTURE
| Directory | Owner | Purpose |
|-----------|-------|---------|
| `/backend/**` | @backend-developer | FastAPI, DynamoDB, SQS, Worker |
| `/frontend/**` | @frontend-developer | React SPA, WebSocket client |
| `/infra/**` | @infra-devops | CDK, ECS, ALB, CloudFront |
| `/.github/**` | @infra-devops | CI/CD GitHub Actions |
---
## KEY FILES
### Backend
- `backend/src/adapters/primary/fastapi/routes/ws_routes.py` - WebSocket endpoint `/ws/jobs`
- `backend/src/adapters/primary/fastapi/routes/notify.py` - Internal notification endpoint
- `backend/src/services/websocket_manager.py` - WebSocket connection manager
- `backend/worker/processor.py` - Job processor, calls `/internal/notify`
- `backend/worker/config.py` - Worker config including `API_BASE_URL`
### Infrastructure
- `infra/stacks/compute_stack.py` - ECS Fargate services, ALB
- `infra/stacks/api_stack.py` - API Gateway REST
- `infra/stacks/data_stack.py` - DynamoDB, SQS
### CI/CD
- `.github/workflows/deploy.yml` - Deployment pipeline
- `.github/workflows/ci.yml` - CI pipeline
---
## WEBSOCKET FLOW
### Connection
```
Frontend → wss://<cloudfront>.cloudfront.net/ws/jobs?user_id={id}&token={jwt}
```
### Notification Flow
```
1. Worker updates job status in DynamoDB
2. Worker POSTs to http://<ALB>/internal/notify
3. FastAPI WebSocketManager broadcasts to connected clients
4. Frontend receives: {"type": "job_update", "data": {...}}
```
### Worker Configuration
```python
# infra/stacks/compute_stack.py - Worker environment
environment={
    "API_BASE_URL": f"http://{self.api_service.load_balancer.load_balancer_dns_name}",
    # ... other vars
}
```
---
## GRACEFUL SHUTDOWN
### Descripción:
Implementación de shutdown graceful para el worker que asegura:
- Jobs activos completan antes del cierre
- Conexiones (SQS, DynamoDB, HTTP) se cierran correctamente
- Timeout de seguridad evita bloqueos infinitos
### Configuración:
| Timeout | Valor | Propósito |
|---------|-------|-----------|
| Shutdown total | 30 segundos | signal.alarm timeout |
| Esperar jobs | 10 segundos | asyncio.wait() |
### Archivos:
- `backend/worker/main.py` - Signal handlers, timeout handler
- `backend/worker/processor.py` - stop() con espera de jobs activos
- `backend/worker/tests/test_processor.py` - Tests de graceful shutdown
### Tests:
- test_stop_waits_for_active_jobs
- test_stop_timeout_forces_shutdown
- test_stop_logs_active_jobs
- test_connections_closed_on_stop
- test_active_tasks_tracked_during_processing
---
## ENVIRONMENT VARIABLES
### Worker (ECS)
| Variable | Source | Description |
|----------|--------|-------------|
| `API_BASE_URL` | CDK (ALB DNS) | Worker calls API for notifications |
| `DYNAMODB_TABLE_JOBS` | CDK | Jobs table name |
| `SQS_QUEUE_URL` | CDK | Main queue URL |
| `AWS_REGION` | CDK | AWS region |
### Frontend Build
| Variable | Source | Description |
|----------|--------|-------------|
| `VITE_API_URL` | GitHub Workflow (API Gateway) | REST API URL |
| `VITE_WS_URL` | GitHub Workflow (CloudFront URL) | WebSocket URL |
---
## CDK STACKS
| Stack | Resources |
|-------|-----------|
| `harrison-data-stack` | DynamoDB tables, SQS queues, VPC, ECS Cluster |
| `harrison-compute-stack` | ECR, ECS Fargate (API + Worker), ALB |
| `harrison-api-stack` | API Gateway REST, Rate Limiting (100 req/sec, burst 200) |
| `harrison-cdn-stack` | S3, CloudFront, OAI, WebSocket routing |
---
## DEPLOYMENT PIPELINE
```
build-ecr → cdk-synth → build-frontend → deploy-cdk → deploy-frontend → verify
```
### cdk-synth Outputs
- `api-url` - API Gateway URL for REST
- `alb-url` - ALB URL for WebSocket
- `frontend-bucket` - S3 bucket name
- `cloudfront-id` - CloudFront distribution ID
### build-frontend
```yaml
VITE_API_URL: ${{ needs.cdk-synth.outputs.api-url }}  # API Gateway
VITE_WS_URL: ${{ needs.cdk-synth.outputs.alb-url }}  # ALB (ws:// converted)
```
---
## TASK DELEGATION
### @backend-developer
- FastAPI routes and business logic
- DynamoDB repository
- SQS queue operations
- Worker job processor
- WebSocket manager
### @frontend-developer
- React components and pages
- API service (Axios)
- WebSocket hook and connection
- State management
### @infra-devops
- CDK infrastructure code
- Docker configurations
- GitHub Actions workflows
- AWS deployments
---
## VERIFICATION COMMANDS
### Local
```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/auth/token -d '{"user_id":"test"}'
```
### AWS (CLI)
```bash
# Get ALB URL
aws cloudformation describe-stacks --stack-name harrison-compute-stack \
  --query 'Stacks[0].Outputs[?OutputKey==`APIServiceUrl`].OutputValue'
# Health check
curl $(aws cloudformation describe-stacks --stack-name harrison-api-stack \
  --query 'Stacks[0].Outputs[?OutputKey==`APIUrl`].OutputValue' --output text)/health
```
---
## STATUS
| Component | Status |
|-----------|--------|
| Local Development | ✅ Working |
| WebSocket via ALB | ✅ Implemented |
| AWS Production | ✅ Implemented |
---
## PREVIOUS CHANGES
### 2026-03-25: Worker API_BASE_URL fix
- Removed port 8000 from `API_BASE_URL` in `infra/stacks/compute_stack.py`
- Worker now calls ALB on port 80 (HTTP), ALB forwards to container port 8000
### 2026-03-22: WebSocket via ALB
- Added `API_BASE_URL` to Worker environment in `infra/stacks/compute_stack.py`
- Updated `.github/workflows/deploy.yml` to use ALB URL for `VITE_WS_URL`
- WebSocket now connects directly to ALB instead of API Gateway
- Worker can notify API via `/internal/notify` endpoint
