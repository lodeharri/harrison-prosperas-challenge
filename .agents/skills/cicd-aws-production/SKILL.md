---
name: cicd-aws-production
description: GitHub Actions pipeline for automated AWS deployment with cost optimization (<$10 USD).
---

# Instructions for Production Pipeline

1. **CI Pipeline**: Define `.github/workflows/deploy.yml` triggered on `main` branch pushes.
2. **Infrastructure Selection**: Prioritize AWS Free Tier services (e.g., App Runner, Lambda, or a small EC2 t3.micro with S3/SQS).
3. **Secret Management**: Configure the workflow to use GitHub Actions Secrets for `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` [11].
4. **Reviewer Access Provisioning**: Write an HCL/Terraform script or step-by-step instructions to create an IAM User with `AdministratorAccess` for reviewers.
5. **Deployment Verification**: Ensure the pipeline outputs the Public URL of the deployed application.

## Success Criteria
- Deployment completes under 10 minutes.
- Monthly projected AWS cost is verified to be <$10 USD.