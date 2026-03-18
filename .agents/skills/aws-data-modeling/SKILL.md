---
name: aws-data-modeling
description: Integration of AWS Database services and Boto3 for state persistence.
---

# Instructions for Persistence Layer

1. **Database Selection**: Use DynamoDB (NoSQL) for high-performance `user_id` lookups or PostgreSQL (RDS) if complex relations are expected.
2. **Index Optimization**:
    - If DynamoDB: Define a Global Secondary Index (GSI) on `user_id` for efficient pagination.
    - If RDS: Create an index on `user_id` and `created_at`.
3. **Initialization**: Provide a standalone Python script (`init_db.py`) to bootstrap tables/schemas programmatically.
4. **Concurrency Handling**: Implement non-blocking DB calls using `asyncio` to prevent I/O blocking during high-volume job listing.
5. **State Sync**: Log schema versions and connection strings (local vs prod) in `backend/AGENTS.md` [17, 18].

## Success Criteria
- Listing jobs by `user_id` executes in <100ms.
- Script provided to recreate the database from scratch.