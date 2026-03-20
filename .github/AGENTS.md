# AGENTS.md - CI/CD Module

**Module:** GitHub Actions Pipeline & AWS Deployment  
**Directory:** `/home/harri/development/projects/harrison-prosperas-challenge/.github`  
**Skill:** `cicd-aws-production`

---

## Overview

This module implements automated CI/CD using GitHub Actions for continuous integration and AWS deployment. The pipeline includes linting, type checking, testing, Docker image building, CDK infrastructure deployment, and frontend hosting.

**Status:** ✅ IMPLEMENTED

---

## Workflows

### 1. CI Pipeline (`ci.yml`)

**Trigger:** PR to `main` + push to `main`

**Jobs:**
| Job | Description | Tool |
|-----|-------------|------|
| `lint-backend` | Lint Python code | ruff |
| `typecheck-backend` | Type check Python code | mypy |
| `test-backend` | Run pytest with coverage | pytest + pytest-cov |
| `lint-frontend` | Lint TypeScript code | eslint |
| `test-frontend` | Run Jest tests | npm test |
| `build-frontend` | Build React app | vite build |

### 2. Deploy Pipeline (`deploy.yml`)

**Trigger:** Push to `main` only

**Jobs:**
| Job | Dependency | Description |
|-----|-------------|-------------|
| `build-ecr` | - | Build and push Docker image to ECR |
| `cdk-synth` | - | Synthesize CDK templates, get outputs |
| `build-frontend` | `cdk-synth` | Build frontend with production API URL |
| `deploy-cdk` | `build-ecr` | Deploy CDK stacks to AWS |
| `deploy-frontend` | `build-frontend`, `deploy-cdk` | Upload to S3, invalidate CloudFront |
| `verify` | `deploy-cdk`, `deploy-frontend` | Health check and smoke test |

---

## Execution Order

```
┌─────────────┐
│ build-ecr   │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│ cdk-synth   │────▶│build-frontend│
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 │
                 ▼
          ┌─────────────┐
          │ deploy-cdk  │
          └──────┬──────┘
                 │
                 ▼
          ┌─────────────┐
          │deploy-frontend│
          └──────┬──────┘
                 │
                 ▼
          ┌─────────────┐
          │   verify    │
          └─────────────┘
```

---

## GitHub Secrets Required

| Secret | Description | Required For |
|--------|-------------|--------------|
| `AWS_ACCESS_KEY_ID` | AWS access key ID | All AWS operations |
| `AWS_SECRET_ACCESS_KEY` | AWS secret access key | All AWS operations |
| `AWS_ACCOUNT_ID` | AWS account ID | CDK bootstrap |
| `JWT_SECRET_KEY` | JWT signing key for production | Backend deployment |
| `CODECOV_TOKEN` | Codecov upload token | Coverage reports (optional) |

### Adding Secrets

```bash
# Using GitHub CLI
gh secret set AWS_ACCESS_KEY_ID --body "$AWS_ACCESS_KEY_ID"
gh secret set AWS_SECRET_ACCESS_KEY --body "$AWS_SECRET_ACCESS_KEY"
gh secret set AWS_ACCOUNT_ID --body "$AWS_ACCOUNT_ID"
gh secret set JWT_SECRET_KEY --body "$JWT_SECRET_KEY"

# Or via GitHub Web UI
# Settings > Secrets and variables > Actions > New repository secret
```

---

## GitHub Variables Required

| Variable | Description | Example |
|----------|-------------|---------|
| `CDK_BOOTSTRAPPED` | Set to `true` after first bootstrap | `true` |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution ID | `E1A2B3C4D5E6F7` |

### Adding Variables

```bash
# Using GitHub CLI
gh variable set CDK_BOOTSTRAPPED --body "true"
gh variable set CLOUDFRONT_DISTRIBUTION_ID --body "E1A2B3C4D5E6F7"

# Or via GitHub Web UI
# Settings > Secrets and variables > Variables > New repository variable
```

---

## IAM Permissions Required

The AWS credentials need the following permissions:

