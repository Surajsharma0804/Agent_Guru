# Multi-stage Production Dockerfile for Agent Guru - Core Reasoning Engine API
#
# Design decisions:
#   - Base: python:3.11-slim (Debian/glibc). Alpine (musl) cannot install
#     manylinux wheels (numpy, cryptography, etc.) without recompiling.
#   - No PyTorch / OpenCV / Whisper / audio libs in this image.
#     Those require GPU drivers, system audio devices, and large model
#     downloads - none of which belong in a stateless API container.
#     The reasoning engine talks to LLM providers over HTTP; it does not
#     run local inference inside Docker.
#   - requirements-docker.txt contains only what the API actually needs.
#   - For GPU/local-inference builds, extend this image and add torch
#     via requirements-torch.txt separately.

# ─── Build stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System build deps - only what's needed to compile C extensions in the
# requirements-docker.txt set (cryptography, aiohttp, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy manifests first - Docker layer cache is reused when only source changes
COPY pyproject.toml ./
COPY requirements-docker.txt ./

# Pre-build all wheels so the production stage needs no compiler
RUN pip install --no-cache-dir --upgrade pip wheel build && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements-docker.txt

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
      org.opencontainers.image.url="https://github.com/Surajsharma0804/Agent_Guru" \
      org.opencontainers.image.source="https://github.com/Surajsharma0804/Agent_Guru" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.title="Agent Guru Reasoning Engine" \
      org.opencontainers.image.description="Production-grade AI reasoning engine API"

WORKDIR /app

# Minimal runtime system libs - no compiler, no dev headers
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

# Install pre-built wheels and the Agent Guru package.
# --find-links points pip at the local wheel cache so no PyPI calls needed.
COPY --from=builder /wheels /wheels
COPY --from=builder /app/dist/*.whl /tmp/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --find-links=/wheels /tmp/*.whl && \
    rm -rf /tmp/*.whl /wheels

USER agentguru

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Starts the reasoning API in HTTP-only mode (no mic/screen/GPU needed)
CMD ["python", "main.py"]
