# AGENTS.md - Infrastructure Module

**Project:** Reto Prosperas - Report Job Processing System  
**Directory:** `infra/`  
**Skill:** `cicd-aws-production`  
**Status:** ✅ CDK v2 - SYNTH SUCCESS - GITHUB ACTIONS READY

---

## Context

This is the **Infrastructure Module** of the Reto Prosperas project. The full project context is documented in the root `AGENTS.md`.

### What is Reto Prosperas?
A system that allows users to create report jobs, processes them asynchronously via AWS SQS workers, and receives real-time notifications via WebSocket when jobs complete.

### What is this module?
Infrastructure as Code (IaC) using **AWS CDK v2** that provisions all AWS resources needed for the system.

## Scope

| Component | Responsibility |
|-----------|----------------|
| **Data Stack** | DynamoDB tables (jobs, idempotency), SQS queues (main, DLQ, priority) |
| **Compute Stack** | ECS Fargate services (API + Worker), ECR repository, IAM roles, Secrets Manager |
| **API Stack** | API Gateway REST, rate limiting (100 req/sec, burst 200), API key |
| **CDN Stack** | S3 bucket for frontend, CloudFront distribution, WebSocket proxy |
| **CI/CD** | GitHub Actions workflow for automated deployment |
| **NOT** | Does NOT build the Docker image or frontend (done in GitHub Actions) |

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     AWS Account                                  │
│                                                                  │
│  harrison-data-stack                                             │
│  ┌─────────────────┐  ┌─────────────────┐                       │
│  │ DynamoDB        │  │ SQS            │                       │
│  │ - harrison-jobs │  │ - jobs-queue    │                       │
│  │ - harrison-idem │  │ - jobs-dlq      │                       │
│  └─────────────────┘  │ - jobs-priority │                       │
│                       └─────────────────┘                       │
│          ↓                                                         │
│  harrison-compute-stack                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ ECS Fargate                                                │    │
│  │   ┌─────────────┐    ┌─────────────┐                     │    │
│  │   │ API Service │    │ Worker      │                     │    │
│  │   │ (FastAPI)   │    │ (Processor) │                     │    │
│  │   └──────┬──────┘    └──────┬──────┘                     │    │
│  │          ↓                   ↓                             │    │
│  │   ┌──────────────────────────────────────────────┐       │    │
│  │   │           Application Load Balancer           │       │    │
│  │   └──────────────────────────────────────────────┘       │    │
│  └─────────────────────────────────────────────────────────┘    │
│          ↓                                                         │
│  harrison-api-stack                                               │
│  ┌─────────────────┐  ┌─────────────────┐                        │
│  │ API Gateway     │  │ Rate Limiting   │                        │
│  │ - /jobs         │  │ - 100 req/sec   │                        │
│  │ - /health       │  │ - Burst 200     │                        │
│  │ - /auth/token   │  │ - API Key       │                        │
│  └────────┬────────┘  └─────────────────┘                        │
│           ↓                                                        │
│  harrison-cdn-stack                                               │
│  ┌─────────────────┐  ┌─────────────────┐                      │
│  │ S3 (Frontend)    │  │ CloudFront      │                      │
│  │ - Static assets │  │ - Global CDN    │                      │
│  │ - OAI protected  │  │ - WS proxy      │                      │
│  └─────────────────┘  └─────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

## Stack Dependencies

```
harrison-data-stack
    └── harrison-compute-stack (needs queue URLs, table names)
            └── harrison-api-stack (needs ECS ALB endpoint)
                    └── harrison-cdn-stack (needs API URL for frontend)
```

## If You Need To...

| Task | Go To |
|------|-------|
| Modify DynamoDB tables | `stacks/data_stack.py` |
| Modify SQS queues | `stacks/data_stack.py` |
| Modify ECS Fargate services | `stacks/compute_stack.py` |
| Modify ECR repository | `stacks/compute_stack.py` |
| Modify IAM roles | `stacks/compute_stack.py` |
| Modify Secrets Manager | `stacks/compute_stack.py` |
| Modify API Gateway | `stacks/api_stack.py` |
| Modify rate limiting | `stacks/api_stack.py` |
| Modify API key | `stacks/api_stack.py` |
| Modify S3 bucket | `stacks/cdn_stack.py` |
| Modify CloudFront | `stacks/cdn_stack.py` |
| Modify deployment pipeline | `.github/workflows/deploy.yml` |
| Modify stack orchestration | `app.py` |
| Modify CDK configuration | `cdk.json` |

---

## Directory Structure

