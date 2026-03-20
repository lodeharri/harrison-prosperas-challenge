# CDK Infrastructure for Reto Prosperas

This directory contains the AWS Cloud Development Kit (CDK) infrastructure code for deploying the Reto Prosperas job processing system to AWS.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              AWS Cloud                                   │
│                                                                          │
│  ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐ │
│  │   API Gateway    │────▶│   App Runner     │────▶│    DynamoDB      │ │
│  │  (Rate Limited)  │     │   (API Service)  │     │  (Jobs + Idemp.) │ │
│  └──────────────────┘     └──────────────────┘     └──────────────────┘ │
│                                    │                                      │
│                                    ▼                                      │
│                           ┌──────────────────┐                           │
│                           │       SQS        │                           │
│                           │  (Priority + DLQ)│                           │
│                           └──────────────────┘                           │
│                                    │                                      │
│                                    ▼                                      │
│                           ┌──────────────────┐                           │
│                           │   App Runner     │                           │
│                           │  (Worker Service)│                           │
│                           └──────────────────┘                           │
│                                                                          │
│  ┌──────────────────┐     ┌──────────────────┐                           │
│  │   CloudFront     │────▶│       S3         │                           │
│  │  (CDN + Caching)│     │  (Static Host)   │                           │
│  └──────────────────┘     └──────────────────┘                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
infra/
├── app.py                 # CDK application entry point
├── requirements.txt       # Python dependencies
├── cdk.json              # CDK configuration
├── stacks/
│   ├── __init__.py
│   ├── data_stack.py     # DynamoDB + SQS
│   ├── compute_stack.py  # App Runner + ECR
│   ├── api_stack.py      # API Gateway
│   └── cdn_stack.py      # S3 + CloudFront
└── README.md             # This file
```

## Prerequisites

### 1. AWS CLI Configuration

```bash
# Configure AWS credentials
aws configure

# Or use environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

### 2. CDK Installation

```bash
# Install CDK globally (recommended)
npm install -g aws-cdk

# Or use Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Verify installation
cdk --version
```

### 3. Bootstrap AWS Environment

CDK requires a one-time bootstrap per AWS account/region:

```bash
# Set your account and region
export CDK_ACCOUNT="123456789012"
export CDK_REGION="us-east-1"

# Bootstrap
cdk bootstrap aws://$CDK_ACCOUNT/$CDK_REGION

# Expected output:
# ⏳  Bootstrapping environment aws://123456789012/us-east-1...
# ✅  Environment aws://123456789012/us-east-1 bootstrapped
```

## Deployment

### 1. Synthesize CloudFormation Templates

```bash
cd infra

# List all stacks
cdk list
# Output:
# harrison-data-stack
# harrison-compute-stack
# harrison-api-stack
# harrison-cdn-stack

# Synthesize (generate CloudFormation)
cdk synth

# Or synth specific stack
cdk synth harrison-data-stack
```

### 2. Deploy All Stacks

```bash
# Deploy all stacks (in dependency order)
cdk deploy --all

# Or deploy specific stacks
cdk deploy harrison-data-stack
cdk deploy harrison-compute-stack
cdk deploy harrison-api-stack
cdk deploy harrison-cdn-stack
```

### 3. Deployment Options

```bash
# Dry run (show changes without deploying)
cdk diff

# Deploy with context overrides
cdk deploy --all -c stackPrefix=myapp -c environment=staging

# Enable rollback on failure (default)
cdk deploy --all --rollback true

# Show outputs after deployment
cdk deploy --all --outputs-file ./cdk-outputs.json
```

## Post-Deployment

### 1. Get Stack Outputs

```bash
# Get all outputs
cdk list --long

# Get specific output
aws cloudformation describe-stacks \
    --stack-name harrison-data-stack \
    --query 'Stacks[0].Outputs'
```

### 2. Build and Push Docker Images

```bash
# Get ECR repository URI
REPO_URI=$(aws cloudformation describe-stacks \
    --stack-name harrison-compute-stack \
    --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
    --output text)

# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin $REPO_URI

# Build and push API image
docker build -t harrison-api:latest ../backend
docker tag harrison-api:latest $REPO_URI:latest
docker push $REPO_URI:latest

# Build and push Worker image
docker build -t harrison-worker:latest ../backend
docker tag harrison-worker:latest $REPO_URI/worker:latest
docker push $REPO_URI/worker:latest
```

### 3. Deploy Frontend

