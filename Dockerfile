# ==============================================================================
# NovaEnterprise Backend Containerfile (Default root build)
# Multi-stage production build enforcing non-root user execution
# ==============================================================================

# Stage 1: Dependency builder
FROM python:3.11-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /build/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Minimal runtime image
FROM python:3.11-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8001 \
    HOST=0.0.0.0

# Create non-root system group and user
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/sh -d /app appuser

# Copy isolated virtualenv from builder stage
COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv

# Copy backend source modules and data dependencies
COPY --chown=appuser:appuser backend/ /app/backend/
COPY --chown=appuser:appuser rag/ /app/rag/
COPY --chown=appuser:appuser agents/ /app/agents/
COPY --chown=appuser:appuser memory/ /app/memory/
COPY --chown=appuser:appuser database/ /app/database/
COPY --chown=appuser:appuser migrations/ /app/migrations/
COPY --chown=appuser:appuser sample_data/ /app/sample_data/
COPY --chown=appuser:appuser alembic.ini /app/alembic.ini

# Create application data directory with non-root ownership
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

# Non-root user gate
USER appuser

# Expose backend REST API port
EXPOSE 8001

# Liveness health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health/live')"

# Start FastAPI application with Uvicorn
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
