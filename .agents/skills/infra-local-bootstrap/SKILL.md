---
name: infra-local-bootstrap
description: Workflow for creating Dockerized environments with LocalStack (SQS/DynamoDB) emulation.
---

# Instructions for Local Scaffolding

1. **Dockerfile Engineering**: Create a multi-stage `Dockerfile` for Python 3.11+. Optimize for small image size using `python:3.11-slim`.
2. **Orchestration**: Write a `docker-compose.yml` that includes:
    - **App Service**: Built from the local Dockerfile.
    - **LocalStack Service**: Exposing port `4566`.
3. **AWS Resource Provisioning**: Create a shell script (e.g., `init-aws.sh`) to be mounted in `/etc/localstack/init/ready.d/` to automatically:
    - Create the SQS queue for reporting jobs.
    - Initialize the AWS Database (DynamoDB or RDS instance).
4. **Environment Integrity**: Generate a `.env.example` mapping all internal container ports and AWS local endpoints.
5. **Validation**: Execute `docker compose up -d` and verify service health via `curl http://localhost:4566/_localstack/health`.

## Success Criteria
- System starts with a single command: `docker compose up`.
- No hardcoded secrets in the repository.