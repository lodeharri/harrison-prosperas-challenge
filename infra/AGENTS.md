# AGENTS.md - Infrastructure Module

**Module:** AWS CDK Infrastructure  
**Directory:** `/home/harri/development/projects/harrison-prosperas-challenge/infra`  
**Skill:** `cicd-aws-production`  
**Status:** ✅ CDK v2 API FIXED - SYNTH SUCCESS

---

## CDK v2 API Compatibility Notes

### CloudFront (cdn_stack.py)

**Changes Applied:**
- Replaced `CfnDistribution.SourceConfigProperty` with separate `origins` (list of `OriginProperty`) and `default_cache_behavior` (`DefaultCacheBehaviorProperty`)
- Converted enum values to strings: `PriceClass.PRICE_CLASS_100.value`, `ViewerProtocolPolicy.REDIRECT_TO_HTTPS.value`
- Updated `originAccessIdentityName` → `originAccessIdentityId` (deprecated attribute fix)
- Changed `attr_function_arn` → `function_arn` for CloudFront Function

### App Runner (compute_stack.py)

**Note:** Uses `CfnAutoScalingConfiguration` with `CfnService` (low-level L1 constructs) which are compatible with CDK v2.

### API Gateway (api_stack.py)

**Note:** Uses high-level constructs (`apigateway.RestApi`, `UsagePlan`, `ApiKey`) which are fully compatible with CDK v2.

### Environment Configuration (app.py)

**Fix Applied:**
- Added default account (`123456789012`) for `cdk synth` when `CDK_ACCOUNT` is not set

---

## Quick Start

### Prerequisites

```bash
# 1. Install CDK
npm install -g aws-cdk

# 2. Set AWS credentials
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_DEFAULT_REGION="us-east-1"

# 3. Bootstrap environment (one-time)
cdk bootstrap aws://ACCOUNT/REGION

# 4. Deploy all stacks
cdk deploy --all
```

---

## Directory Structure

```
infra/
├── app.py                      # CDK App entry point
├── requirements.txt           # aws-cdk-lib>=2.0.0, constructs
├── cdk.json                    # {"app": "python app.py"}
├── stacks/
│   ├── __init__.py            # Stack exports
│   ├── data_stack.py          # DynamoDB + SQS
│   ├── compute_stack.py       # App Runner (API + Worker)
│   ├── api_stack.py           # API Gateway + Rate Limiting
│   └── cdn_stack.py           # S3 + CloudFront
└── README.md                  # Full deployment guide
```

---

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
| IAM Role | `APIServiceRole` | App Runner | DynamoDB + SQS + Secrets |
| IAM Role | `WorkerServiceRole` | App Runner | DynamoDB + SQS |
| App Runner | `harrison-api` | Service | 1 vCPU, 2 GB, port 8000 |
| App Runner | `harrison-worker` | Service | 1 vCPU, 2 GB |

### 3. API Stack (`harrison-api-stack`)

| Resource | Name | Type | Config |
|----------|------|------|--------|
| API Gateway | `harrison-api-gw` | REST | Regional endpoint |
| Resource | `/jobs` | POST, GET | App Runner integration |
| Resource | `/jobs/{job_id}` | GET | App Runner integration |
| Resource | `/health` | GET | No auth |
| Resource | `/auth` | POST | Token generation |
| Usage Plan | `harrison-rate-limit` | 100 req/min | Burst 200 |
| API Key | `harrison-api-key` | Key | Auto-generated |

### 4. CDN Stack (`harrison-cdn-stack`)

| Resource | Name | Type | Config |
|----------|------|------|--------|
| S3 Bucket | `harrison-frontend` | Static hosting | OAI protected |
| CloudFront | `harrison-frontend-cdn` | Distribution | Price Class 100 |
| OAI | Origin Access Identity | Security | S3 protection |
| Function | `spa-routing` | CloudFront | SPA routing |

---

## Environment Variables for App Runner

### API Service

```python
environment={
    "AWS_REGION": "us-east-1",
    "AWS_ENDPOINT_URL": "",  # Empty for real AWS
    "DYNAMODB_TABLE_JOBS": "harrison-jobs",
    "DYNAMODB_TABLE_IDEMPOTENCY": "harrison-idempotency",
    "SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/ACCOUNT/harrison-jobs-queue",
    "SQS_DLQ_URL": "https://sqs.us-east-1.amazonaws.com/ACCOUNT/harrison-jobs-dlq",
    "SQS_PRIORITY_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/ACCOUNT/harrison-jobs-priority",
    "JWT_SECRET_KEY": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:harrison-jwt-secret",
    "LOG_LEVEL": "INFO",
}
```