```
infra/
├── app.py                      # CDK App entry point, stack orchestration
├── requirements.txt           # aws-cdk-lib>=2.0.0, constructs
├── cdk.json                    # {"app": "python app.py"}
├── package.json                # Node.js CDK dependencies
├── stacks/
│   ├── __init__.py            # Stack exports
│   ├── data_stack.py          # DynamoDB + SQS resources
│   ├── compute_stack.py       # ECS Fargate (API + Worker) + ECR + IAM
│   ├── api_stack.py           # API Gateway + Rate Limiting
│   └── cdn_stack.py           # S3 + CloudFront
└── README.md                  # Full deployment guide
```

## AWS Resources Created

### 1. Data Stack (`harrison-data-stack`)

| Resource | Name | Type | Config |
|----------|------|------|--------|
| DynamoDB Table | `harrison-jobs` | PK: job_id | GSI: user_id-created_at |
| DynamoDB Table | `harrison-idempotency` | PK: idempotency_key | TTL: expires_at |
| SQS Queue | `harrison-jobs-queue` | DLQ: harrison-jobs-dlq | maxReceiveCount: 3 |
| SQS Queue | `harrison-jobs-dlq` | 14-day retention | - |
| SQS Queue | `harrison-jobs-priority` | 30s visibility | High-priority jobs |

### 2. Compute Stack (`harrison-compute-stack`)

| Resource | Name | Type | Config |
|----------|------|------|--------|
| ECR Repository | `harrison-prospera-challenge` | Docker images | Scan on push |
| Secrets Manager | `harrison-jwt-secret` | 64-char key | Auto-generated |
| IAM Role | `APIServiceRole` | ECS Fargate | DynamoDB + SQS + Secrets |
| IAM Role | `WorkerServiceRole` | ECS Fargate | DynamoDB (jobs + idempotency) + SQS (receive/delete/change visibility) |
| ECS Fargate | `harrison-api` | ALB Service | 0.5 vCPU, 1 GB, port 8000 |
| ECS Fargate | `harrison-worker` | Service | 0.25 vCPU, 0.5 GB |

#### Worker Auto Scaling

The Worker service implements **target tracking** auto scaling based on SQS queue depth:

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Scaling Type** | Target Tracking | Maintains a target value for the metric |
| **Metric** | SQS `ApproximateNumberOfMessagesVisible` | Queue depth |
| **Min Tasks** | 1 | Minimum worker instances |
| **Max Tasks** | 8 | Maximum worker instances |
| **Target Value** | 25 messages/task | Desired messages per worker task |

This configuration ensures that as message volume increases, additional worker tasks are automatically spawned to handle the load, maintaining consistent processing throughput.

### 3. API Stack (`harrison-api-stack`)

| Resource | Name | Type | Config |
|----------|------|------|--------|
| API Gateway | `harrison-api-gw` | REST | Regional endpoint |
| Resource | `/jobs` | POST, GET | ECS ALB integration |
| Resource | `/jobs/{job_id}` | GET | ECS ALB integration |
| Resource | `/health` | GET | No auth |
| Resource | `/auth` | POST | Token generation |
| Usage Plan | `harrison-rate-limit` | 100 req/sec | Burst 200 |
| API Key | `harrison-api-key` | Key | Auto-generated |

### 4. CDN Stack (`harrison-cdn-stack`)

| Resource | Name | Type | Config |
|----------|------|------|--------|
| S3 Bucket | `harrison-frontend` | Static hosting | OAI protected |
| CloudFront | `harrison-frontend-cdn` | Distribution | Global distribution |
| OAI | Origin Access Identity | Security | S3 protection |
| Function | `spa-routing` | CloudFront | SPA routing |

## Environment Variables for ECS Fargate

### API Service

```python
environment={
    "AWS_REGION": "us-east-1",
    "AWS_ENDPOINT_URL": "",  # Empty for real AWS
    "DYNAMODB_TABLE_JOBS": "harrison-jobs",
    "DYNAMODB_TABLE_IDEMPOTENCY": "harrison-idempotency",
    "SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/ACCOUNT/harrison-jobs-queue",
    "SQS_QUEUE_NAME": "harrison-jobs-queue",
    "SQS_DLQ_URL": "https://sqs.us-east-1.amazonaws.com/ACCOUNT/harrison-jobs-dlq",
    "SQS_DLQ_NAME": "harrison-jobs-dlq",
    "SQS_PRIORITY_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/ACCOUNT/harrison-jobs-priority",
    "SQS_PRIORITY_QUEUE_NAME": "harrison-jobs-priority",
    "JWT_SECRET_KEY": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:harrison-jwt-secret",
    "LOG_LEVEL": "INFO",
}
```

