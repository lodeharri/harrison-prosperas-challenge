# AGENTS.md - Worker Module

**Module:** Async Job Processor  
**Directory:** `/home/harri/development/projects/reto-prosperas2/backend/worker`  
**Parent Skill:** `fastapi-api-core` (AWS integration patterns)

## Overview

The worker module consumes messages from AWS SQS, processes report jobs asynchronously, and updates job status in DynamoDB. It supports concurrent processing, error handling with retries, and optional circuit breaker patterns.

---

## Setup Commands

```bash
# Install worker dependencies
pip install -r backend/requirements.txt

# Run worker locally (requires LocalStack)
python -m backend.worker.main

# Run via Docker
docker compose up worker

# Run tests
pytest backend/worker/tests/ -v
```

---

## Tech Stack

| Component | Library | Purpose |
|-----------|---------|---------|
| Async Runtime | asyncio | Concurrent processing |
| AWS SDK | aiobotocore | Non-blocking SQS/DynamoDB |
| HTTP Client | httpx | Result URL generation (mock) |
| Testing | pytest, pytest-asyncio | Async test support |

---

## Core Processing Logic

### Main Loop (asyncio.gather)

```python
async def process_jobs():
    """Main worker loop processing multiple jobs concurrently."""
    tasks = []
    while running:
        # Fetch messages in batches
        messages = await sqs.receive_messages(MaxNumberOfMessages=10)
        
        for message in messages:
            task = asyncio.create_task(process_single_job(message))
            tasks.append(task)
        
        # Process at least 2 jobs concurrently
        if tasks:
            completed, pending = await asyncio.gather(*tasks, return_exceptions=True)
            tasks = [t for t in pending if not t.done()]
        
        await asyncio.sleep(1)  # Poll interval
```

### Job Processing Flow

```
1. Receive message from SQS
   ↓
2. Parse message: { job_id, report_type, priority }
   ↓
3. Update DynamoDB: status = PROCESSING
   ↓
4. Check circuit breaker for report_type
   ↓
5. Process report (simulated: random 5-30s sleep)
   ↓
6. Generate dummy report data
   ↓
7. Update DynamoDB: status = COMPLETED, result_url = "..."
   ↓
8. Delete message from SQS
```

### Simulated Processing

```python
import random
import asyncio

async def process_report(job_id: str, report_type: str) -> dict:
    """Simulate report generation with random delay."""
    # Random processing time: 5-30 seconds
    processing_time = random.uniform(5, 30)
    await asyncio.sleep(processing_time)
    
    # Generate dummy report data
    return {
        "job_id": job_id,
        "report_type": report_type,
        "generated_at": datetime.utcnow().isoformat(),
        "data": {
            "total_records": random.randint(100, 10000),
            "summary": "Dummy report summary"
        }
    }
```

---

## Concurrency Requirements

### Minimum: 2 Concurrent Jobs

```python
# Ensure at least 2 jobs process simultaneously
MAX_CONCURRENT = 10  # Can be increased based on resources

async def run():
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
    async def bounded_process(msg):
        async with semaphore:
            await process_single_job(msg)
    
    # ... gather multiple bounded_process tasks
```

### Using asyncio.gather

```python
# Process multiple messages in parallel
batch = [msg1, msg2, msg3, ...]
tasks = [process_single_job(msg) for msg in batch]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

---

## Error Handling & Retries

### Dead Letter Queue Strategy

```python
async def handle_message_failure(message, error, attempt: int):
    """Handle failed message processing."""
    max_attempts = 3
    
    if attempt >= max_attempts:
        # Move to DLQ
        await sqs.send_to_dlq(message)
        await delete_from_main_queue(message)
        logger.error(f"Message moved to DLQ after {attempt} attempts: {job_id}")
    else:
        # Exponential backoff before retry
        delay = 2 ** attempt  # 1, 2, 4, 8... seconds
        await asyncio.sleep(delay)
        # Message will be retried (VisibilityTimeout handles this)
