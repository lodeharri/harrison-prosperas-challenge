# AGENTS.md - Project Root

## Project Overview

**Project Name:** Prosperas Challenge - Async Job Processing System  
**Type:** Asynchronous Job Processing Platform  
**Core Functionality:** FastAPI REST API that accepts report job requests, queues them via AWS SQS, processes them asynchronously with workers, and persists job state in AWS DynamoDB.

---

## Module Structure

```
harrison-prosperas-challenge/
├── infra/                     # AWS CDK Infrastructure
├── backend/                  # FastAPI REST API + Worker
├── frontend/                # React SPA (Vite + TypeScript)
├── .github/                 # CI/CD workflows
├── docker-compose.yml       # Local development orchestration
└── AGENTS.md               # This file
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| REST API | FastAPI, Pydantic v2, JWT |
| Database | AWS DynamoDB |
| Queue | AWS SQS |
| Workers | Python asyncio |
| Infrastructure | Docker, LocalStack |
| Observability | CloudWatch Logs + Metrics |
| CI/CD | GitHub Actions |

---

## Environment Detection

The application detects environment based on `AWS_ENDPOINT_URL`:

| Environment | `AWS_ENDPOINT_URL` | Behavior |
|-------------|-------------------|----------|
| LocalStack (dev) | `http://localhost:4566` | Uses local endpoints |
| AWS Production | NOT SET | Uses real AWS services |

---

## Task List

### Completed
- [x] Local Development (Docker, LocalStack, Zero-config startup)
- [x] REST API (all endpoints: POST/GET /jobs, JWT auth, health, CORS)
- [x] Persistence (DynamoDB with GSI on user_id)
- [x] Workers (async, DLQ, circuit breaker, exponential backoff)
- [x] Bonus: Priority queues, WebSocket, CloudWatch, Tests (92%), Idempotency
- [x] CI/CD Pipeline (GitHub Actions + AWS deployment via CDK)
- [x] CDK v2 Compatibility (CloudFront API fixes, enum conversions)
- [x] AWS Resources Cleanup (ready for fresh deployment)
- [x] GitHub Workflow Improvements (robust CDK outputs extraction)
- [x] GitHub Workflow Robustness Update (pre-deployment checks, error handling)
- [x] Infrastructure & DevOps Setup (Docker, LocalStack, CDK bootstrap fix)

### Pending
- [ ] AWS Production deployment from scratch (trigger GitHub Actions with configured secrets)

---

## Deployment Status

| Environment | Status |
|-------------|--------|
| Local (Docker) | ✅ Ready |
| AWS Production | ✅ CDK Synth Working (4 stacks) |

---

## Project Status
✅ **AWS Clean:** Verified no existing resources (CloudFormation, ECR, S3, CloudFront, DynamoDB, SQS, App Runner, API Gateway).  
✅ **Workflow Optimized:** `deploy.yml` reduced from 1131 to 511 lines (54% reduction).  
✅ **Bootstrap Fixed:** Simplified bootstrap script resolves S3 bucket error.  
✅ **Documentation Synthesized:** `AGENTS.md` converted to English, reduced from 408 to 173 lines.  
✅ **CDK Ready:** 4 stacks synthesize correctly (Data, Compute, API, CDN).  
✅ **CI/CD Operational:** GitHub Actions pipeline ready for zero-deployment.  
✅ **Local Verification Complete:** Docker Compose works correctly, all services operational.  
✅ **Workflow Portable:** `deploy.yml` updated with simple auto-bootstrap.  
✅ **CDK Bootstrap Authentication Fixed:** Fixed app.py environment context function to properly pass app instance.  
🚀 **Ready for Deployment:** Configure GitHub secrets/variables and trigger deployment.

---

## Bonus Challenges

| ID | Feature | Status |
|----|---------|--------|
| B1 | Priority queues (high/standard by report type) | ✅ |
| B3 | WebSocket notifications for real-time updates | ✅ |
| B5 | CloudWatch observability (structured logging + metrics) | ✅ |
| B6 | Test coverage ≥70% (backend only) | ✅ (92%) |
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

## CI/CD Workflows

### CI Pipeline (`.github/workflows/ci.yml`)
- **Trigger:** Push to any branch + PR
- **Jobs:** lint-backend, typecheck-backend, test-backend, lint-frontend, build-frontend

### Deploy Pipeline (`.github/workflows/deploy.yml`)
- **Trigger:** Push to `master` only
- **Jobs:** 
  1. `build-ecr` - Build and push Docker to ECR
  2. `cdk-synth` - Synthesize CDK templates
  3. `build-frontend` - Build frontend with production API URL
  4. `deploy-cdk` - Deploy 4 stacks to AWS
  5. `deploy-frontend` - Upload to S3, invalidate CloudFront
  6. `verify` - Health check and smoke test

### Required GitHub Secrets
| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_ACCOUNT_ID` | AWS account ID |
| `JWT_SECRET_KEY` | JWT signing key |

### Required GitHub Variables
| Variable | Description | Value |
|----------|-------------|-------|
| `CDK_BOOTSTRAPPED` | If CDK already bootstrapped | `false` |

---

## Next Steps

1. **Configure GitHub Secrets** (Settings > Secrets > Actions):
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ACCOUNT_ID`, `JWT_SECRET_KEY`

2. **Configure GitHub Variables** (Settings > Variables > Actions):
   - `CDK_BOOTSTRAPPED`: `false`

3. **Merge to master** or push to master branch

4. **Monitor deployment** via GitHub Actions

### Estimated Monthly Cost: < $15 USD

| Stack | AWS Resources | Estimated Cost |
|-------|--------------|----------------|
| **Data Stack** | DynamoDB (2 tables), SQS (3 queues) | ~$0-1/month |
| **Compute Stack** | ECR, App Runner (2 services), Secrets Manager | ~$5-7/month |
| **API Stack** | API Gateway, Rate Limiting, API Key | ~$0-5/month |
| **CDN Stack** | S3, CloudFront, OAI | ~$0-1/month |
| **TOTAL** | | **~$5-14/month** |

---

## Module AGENTS.md Files

Each module has its own detailed AGENTS.md:
- `infra/AGENTS.md`: CDK stacks, AWS resources, deployment guide
- `backend/AGENTS.md`: API, Worker, DynamoDB, SQS, tests, observability
- `frontend/AGENTS.md`: React SPA, components, hooks, WebSocket integration
