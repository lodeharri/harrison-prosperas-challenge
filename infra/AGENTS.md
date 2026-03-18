# AGENTS.md - Infrastructure Module

**Module:** Docker & LocalStack Configuration  
**Directory:** `/home/harri/development/projects/reto-prosperas2/infra`  
**Skill:** `infra-local-bootstrap`  
**Status:** ✅ IMPLEMENTED

---

## Quick Start

```bash
# Copy environment template
cp .env.example .env

# Start all services
docker compose up -d

# Verify LocalStack health
curl http://localhost:4566/_localstack/health

# View logs
docker compose logs -f

# Stop services
docker compose down
```

---

## Docker Network Structure

| Service | Container Name | External Port | Internal Network |
|---------|---------------|--------------|-----------------|
| LocalStack | `reto-prosperas-localstack` | 4566 | `reto-network` |
| API | `reto-prosperas-api` | 8000 | `reto-network` |
| Worker | `reto-prosperas-worker` | - | `reto-network` |
| Init | `reto-prosperas-init` | - | `reto-network` |

---

## Mocked AWS Services

| Service | Purpose | Queue/Table | Port |
|---------|---------|-------------|------|
| SQS | Main job queue | `jobs-queue` | 4566 |
| SQS | Dead Letter Queue | `jobs-queue-dlq` | 4566 |
| SQS | Priority queue | `jobs-queue-priority` | 4566 |
| DynamoDB | Job persistence | `jobs` table + 2 GSIs | 4566 |

### DynamoDB Table Schema

**Table:** `jobs`  
**Partition Key:** `job_id` (String)

**Global Secondary Indexes:**

| Index Name | Partition Key | Sort Key | Purpose |
|------------|--------------|----------|---------|
| `user_id-created_at-index` | `user_id` | `created_at` | List user's jobs |
| `status-created_at-index` | `status` | `created_at` | Filter by status |

**Attributes:** `job_id`, `user_id`, `status`, `report_type`, `created_at`, `updated_at`, `result_url`, `ttl`

### SQS Queue Configuration

| Queue | VisibilityTimeout | MaxReceiveCount | RetentionPeriod |
|-------|------------------|-----------------|-----------------|
| `jobs-queue` | 60s | 3 | 24 hours |
| `jobs-queue-dlq` | 60s | - | 14 days |
| `jobs-queue-priority` | 30s | - | 24 hours |

---

## Files Created

| File | Purpose |
|------|---------|
| `../Dockerfile` | Multi-stage Python 3.11-slim build |
| `../docker-compose.yml` | Service orchestration |
| `init-aws.sh` | AWS resource initialization (auto-run on LocalStack start) |
| `../.env.example` | Environment variables template |

---

## AWS CLI Commands (Manual Verification)

```bash
# Set endpoint for awslocal
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# List SQS queues
aws sqs list-queues

# Get queue URL
aws sqs get-queue-url --queue-name jobs-queue

# List DynamoDB tables
aws dynamodb list-tables

# Describe jobs table
aws dynamodb describe-table --table-name jobs

# Describe GSI
aws dynamodb describe-table --table-name jobs --query 'Table.GlobalSecondaryIndexes'
```

---

## Environment Variables

All variables are documented in `../.env.example`. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | LocalStack endpoint |
| `AWS_REGION` | `us-east-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | `test` | LocalStack credentials |
| `AWS_SECRET_ACCESS_KEY` | `test` | LocalStack credentials |
| `DYNAMODB_TABLE_JOBS` | `jobs` | DynamoDB table name |
| `SQS_QUEUE_URL` | Auto-generated | Main queue URL |
| `SQS_DLQ_URL` | Auto-generated | Dead letter queue URL |
| `SQS_PRIORITY_QUEUE_URL` | Auto-generated | Priority queue URL |
| `JWT_SECRET_KEY` | (Generate secure) | JWT signing key |

---

## Validation Checklist

After `docker compose up`, verify:

- [x] `curl http://localhost:4566/_localstack/health` returns 200
- [x] SQS queues created: `aws sqs list-queues --endpoint-url http://localhost:4566`
- [x] DynamoDB table exists: `aws dynamodb describe-table --table-name jobs --endpoint-url http://localhost:4566`
- [x] No hardcoded secrets in repository (all use `.env` template)
- [x] Init service completes successfully before app starts

---

## Dependencies

```
LocalStack (standalone)
    └── init (waits for LocalStack, creates resources)
    └── app (waits for init, runs FastAPI)
    └── worker (waits for app, processes jobs)
```

---

## References

- Infrastructure Skill: `../.agents/skills/infra-local-bootstrap/SKILL.md`
- Root AGENTS.md: `../AGENTS.md`