```

### Visibility Timeout

- Set to 30 seconds (longer than max processing time)
- If not deleted in time, message returns to queue automatically

### Retry Logic

```python
async def process_with_retry(message, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        try:
            await process_single_job(message)
            return True
        except RetryableError as e:
            if attempt == max_attempts:
                raise
            delay = min(2 ** attempt + random.uniform(0, 1), 60)
            await asyncio.sleep(delay)
        except NonRetryableError:
            raise
```

---

## Circuit Breaker (Bonus Challenge B2)

```python
class CircuitBreaker:
    """Circuit breaker to pause processing for failing report types."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures: dict[str, int] = {}
        self.circuits: dict[str, float] = {}  # report_type -> opened_at
    
    def record_failure(self, report_type: str):
        self.failures[report_type] = self.failures.get(report_type, 0) + 1
        if self.failures[report_type] >= self.failure_threshold:
            self.circuits[report_type] = time.time()
    
    def record_success(self, report_type: str):
        self.failures[report_type] = 0
        self.circuits.pop(report_type, None)
    
    def is_open(self, report_type: str) -> bool:
        if report_type not in self.circuits:
            return False
        
        elapsed = time.time() - self.circuits[report_type]
        if elapsed > self.recovery_timeout:
            # Half-open state: allow one attempt
            del self.circuits[report_type]
            return False
        return True
```

---

## Priority Queues (Bonus Challenge B1)

### High Priority Processing

```python
async def process_by_priority():
    """Process high priority jobs first."""
    # Poll high-priority queue more frequently
    while True:
        high_priority = await sqs.receive_messages(
            QueueUrl=HIGH_PRIORITY_QUEUE,
            MaxNumberOfMessages=5
        )
        
        if high_priority:
            await asyncio.gather(*[process(msg) for msg in high_priority])
        else:
            # Only poll standard queue if high priority is empty
            standard = await sqs.receive_messages(
                QueueUrl=STANDARD_QUEUE,
                MaxNumberOfMessages=5
            )
            await asyncio.gather(*[process(msg) for msg in standard])
        
        await asyncio.sleep(0.5)  # High priority poll interval
```

### Message Attributes

```json
{
  "job_id": "uuid",
  "report_type": "sales_report",
  "priority": "high",  // or "standard"
  "user_id": "user-uuid"
}
```

---

## Exponential Backoff (Bonus Challenge B4)

```python
async def exponential_backoff(attempt: int, base: float = 1.0, max_delay: float = 60.0):
    """Calculate exponential backoff delay with jitter."""
    delay = min(base * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.1)
    return delay + jitter

# Usage in retry loop
for attempt in range(max_retries):
    try:
        await process_job(job_id)
    except RetryableError:
        delay = await exponential_backoff(attempt)
        logger.info(f"Retry {attempt + 1} in {delay:.2f}s")
        await asyncio.sleep(delay)
```

---

## Observability (Bonus Challenge B5)

### Structured Logging

```python
import structlog

logger = structlog.get_logger()

async def process_single_job(message):
    job_id = message["job_id"]
    logger.info("job_processing_started", job_id=job_id, report_type=message["report_type"])
    
    try:
        result = await process_report(job_id, message["report_type"])
        logger.info("job_processing_completed", job_id=job_id, duration=result["duration"])
        return result
    except Exception as e:
        logger.error("job_processing_failed", job_id=job_id, error=str(e))
        raise
```

### Business Metrics

```python
# Track metrics for monitoring
METRICS = {
    "jobs_processed_total": 0,
    "jobs_failed_total": 0,
    "jobs_by_type": defaultdict(int),
    "processing_duration_seconds": [],
}

async def record_completion(job_id, duration, report_type):
    METRICS["jobs_processed_total"] += 1
    METRICS["jobs_by_type"][report_type] += 1
    METRICS["processing_duration_seconds"].append(duration)
```

---

## File Structure

```
backend/worker/
├── __init__.py             # Package init
├── main.py                 # Entry point
├── config.py               # Configuration
├── processor.py            # Main processing logic
├── circuit_breaker.py      # Circuit breaker implementation
├── backoff.py              # Exponential backoff
├── sqs_client.py           # SQS operations
├── dynamodb_client.py      # DynamoDB operations
├── models.py               # Data models
├── pytest.ini              # Pytest configuration
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_processor.py
    ├── test_circuit_breaker.py
    └── test_backoff.py
```

---

## Dependencies

- **DynamoDB:** Read job, update status
- **SQS:** Receive messages, delete on success, move to DLQ on failure

---

## References

- Parent Skill: `../../../.agents/skills/fastapi-api-core/SKILL.md`
- AWS Data Modeling: `../../../.agents/skills/aws-data-modeling/SKILL.md`
- Backend Module: `../../AGENTS.md`
