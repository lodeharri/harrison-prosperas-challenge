# AGENTS.md - Infrastructure Context

## Setup Commands
- Full Boot: `docker compose up -d`
- Status Check: `docker compose ps`
- AWS Local Check: `awslocal s3 ls`

## Tech Stack
- Docker / Docker Compose
- LocalStack (Emulating: S3, SQS, DynamoDB)
- GitHub Actions (Workflows in `.github/workflows/`)

## Environment Specs
- LocalStack Edge Port: `4566`
- Network Mode: `bridge`
- Docker Base Image: `python:3.11-slim`