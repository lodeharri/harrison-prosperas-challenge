# AGENTS.md - CI/CD Module

**Module:** GitHub Actions Pipeline & AWS Deployment  
**Directory:** `/home/harri/development/projects/reto-prosperas2/.github`  
**Skill:** `cicd-aws-production`

## Overview

This module implements automated deployment using GitHub Actions. The pipeline builds the Docker container, deploys to AWS, and ensures the application is accessible via a public URL.

**Status:** PENDING - Implementation deferred until infrastructure is ready

---

## Setup Commands

```bash
# Test workflow locally (requires act)
act -W .github/workflows/deploy.yml

# Validate workflow syntax
yamllint .github/workflows/deploy.yml

# Manual deployment (for testing)
aws configure
./scripts/deploy.sh
```

---

## Tech Stack

| Component | Service | Purpose |
|-----------|---------|---------|
| CI/CD | GitHub Actions | Pipeline automation |
| Container Registry | Amazon ECR | Docker image storage |
| Compute | AWS App Runner | Container hosting |
| Database | Amazon DynamoDB | Job persistence |
| Queue | Amazon SQS | Message processing |

---

## GitHub Actions Workflow

### deploy.yml Structure

```yaml
name: Deploy to AWS

on:
  push:
    branches: [main]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: reto-prosperas
  APP_RUNNER_SERVICE: reto-prosperas-service

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push Docker image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG ./backend
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG

      - name: Create/update App Runner service
        run: |
          aws apprunner create-service \
            --service-name $APP_RUNNER_SERVICE \
            --image-repository $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG \
            --port 8000 \
            --health-check-configuration path=/health

      - name: Get App Runner URL
        id: app-url
        run: |
          SERVICE_URL=$(aws apprunner describe-service \
            --service-arn $APP_RUNNER_SERVICE_ARN \
            --query 'Service.ServiceUrl' --output text)
          echo "APP_URL=https://$SERVICE_URL" >> $GITHUB_ENV

      - name: Verify deployment
        run: |
          curl -f $APP_URL/health || exit 1
```

---

## AWS Resources

### Required Resources

| Resource | Type | Purpose |
|----------|------|---------|
| ECR Repository | Container Registry | Store Docker images |
| App Runner Service | Compute | Run containerized app |
| DynamoDB Table | Database | Job persistence |
| SQS Queue | Queue | Job processing |
| IAM Role | Execution Role | App Runner permissions |

### Resource Creation

```bash
# Create ECR repository
aws ecr create-repository --repository-name reto-prosperas

# Create DynamoDB table
aws dynamodb create-table \
  --table-name jobs \
  --attribute-definitions \
    AttributeName=job_id,AttributeType=S \
    AttributeName=user_id,AttributeType=S \
    AttributeName=created_at,AttributeType=S \
  --key-schema AttributeName=job_id,KeyType=HASH \
  --global-secondary-indexes \
    '[{"IndexName": "user_id-created_at-index", "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}, {"AttributeName": "created_at", "KeyType": "RANGE"}], "Projection": {"ProjectionType": "ALL"}}]' \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5

# Create SQS queues
aws sqs create-queue --queue-name report-jobs-queue
aws sqs create-queue --queue-name report-jobs-dlq
```

---

## Cost Optimization (< $10 USD/month)

### Service Selection

| Service | Tier | Estimated Cost |
|---------|------|----------------|
| App Runner | 1 vCPU, 2 GB | ~$5-7/month |
| DynamoDB | 5 RCU/WCU | ~$0/month* |
| SQS | Standard | ~$0/month** |
| ECR | Storage only | ~$0.05/month |
| **Total** | | **~$5-7/month** |

*DynamoDB on-demand or 25 GB free tier
**First 1M requests/month free

### Cost-Saving Measures

1. **App Runner Auto-Scaling:** Scale to 0 when idle
2. **DynamoDB On-Demand:** Pay per request
3. **SQS Free Tier:** Use standard queue within free limits
4. **ECR Cleanup:** Delete old images regularly

---

## GitHub Secrets Configuration

### Required Secrets

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS access key for deployment |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for deployment |
| `JWT_SECRET_KEY` | Production JWT signing key |

### Adding Secrets

```bash
# Using GitHub CLI
gh secret set AWS_ACCESS_KEY_ID --body "$AWS_ACCESS_KEY_ID"
gh secret set AWS_SECRET_ACCESS_KEY --body "$AWS_SECRET_ACCESS_KEY"
gh secret set JWT_SECRET_KEY --body "$JWT_SECRET_KEY"

# Or via GitHub Web UI
# Settings > Secrets and variables > Actions > New repository secret
```

---

## Reviewer Access (IAM User)

### Create Admin User for Reviewers

```bash
#!/bin/bash
# create-reviewer-iam.sh

# Create IAM user
aws iam create-user --user-name reto-prosperas-reviewer

# Attach AdministratorAccess policy
aws iam attach-user-policy \
  --user-name reto-prosperas-reviewer \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

# Create access keys
aws iam create-access-key --user-name reto-prosperas-reviewer
```

### Alternative: Terraform Configuration

```hcl
# infrastructure/iam.tf
resource "aws_iam_user" "reviewer" {
  name = "reto-prosperas-reviewer"
}

resource "aws_iam_user_policy_attachment" "reviewer_admin" {
  user       = aws_iam_user.reviewer.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

resource "aws_iam_access_key" "reviewer" {
  user = aws_iam_user.reviewer.name
}

output "reviewer_access_key" {
  value     = aws_iam_access_key.reviewer.id
  sensitive = true
}

output "reviewer_secret_key" {
  value     = aws_iam_access_key.reviewer.secret
  sensitive = true
}
```

---

## Deployment Verification

### Health Check Endpoint

```bash
# After deployment, verify health endpoint
curl https://<app-url>/health

# Expected response
{
  "status": "healthy",
  "version": "1.0.0",
  "dependencies": {
    "dynamodb": "ok",
    "sqs": "ok"
  }
}
```

### Smoke Test

```yaml
- name: Run smoke tests
  run: |
    # Test job creation
    RESPONSE=$(curl -s -X POST \
      -H "Authorization: Bearer $TEST_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"report_type": "test"}' \
      https://$APP_URL/jobs)
    
    JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
    
    # Verify job exists
    curl -f https://$APP_URL/jobs/$JOB_ID \
      -H "Authorization: Bearer $TEST_TOKEN"
```

---

## File Structure

```
.github/
├── AGENTS.md              # This file
└── workflows/
    └── deploy.yml         # Main deployment workflow
```

---

## Task List

- [ ] **deploy.yml:** Create GitHub Actions workflow
- [ ] **Secrets:** Configure AWS secrets in repository
- [ ] **IAM Script:** Create reviewer access script
- [ ] **Verify Deployment:** Test health endpoint
- [ ] **Cost Verification:** Confirm < $10/month estimate

---

## Dependencies

- **AWS Account:** Required for deployment
- **ECR Repository:** Created before first deployment
- **DynamoDB/SQS:** Created via infrastructure scripts

---

## References

- CI/CD Skill: `../.agents/skills/cicd-aws-production/SKILL.md`
