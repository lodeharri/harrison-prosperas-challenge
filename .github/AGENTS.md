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

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `CDK_BOOTSTRAPPED` | Set to `true` after first bootstrap | `false` | Yes |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution ID | (post-deploy) | No |
| `AWS_REGION` | AWS region for deployment | `us-east-1` | No |
| `STACK_PREFIX` | Prefix for all AWS resource names | `harrison` | No |
| `CDK_APP_NAME` | CDK application name | `harrison-prosperas-challenge` | No |
| `ECR_REPOSITORY` | ECR repository name | `harrison-prospera-challenge` | No |
| `FRONTEND_BUCKET` | S3 bucket for frontend | `harrison-frontend` | No |
| `CI_API_URL` | API URL for CI frontend builds | `http://localhost:8000` | No |
| `CI_WS_URL` | WebSocket URL for CI frontend builds | `ws://localhost:8000` | No |

### Adding Variables

```bash
# Using GitHub CLI
gh variable set CDK_BOOTSTRAPPED --body "false"
gh variable set AWS_REGION --body "us-east-1"
gh variable set STACK_PREFIX --body "harrison"
gh variable set CDK_APP_NAME --body "harrison-prosperas-challenge"
gh variable set ECR_REPOSITORY --body "harrison-prospera-challenge"
gh variable set FRONTEND_BUCKET --body "harrison-frontend"
gh variable set CI_API_URL --body "http://localhost:8000"
gh variable set CI_WS_URL --body "ws://localhost:8000"

# Or via GitHub Web UI
# Settings > Secrets and variables > Variables > New repository variable
```

---

## IAM Permissions Required

The AWS credentials need the following permissions (full policy in README.md):

### Core Deployment Permissions
- `cloudformation:*` - Full CloudFormation access for stack management
- `sts:GetCallerIdentity` - For identity verification

### Networking (EC2/VPC)
- `ec2:CreateVpc`, `ec2:DeleteVpc`, `ec2:DescribeVpcs`
- `ec2:CreateSubnet`, `ec2:DeleteSubnet`, `ec2:DescribeSubnets`
- `ec2:CreateSecurityGroup`, `ec2:DeleteSecurityGroup`, `ec2:DescribeSecurityGroups`
- `ec2:AuthorizeSecurityGroupIngress`, `ec2:RevokeSecurityGroupIngress`

### Container Registry (ECR)
- `ecr:CreateRepository`, `ecr:DescribeRepositories`, `ecr:DeleteRepository`
- `ecr:GetAuthorizationToken`, `ecr:PutImage`, `ecr:BatchGetImage`
- `ecr:PutLifecyclePolicy`, `ecr:GetLifecyclePolicy`

### Container Orchestration (ECS)
- `ecs:CreateCluster`, `ecs:DeleteCluster`, `ecs:DescribeClusters`
- `ecs:CreateService`, `ecs:DeleteService`, `ecs:DescribeServices`, `ecs:UpdateService`
- `ecs:CreateTaskDefinition`, `ecs:DeleteTaskDefinition`, `ecs:DescribeTaskDefinition`
- `ecs:RegisterTaskDefinition`, `ecs:DeregisterTaskDefinition`

### Database (DynamoDB)
- `dynamodb:CreateTable`, `dynamodb:DeleteTable`, `dynamodb:DescribeTable`
- `dynamodb:UpdateTable`, `dynamodb:ListTables`
- `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:Query`

### Messaging (SQS)
- `sqs:CreateQueue`, `sqs:DeleteQueue`, `sqs:GetQueueUrl`
- `sqs:GetQueueAttributes`, `sqs:SetQueueAttributes`, `sqs:ListQueues`
- `sqs:SendMessage`, `sqs:ReceiveMessage`, `sqs:DeleteMessage`

### Storage (S3)
- `s3:CreateBucket`, `s3:DeleteBucket`, `s3:GetBucketLocation`
- `s3:ListBucket`, `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`
- `s3:GetBucketPolicy`, `s3:PutBucketPolicy`, `s3:DeleteBucketPolicy`