### Worker Service

Same as API + `API_BASE_URL` for notifying API of status changes.

---

## Deployment Pipeline Flow

```
┌─────────────┐
│ build-ecr   │ → Builds and pushes Docker image to ECR
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│ cdk-synth   │────▶│build-frontend│ → Builds frontend with API URL
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 │
                 ▼
          ┌─────────────┐
          │ deploy-cdk  │ → Deploys all CDK stacks
          └──────┬──────┘
                 │
                 ▼
          ┌─────────────┐
          │deploy-frontend│ → Uploads to S3, invalidates CloudFront
          └──────┬──────┘
                 │
                 ▼
          ┌─────────────┐
          │   verify    │ → Health check + smoke test
          └─────────────┘
```

---

## GitHub Actions Secrets & Variables

### Required Secrets
| Secret | Purpose |
|--------|---------|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_ACCOUNT_ID` | AWS account ID |
| `JWT_SECRET_KEY` | JWT signing key |

### Required Variables
| Variable | Purpose | Default |
|----------|---------|---------|
| `CDK_BOOTSTRAPPED` | Skip bootstrap if already done | `false` |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution ID | (post-deploy) |

---

## Quick Start

```bash
# Install CDK
npm install -g aws-cdk

# Set AWS credentials
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_DEFAULT_REGION="us-east-1"

# Bootstrap (one-time)
cdk bootstrap aws://ACCOUNT/REGION

# Deploy all stacks
cdk deploy --all
```

## CDK Commands

```bash
# List stacks
cdk list

# Deploy all
cdk deploy --all

# Deploy specific
cdk deploy harrison-data-stack

# Synthesize (dry run)
cdk synth

# Show diff
cdk diff

# Destroy all
cdk destroy --all
```

## AWS CLI Verification

```bash
# List stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE

# Get stack outputs
aws cloudformation describe-stacks \
  --stack-name harrison-data-stack \
  --query 'Stacks[0].Outputs'

# Check DynamoDB
aws dynamodb list-tables

# Check SQS
aws sqs list-queues

# Check ECS
aws ecs list-services --cluster harrison-cluster

# Check API Gateway
aws apigateway get-rest-apis
```

## Local Development

For local development with LocalStack, see root `AGENTS.md`:
- `docker compose up` starts LocalStack + API + Worker + Frontend
- Backend uses `AWS_ENDPOINT_URL=http://localhost:4566` for local resources

---

## Validation Checklist

After deployment, verify:

- [ ] `aws cloudformation describe-stacks --stack-status-filter CREATE_COMPLETE`
- [ ] DynamoDB tables exist: `aws dynamodb list-tables`
- [ ] SQS queues exist: `aws sqs list-queues`
- [ ] ECR repository exists: `aws ecr describe-repositories`
- [ ] ECS Fargate services running: `aws ecs list-services --cluster harrison-cluster`
- [ ] API Gateway configured: `aws apigateway get-rest-apis`
- [ ] CloudFront distribution active: `aws cloudfront list-distributions`
- [ ] Secrets Manager secret exists: `aws secretsmanager list-secrets`

## Cleanup

```bash
cdk destroy --all
```

**Warning:** This deletes all data!

---

## CDK v2 Compatibility Notes

### CloudFront (cdn_stack.py)
- Uses `OriginProperty`, `DefaultCacheBehaviorProperty` (not `CfnDistribution.SourceConfigProperty`)
- Enum values as strings: `PriceClass.PRICE_CLASS_100.value`, `ViewerProtocolPolicy.REDIRECT_TO_HTTPS.value`

### ECS Fargate (compute_stack.py)
- Uses `ApplicationLoadbalancedFargateService`, `FargateService` - fully compatible with CDK v2

### API Gateway (api_stack.py)
- Uses high-level constructs: `apigateway.RestApi`, `UsagePlan`, `ApiKey` - fully compatible with CDK v2

---

## References

- CDK Documentation: https://docs.aws.amazon.com/cdk/
- ECS Fargate: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/getting-started-fargate.html
- CDK Best Practices: https://docs.aws.amazon.com/cdk/latest/guide/best-practices.html

---

## Recent Changes

### 2026-03-25: Worker IAM Role Permissions Update
- Added `self.data_stack.idempotency_table.table_arn` to DynamoDB resources in `_create_worker_role()` function
- Added `sqs:ChangeMessageVisibility` action to SQS permissions for worker role
- Worker now has full access to idempotency table and can change message visibility for long-running jobs