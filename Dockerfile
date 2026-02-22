# Multi-stage Production Dockerfile for Agent_Guru Core Reasoning Engine
# Optimized for minimal size with Alpine base and layer caching

# Build stage
FROM python:3.11-alpine as builder

# Set working directory
WORKDIR /app

# Install build dependencies (cached layer)
RUN apk add --no-cache \
    git \
    build-base \
    curl \
    libffi-dev \
    openssl-dev \
    && rm -rf /var/cache/apk/*

# Copy dependency files first (cached layer if unchanged)
COPY pyproject.toml ./
COPY requirements.txt ./

# Install Python dependencies (cached layer)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir build wheel && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Copy source code
COPY Agent_Guru/ ./Agent_Guru/

# Build package
RUN python -m build

# Production stage - Alpine for minimal size
FROM python:3.11-alpine

# Build arguments
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=1.0.0

# Labels (OCI standard)
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.authors="Agent_Guru Team" \
      org.opencontainers.image.url="https://github.com/agent-guru/agent-guru" \
      org.opencontainers.image.source="https://github.com/agent-guru/agent-guru" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.title="Agent Guru Reasoning Engine" \
      org.opencontainers.image.description="Production-grade AI reasoning engine"

# Set working directory
WORKDIR /app

# Install runtime dependencies only (minimal set)
RUN apk add --no-cache \
    libffi \
    openssl \
    curl \
    ca-certificates \
    && rm -rf /var/cache/apk/*

# Create non-root user for security
RUN addgroup -g 1000 agentguru && \
    adduser -D -u 1000 -G agentguru agentguru && \
    chown -R agentguru:agentguru /app

# Copy wheels from builder
COPY --from=builder /wheels /wheels
COPY --from=builder /app/dist/*.whl /tmp/

# Install the package and dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --find-links=/wheels /tmp/*.whl && \
    rm -rf /tmp/*.whl /wheels

# Switch to non-root user
USER agentguru

# Expose port for API/monitoring
EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Default command for production
CMD ["python", "-m", "Agent_Guru.reasoning"]