### API Management (API Gateway)
- `apigateway:CreateRestApi`, `apigateway:DeleteRestApi`, `apigateway:GetRestApi`
- `apigateway:CreateResource`, `apigateway:DeleteResource`, `apigateway:GetResource`
- `apigateway:CreateMethod`, `apigateway:DeleteMethod`, `apigateway:GetMethod`
- `apigateway:CreateIntegration`, `apigateway:DeleteIntegration`, `apigateway:GetIntegration`
- `apigateway:CreateDeployment`, `apigateway:DeleteDeployment`, `apigateway:GetDeployment`
- `apigateway:CreateUsagePlan`, `apigateway:DeleteUsagePlan`, `apigateway:GetUsagePlan`
- `apigateway:CreateApiKey`, `apigateway:DeleteApiKey`, `apigateway:GetApiKey`

### CDN (CloudFront)
- `cloudfront:CreateDistribution`, `cloudfront:DeleteDistribution`, `cloudfront:GetDistribution`
- `cloudfront:UpdateDistribution`, `cloudfront:ListDistributions`
- `cloudfront:CreateInvalidation`, `cloudfront:GetInvalidation`, `cloudfront:ListInvalidations`
- `cloudfront:CreateCloudFrontOriginAccessIdentity`, `cloudfront:DeleteCloudFrontOriginAccessIdentity`
- `cloudfront:GetCloudFrontOriginAccessIdentity`, `cloudfront:UpdateCloudFrontOriginAccessIdentity`

### Identity & Access (IAM)
- `iam:CreateRole`, `iam:DeleteRole`, `iam:GetRole`, `iam:PassRole`
- `iam:AttachRolePolicy`, `iam:DetachRolePolicy`
- `iam:CreatePolicy`, `iam:DeletePolicy`, `iam:GetPolicy`

### Monitoring (CloudWatch)
- `logs:CreateLogGroup`, `logs:DeleteLogGroup`, `logs:DescribeLogGroups`
- `logs:CreateLogStream`, `logs:DeleteLogStream`, `logs:DescribeLogStreams`
- `logs:PutLogEvents`, `logs:GetLogEvents`, `logs:FilterLogEvents`
- `cloudwatch:PutMetricData`, `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`

### Secrets Management
- `secretsmanager:CreateSecret`, `secretsmanager:DeleteSecret`, `secretsmanager:GetSecretValue`
- `secretsmanager:DescribeSecret`, `secretsmanager:ListSecrets`

### Load Balancing (ELB)
- `elasticloadbalancing:CreateLoadBalancer`, `elasticloadbalancing:DeleteLoadBalancer`
- `elasticloadbalancing:DescribeLoadBalancers`
- `elasticloadbalancing:CreateTargetGroup`, `elasticloadbalancing:DeleteTargetGroup`
- `elasticloadbalancing:DescribeTargetGroups`
- `elasticloadbalancing:CreateListener`, `elasticloadbalancing:DeleteListener`
- `elasticloadbalancing:DescribeListeners`

**Note:** For the complete JSON policy with resource restrictions, see the README.md file.

---

---

## CDK Outputs

The following outputs are generated by CDK stacks:

| Output Key | Stack | Description |
|------------|-------|-------------|
| `ApiEndpoint` | API Stack | API Gateway URL |
| `APIServiceUrl` | Compute Stack | ALB DNS name (for WebSocket) |
| `DynamoDBTableArn` | Data Stack | Jobs table ARN |
| `SQSQueueUrl` | Data Stack | Main queue URL |
| `ECRRepositoryUri` | Compute Stack | ECR repository URI |
| `FrontendBucketName` | CDN Stack | S3 bucket name |
| `CloudFrontDistributionId` | CDN Stack | CloudFront ID |

### URL Architecture

The application uses two endpoints:
- **REST API**: `VITE_API_URL` → API Gateway (for HTTP/REST calls)
- **WebSocket**: `VITE_WS_URL` → ALB (for WebSocket connections)

The ALB provides a stable DNS name that supports WebSocket connections directly to ECS Fargate.

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