```bash
# Set environment variables for build
export VITE_API_URL="https://<api-gateway-id>.execute-api.us-east-1.amazonaws.com/prod"
export VITE_WS_URL="wss://<api-gateway-id>.execute-api.us-east-1.amazonaws.com/prod/ws"

# Build frontend
cd ../frontend
npm run build

# Sync to S3
aws s3 sync dist/ s3://harrison-frontend --delete

# Create CloudFront invalidation
aws cloudfront create-invalidation \
    --distribution-id <distribution-id> \
    --paths "/*"
```

## Stack Details

### Data Stack (`harrison-data-stack`)

Creates:
- DynamoDB Table: `harrison-jobs` (PK: job_id, GSI: user_id)
- DynamoDB Table: `harrison-idempotency` (TTL: 24h)
- SQS Queue: `harrison-jobs-queue` (DLQ: harrison-jobs-dlq)
- SQS Queue: `harrison-jobs-dlq` (14-day retention)
- SQS Queue: `harrison-jobs-priority` (high-priority jobs)

### Compute Stack (`harrison-compute-stack`)

Creates:
- ECR Repository: `harrison-prospera-challenge`
- Secrets Manager: `harrison-jwt-secret`
- IAM Roles: API and Worker service roles
- App Runner Service: `harrison-api` (1 vCPU, 2 GB)
- App Runner Service: `harrison-worker` (1 vCPU, 2 GB)

### API Stack (`harrison-api-stack`)

Creates:
- API Gateway: `harrison-api-gw`
- Resources: /jobs, /jobs/{job_id}, /health, /auth
- Usage Plan: 100 req/min, burst 200
- API Key: For authentication

### CDN Stack (`harrison-cdn-stack`)

Creates:
- S3 Bucket: `harrison-frontend` (static hosting)
- CloudFront Distribution: `harrison-frontend-cdn`
- Origin Access Identity (OAI)
- CloudFront Function: SPA routing

## Environment Variables

### For App Runner Services

| Variable | Description |
|----------|-------------|
| `AWS_REGION` | AWS region (e.g., us-east-1) |
| `AWS_ENDPOINT_URL` | Empty for real AWS |
| `DYNAMODB_TABLE_JOBS` | Table name: harrison-jobs |
| `DYNAMODB_TABLE_IDEMPOTENCY` | Table name: harrison-idempotency |
| `SQS_QUEUE_URL` | Main queue URL |
| `SQS_DLQ_URL` | Dead letter queue URL |
| `SQS_PRIORITY_QUEUE_URL` | Priority queue URL |
| `JWT_SECRET_KEY` | Secrets Manager ARN for JWT |

### For Frontend (Build Time)

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | API Gateway URL |
| `VITE_WS_URL` | WebSocket URL |

## Cost Estimation

Based on AWS Free Tier and App Runner pricing:

| Resource | Monthly Cost (Estimate) |
|----------|------------------------|
| App Runner (API) | ~$5-10 |
| App Runner (Worker) | ~$5-10 |
| DynamoDB | ~$0 |
| SQS | ~$0 |
| API Gateway | ~$0-5 |
| CloudFront | ~$0-5 |
| S3 | ~$0-1 |
| **Total** | **<$20/month** |

## Troubleshooting

### CDK Bootstrapping Fails

```bash
# Check IAM permissions
aws iam get-user

# Ensure you have AdminAccess or specific CDK permissions
```

### Deployment Fails

```bash
# Check CloudFormation events
aws cloudformation describe-stack-events \
    --stack-name harrison-data-stack

# Check specific resource failures
aws cloudformation describe-stack-resources \
    --stack-name harrison-data-stack
```

### App Runner Not Starting

```bash
# Check service status
aws apprunner describe-service \
    --service-arn <service-arn>

# Check logs in CloudWatch
aws logs tail /aws/apprunner/<service-name>/<instance-id>
```

## Cleanup

To destroy all resources:

```bash
cd infra

# Destroy all stacks
cdk destroy --all

# Or destroy specific stacks
cdk destroy harrison-cdn-stack
cdk destroy harrison-api-stack
cdk destroy harrison-compute-stack
cdk destroy harrison-data-stack
```

**Warning**: This will delete all data in DynamoDB and SQS queues.

## Security Considerations

1. **Secrets**: JWT secret stored in Secrets Manager, not in code
2. **S3 Access**: Protected by CloudFront OAI (no public access)
3. **IAM Roles**: Least-privilege permissions per service
4. **Encryption**: DynamoDB and SQS use KMS-managed encryption
5. **API Gateway**: Rate limiting enabled

## Monitoring

- **CloudWatch Logs**: App Runner services log to `/aws/apprunner/`
- **CloudWatch Metrics**: Custom metrics for job processing
- **CloudWatch Alarms**: Set up for error rate thresholds

## CI/CD Integration

See `.github/workflows/deploy.yml` for GitHub Actions integration.

## License

MIT
