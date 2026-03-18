# AGENTS.md - Backend Context

## Setup Commands
- Install: `pip install -r requirements.txt`
- Test: `pytest --cov=app`
- Dev: `fastapi dev main.py`

## Concurrency Requirements
- Worker must use `asyncio.gather` or `TaskGroups` to process at least 2 messages concurrently from SQS.

## AWS Integration
- Use LocalStack endpoints for development as defined in the infrastructure AGENTS.md.