# Multi-stage Production Dockerfile for Agent_Guru Core Reasoning Engine
#
# Base: python:3.11-slim (Debian/glibc) — required for PyTorch manylinux wheels.
#       Alpine (musl libc) cannot install PyTorch wheels.
#
# PyTorch: CPU-only build installed from download.pytorch.org/whl/cpu via a
#          dedicated requirements-torch.txt that embeds the --index-url directive.
#          GPU support is handled at runtime through host CUDA drivers; swap
#          requirements-torch.txt for the cu118/cu121 variant to build a GPU image.

# ─── Build stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests first so Docker layer cache is reused when only
# source code changes.
COPY requirements-torch.txt ./
COPY requirements-cpu.txt ./
COPY pyproject.toml ./

# 1. Upgrade pip/wheel tooling
# 2. Install PyTorch CPU wheels (index-url is embedded in requirements-torch.txt)
# 3. Pre-build wheels for all other CPU deps so the production stage never
#    needs a compiler.
RUN pip install --no-cache-dir --upgrade pip wheel build && \
    pip install --no-cache-dir -r requirements-torch.txt && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements-cpu.txt

# Copy source and build the distributable package
COPY Agent_Guru/ ./Agent_Guru/
COPY main.py ./
RUN python -m build

# ─── Production stage ────────────────────────────────────────────────────────
FROM python:3.11-slim

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=1.0.0

LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.authors="Agent_Guru Team" \
      org.opencontainers.image.url="https://github.com/agent-guru/agent-guru" \
      org.opencontainers.image.source="https://github.com/agent-guru/agent-guru" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.title="Agent Guru Reasoning Engine" \
      org.opencontainers.image.description="Production-grade AI reasoning engine"

WORKDIR /app

# Minimal runtime system deps (no compiler needed — wheels were pre-built)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 \
    libssl3 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN groupadd -g 1000 agentguru && \
    useradd -m -u 1000 -g agentguru agentguru && \
    chown -R agentguru:agentguru /app

# Bring in pre-built wheels and the distributable package from the builder
COPY --from=builder /wheels /wheels
COPY --from=builder /app/dist/*.whl /tmp/
COPY requirements-torch.txt ./

# Install in order:
#   1. PyTorch CPU (from its own index — embedded in requirements-torch.txt)
#   2. All other deps from pre-built wheels
#   3. The Agent Guru package itself
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-torch.txt && \
    pip install --no-cache-dir --find-links=/wheels /tmp/*.whl && \
    rm -rf /tmp/*.whl /wheels requirements-torch.txt

USER agentguru

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# In Docker, mic/screen access isn't available — this starts the
# LLM/API reasoning-only mode automatically.
CMD ["python", "main.py"]