### ECR
- `ecr:CreateRepository` (first run only)
- `ecr:GetAuthorizationToken`
- `ecr:DescribeImages`
- `ecr:BatchCheckLayerAvailability`
- `ecr:GetDownloadUrlForLayer`
- `ecr:BatchGetImage`
- `ecr:PutImage`
- `ecr:InitiateLayerUpload`
- `ecr:UploadLayerPart`
- `ecr:CompleteLayerUpload`

### CDK
- `cloudformation:CreateChangeSet`
- `cloudformation:DescribeChangeSet`
- `cloudformation:ExecuteChangeSet`
- `cloudformation:DeleteStack`
- `cloudformation:DescribeStacks`
- `iam:CreateRole`
- `iam:AttachRolePolicy`
- `iam:PassRole`
- `apprunner:CreateService`
- `apprunner:DescribeService`
- `apprunner:UpdateService`
- `dynamodb:CreateTable`
- `dynamodb:DescribeTable`
- `sqs:CreateQueue`
- `sqs:GetQueueUrl`
- `sqs:SetQueueAttributes`

### S3
- `s3:CreateBucket` (first run only)
- `s3:PutObject`
- `s3:DeleteObject`
- `s3:ListBucket`
- `s3:Sync`

### CloudFront
- `cloudfront:CreateInvalidation`
- `cloudfront:GetDistribution`

---

## Cost Optimization (< $10 USD/month)

| Service | Configuration | Estimated Cost |
|---------|---------------|----------------|
| App Runner | 1 vCPU, 2 GB, Auto-scaling | ~$5-7/month |
| DynamoDB | On-demand | ~$0-1/month |
| SQS | Standard queue | ~$0/month* |
| ECR | Storage only | ~$0.05/month |
| CloudFront | Pay-as-you-go | ~$0.02/month |
| S3 | Standard | ~$0.01/month |
| **Total** | | **~$5-8/month** |

*SQS: First 1M requests/month free

---

## CDK Outputs

The following outputs are generated by CDK stacks:

| Output Key | Description |
|------------|-------------|
| `ApiEndpoint` | API Gateway URL |
| `DynamoDBTableArn` | Jobs table ARN |
| `SQSQueueUrl` | Main queue URL |
| `ECRRepositoryUri` | ECR repository URI |
| `FrontendBucketName` | S3 bucket name |
| `CloudFrontDistributionId` | CloudFront ID |

---

## Deployment Verification

### Health Check

```bash
curl https://<api-gateway-id>.execute-api.us-east-1.amazonaws.com/prod/health
```

### Expected Response
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-03-19T..."
}
```

### Smoke Test

```bash
# 1. Get JWT token
TOKEN=$(curl -s -X POST "$API_URL/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user"}' | jq -r '.access_token')

# 2. Create job
curl -X POST "$API_URL/jobs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "sales_report", "date_range": "last_7_days", "format": "pdf"}'
```

---

## Local Testing

```bash
# Validate workflow syntax
yamllint .github/workflows/ci.yml
yamllint .github/workflows/deploy.yml

# Test workflows locally (requires act)
act -W .github/workflows/ci.yml
act -W .github/workflows/deploy.yml
```

---

## File Structure

```
.github/
├── AGENTS.md              # This file
└── workflows/
    ├── ci.yml             # Continuous Integration
    └── deploy.yml         # Continuous Deployment
```

---

## Dependencies

- **AWS Account:** Required for deployment
- **ECR Repository:** Created on first run
- **DynamoDB/SQS:** Created via CDK
- **Frontend Bucket:** Created via CDK

---

## References

- CI/CD Skill: `../.agents/skills/cicd-aws-production/SKILL.md`
- AWS CDK Documentation
- GitHub Actions Documentation

---

## Task List

- [x] **ci.yml:** Create CI workflow (lint, typecheck, test, build)
- [x] **deploy.yml:** Create deployment workflow (ECR, CDK, S3, verify)
- [x] **Secrets documentation:** AWS credentials, JWT key
- [x] **Variables documentation:** CloudFront ID
- [x] **IAM permissions:** Complete permission set
- [x] **Cost estimation:** <$10/month
