# Exponential Backoff for AWS Client Creation

## Modified Files

1. **backend/worker/backoff.py**
   - Added `exponential_backoff_sync()` – synchronous version of the backoff calculator.
   - Added `retry_with_backoff_sync()` – synchronous retry wrapper using `time.sleep`.
   - Updated type hints to use `Awaitable` for async version and `Any` for `*args`/`**kwargs`.

2. **backend/src/config/settings.py**
   - Added `backoff_base_delay: float = 1.0` and `backoff_max_delay: float = 60.0` to the Settings class.

3. **backend/src/adapters/secondary/dynamodb/job_repository.py**
   - Imported `retry_with_backoff_sync` and retryable exceptions (`ClientError`, `ConnectionError`, `EndpointConnectionError`, `ReadTimeoutError`, `ConnectTimeoutError`).
   - Wrapped `boto3.client` calls in the `client` property with retry.
   - Wrapped `boto3.resource` calls in `jobs_table` and `idempotency_table` properties with retry.
   - Max attempts computed as `min(5, int(max_delay / base_delay) + 1)`.

4. **backend/src/adapters/secondary/sqs/job_queue.py**
   - Imported `retry_with_backoff_sync` and retryable exceptions.
   - Wrapped `boto3.client` call in the `client` property with retry.

5. **backend/worker/sqs_client.py**
   - Imported `retry_with_backoff` and retryable exceptions.
   - Added helper `_create_client_with_retry()` that wraps `session.create_client` with async retry.
   - Replaced all `session.create_client` calls in `receive_messages`, `delete_message`, `send_to_dlq`, `change_visibility_timeout`, and `health_check` with `await self._create_client_with_retry(...)`.
   - Fixed indentation issues in `health_check` inner try‑except block.

6. **backend/worker/dynamodb_client.py**
   - Imported `retry_with_backoff` and retryable exceptions.
   - Added helper `_create_client_with_retry()` that wraps `session.create_client` with async retry.
   - Replaced `session.create_client` calls in `get_job`, `update_job_status`, and `health_check` with `await self._create_client_with_retry(...)`.

## Summary of Changes

- **Exponential backoff for client creation only**: Retry logic is applied exclusively to the creation of AWS clients (`boto3.client`, `boto3.resource`, `aiobotocore session.create_client`). Subsequent operations (e.g., `receive_message`, `put_item`) are **not** retried.
- **Synchronous retry for backend adapters**: Uses `time.sleep` and the new synchronous backoff functions.
- **Asynchronous retry for worker adapters**: Uses `asyncio.sleep` and the existing async backoff functions.
- **Retryable exceptions**: Includes `ClientError`, `ConnectionError`, `EndpointConnectionError`, `ReadTimeoutError`, and `ConnectTimeoutError`. Configuration errors (invalid credentials, parameter validation) are not explicitly filtered; they will also trigger a retry (a possible improvement would be to examine error codes).
- **Configurable via Settings**: Both backend and worker settings now expose `backoff_base_delay` and `backoff_max_delay` (default 1.0 s and 60 s respectively). Max attempts is derived as `min(5, max_delay / base_delay + 1)`.

## Test Suggestions

1. **Unit tests for synchronous backoff**: Add tests for `exponential_backoff_sync` and `retry_with_backoff_sync` in `backend/worker/tests/test_backoff.py`.
2. **Integration tests for retry behavior**: Mock `boto3.client`/`boto3.resource` to raise retryable exceptions and verify that the retry loop is invoked the correct number of times.
3. **Configuration tests**: Ensure that changes to `backoff_base_delay` and `backoff_max_delay` environment variables are reflected in the retry behavior.
4. **Regression tests**: Run the existing test suite (already passing) to confirm no regressions.
5. **Error‑code filtering**: Consider adding a filter to exclude non‑transient `ClientError` codes (e.g., `InvalidClientTokenId`, `SignatureDoesNotMatch`, `ValidationException`) from retry.

## Verification

All existing tests pass:
- `backend/worker/tests/test_backoff.py` – 18 passed.
- `backend/tests/unit/adapters/test_job_repository.py` – 28 passed.
- `backend/tests/unit/adapters/test_job_queue.py` – 13 passed.
- `backend/worker/tests/` – 43 passed.

Imports of all modified modules succeed without error.

## Notes

- No new dependencies were added; only existing modules are imported.
- The changes follow hexagonal architecture and dependency‑injection principles (settings are injected, not hardcoded).
- The retry logic is limited to client creation, satisfying the requirement that operations themselves are not retried.