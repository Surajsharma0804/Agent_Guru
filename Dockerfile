# Multi-stage Production Dockerfile for Agent_Guru Core Reasoning Engine
# Uses python:3.11-slim (Debian/glibc) so PyTorch wheels resolve correctly.
# GPU acceleration is handled at runtime via CUDA drivers on the host —
# the image itself installs the CPU-only torch build to keep image size
# manageable and avoid needing a GPU on the CI runner.

# Build stage
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies (cached layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (cached layer if unchanged)
COPY pyproject.toml ./
COPY requirements.txt ./
COPY requirements-cpu.txt ./

# Install Python dependencies (cached layer)
# We use the CPU-only PyTorch index so the build works on any runner
# (including CI machines without a GPU). At runtime, if a CUDA-capable
# GPU is present, swap the image for one built with the cu118/cu121 index.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir build wheel && \
    pip install --no-cache-dir \
        torch>=2.0.0 torchvision>=0.15.0 torchaudio>=2.0.0 \
        --index-url https://download.pytorch.org/whl/cpu && \
    pip wheel --no-cache-dir --wheel-dir /wheels \
        --find-links https://download.pytorch.org/whl/cpu \
        -r requirements-cpu.txt

# Copy source code
COPY Agent_Guru/ ./Agent_Guru/
COPY main.py ./

# Build package
RUN python -m build

# Production stage — slim for a smaller final image
FROM python:3.11-slim

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
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 \
    libssl3 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -g 1000 agentguru && \
    useradd -m -u 1000 -g agentguru agentguru && \
    chown -R agentguru:agentguru /app

# Copy wheels from builder
COPY --from=builder /wheels /wheels
COPY --from=builder /app/dist/*.whl /tmp/

# Install torch (CPU) first from the PyTorch index, then install the
# rest of the dependencies from the pre-built wheels, then the package.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        torch>=2.0.0 torchvision>=0.15.0 torchaudio>=2.0.0 \
        --index-url https://download.pytorch.org/whl/cpu && \
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

# Default command — runs the full voice assistant entry point
# NOTE: mic/screen access requires running on the HOST, not in Docker.
# In Docker this starts the LLM/API reasoning-only mode.
CMD ["python", "main.py"]


