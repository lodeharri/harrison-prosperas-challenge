# Reto Prosperas - Dockerfile
# Multi-stage optimized build for Python 3.11

# =============================================================================
# Stage 1: Builder - Install dependencies
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# =============================================================================
# Stage 2: Runtime - Minimal production image
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Copy application code (context is ./backend, so . copies everything inside)
COPY --chown=appuser:appuser . /app/backend/

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/backend

# Expose port for FastAPI
EXPOSE 8000

# Default command - can be overridden in docker-compose
# Import path: src.adapters.primary.fastapi.main means /app/backend/src/adapters/primary/fastapi/main.py
CMD ["uvicorn", "src.adapters.primary.fastapi.main:app", "--host", "0.0.0.0", "--port", "8000"]
