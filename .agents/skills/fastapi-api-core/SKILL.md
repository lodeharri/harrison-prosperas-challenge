---
name: fastapi-api-core
description: Implementation of a secure, asynchronous REST API using FastAPI and JWT.
---

# Instructions for Backend Implementation

1. **Architecture**: Implement a global error handler using `@app.exception_handler` to centralize response formatting.
2. **Security**: Build a stateless JWT authentication module (HS256) for the `/jobs` endpoints.
3. **Contract Definition**: 
    - Use Pydantic v2 `BaseModel` for request/response validation [14].
    - Implement the `Job` schema with: `job_id`, `user_id`, `status`, `report_type`, `created_at`, `updated_at`, `result_url`.
4. **Endpoint Logic**:
    - `POST /jobs`: Asynchronously publish to SQS using `aiobotocore` or `boto3`.
    - `GET /jobs`: Implement offset-based or cursor-based pagination (min 20 items/page).
5. **Documentation**: Ensure `/docs` (Swagger) is correctly annotated with security schemes.

## Success Criteria
- All payloads validated via Pydantic v2.
- JWT tokens required for all Job-related endpoints.