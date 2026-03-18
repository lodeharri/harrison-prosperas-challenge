---
name: aws-observability-bootstrap
description: Standardization of AWS X-Ray and CloudWatch instrumentation for FastAPI and Boto3.
---

# Instructions for Telemetry Implementation

1. **Middleware Setup**: Install and configure `aws-xray-sdk`. Wrap the FastAPI app with `XRayMiddleware`.
2. **Async Instrumentation**: Patch `aiobotocore` or `boto3` libraries programmatically to ensure all AWS service calls generate sub-segments in X-Ray.
3. **Log Correlation**: Implement a logging filter that extracts the X-Ray `Trace-ID` and injects it into every log record.
4. **Health Metrics**: Create a background task that reports the internal queue size (SQS) to CloudWatch every 60 seconds.
5. **Validation**: Use `bash` to run a smoke test and verify that logs appear in the local CloudWatch emulator (LocalStack) or real AWS [8].

## Technical Stack
- AWS X-Ray SDK for Python
- Python `logging` with JSON formatter
- Custom CloudWatch Metrics (Namespace: `App/Jobs`)