### Worker Service

Same as API + `SQS_DLQ_URL` for sending failed messages.

---

## Deployment Commands

```bash
# Set environment
export CDK_ACCOUNT="123456789012"
export CDK_REGION="us-east-1"

# Bootstrap (one-time)
cdk bootstrap aws://$CDK_ACCOUNT/$CDK_REGION

# Deploy all stacks
cdk deploy --all

# Deploy specific stack
cdk deploy harrison-data-stack

# Synthesize (dry run)
cdk synth

# Show diff
cdk diff

# List stacks
cdk list
```

---

## Post-Deployment Steps

### 1. Build and Push Docker Images

```bash
# Get ECR URI
REPO_URI=$(aws cloudformation describe-stacks \
    --stack-name harrison-compute-stack \
    --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
    --output text)

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin $REPO_URI

# Build and push
docker build -t api:latest ../backend
docker tag api:latest $REPO_URI:latest
docker push $REPO_URI:latest
```

### 2. Deploy Frontend

```bash
# Set build vars
export VITE_API_URL="https://<api-id>.execute-api.us-east-1.amazonaws.com/prod"
export VITE_WS_URL="wss://<api-id>.execute-api.us-east-1.amazonaws.com/prod/ws"

# Build and deploy
cd ../frontend && npm run build
aws s3 sync dist/ s3://harrison-frontend --delete
aws cloudfront create-invalidation --distribution-id <id> --paths "/*"
```

---

## CDK Context Options

```json
{
  "stackPrefix": "harrison",
  "environment": "production",
  "removalPolicy": "retain",
  "jwtSecretName": "harrison-jwt-secret"
}
```

---

## Stack Dependencies

```
harrison-data-stack
    └── harrison-compute-stack (needs queue URLs, table names)
            └── harrison-api-stack (needs App Runner endpoint)
                    └── harrison-cdn-stack (needs API URL for frontend)
```

---

## AWS CLI Verification Commands

```bash
# List stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE

# Describe stack outputs
aws cloudformation describe-stacks \
    --stack-name harrison-data-stack \
    --query 'Stacks[0].Outputs'

# List DynamoDB tables
aws dynamodb list-tables

# List SQS queues
aws sqs list-queues

# Describe API Gateway
aws apigateway get-rest-apis

# Describe CloudFront
aws cloudfront list-distributions
```

---

## Cost Estimate

| Service | Monthly Cost |
|---------|--------------|
| App Runner (API) | ~$5-10 |
| App Runner (Worker) | ~$5-10 |
| DynamoDB | ~$0 (free tier) |
| SQS | ~$0 (free tier) |
| API Gateway | ~$0-5 |
| CloudFront | ~$0-5 |
| S3 | ~$0-1 |
| **Total** | **<$25/month** |

---

## Cleanup

```bash
cdk destroy --all
```

**Warning**: This deletes all data!

---

## Files Created

| File | Purpose |
|------|---------|
| `app.py` | CDK entry point, stack orchestration |
| `requirements.txt` | CDK dependencies |
| `cdk.json` | CDK configuration |
| `stacks/__init__.py` | Stack exports |
| `stacks/data_stack.py` | DynamoDB + SQS resources |
| `stacks/compute_stack.py` | App Runner + ECR + IAM |
| `stacks/api_stack.py` | API Gateway + Rate limiting |
| `stacks/cdn_stack.py` | S3 + CloudFront |
| `README.md` | Deployment guide |

---

## Validation Checklist

After deployment, verify:

- [ ] `aws cloudformation describe-stacks --stack-status-filter CREATE_COMPLETE`
- [ ] DynamoDB tables exist: `aws dynamodb list-tables`
- [ ] SQS queues exist: `aws sqs list-queues`
- [ ] ECR repository exists: `aws ecr describe-repositories`
- [ ] App Runner services running: `aws apprunner list-services`
- [ ] API Gateway configured: `aws apigateway get-rest-apis`
- [ ] CloudFront distribution active: `aws cloudfront list-distributions`
- [ ] Secrets Manager secret exists: `aws secretsmanager list-secrets`

---

## References

- CDK Documentation: https://docs.aws.amazon.com/cdk/
- App Runner: https://docs.aws.amazon.com/apprunner/
- CDK Best Practices: https://docs.aws.amazon.com/cdk/latest/guide/best-practices.html
