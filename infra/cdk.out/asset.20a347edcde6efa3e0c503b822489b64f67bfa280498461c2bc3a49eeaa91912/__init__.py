"""Reto Prosperas Backend Module - Hexagonal Architecture.

This module provides the FastAPI REST API for the report job processing system.

## Architecture

The backend follows Hexagonal Architecture (Ports & Adapters):

```
src/
├── domain/           # Core business logic (no external dependencies)
│   ├── entities/     # Job entity
│   ├── value_objects/ # JobStatus enum
│   └── exceptions/   # Domain exceptions
├── application/       # Use cases and ports (interfaces)
│   ├── ports/        # JobRepository, JobQueue interfaces
│   └── use_cases/    # CreateJob, GetJob, ListJobs, UpdateJobStatus
├── adapters/         # Infrastructure implementations
│   ├── primary/      # FastAPI routes (entry points)
│   └── secondary/    # DynamoDB, SQS adapters
├── config/           # Settings
└── shared/           # JWT, exceptions, schemas
```

## Running

```bash
# Run the API server
cd backend
PYTHONPATH=.. uvicorn src.adapters.primary.fastapi.main:app --reload --port 8000

# Run tests
PYTHONPATH=.. pytest tests/ -v --cov=src

# Run with Docker
docker compose up backend
```

## Testing the API

```bash
# Get a token
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-123"}'

# Create a job
curl -X POST http://localhost:8000/jobs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "sales_report"}'

# List jobs
curl http://localhost:8000/jobs \
  -H "Authorization: Bearer <token>"

# Health check
curl http://localhost:8000/health
```
"""

from backend.src.adapters.primary.fastapi.main import create_app

__all__ = ["create_app"]
