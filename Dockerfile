# Development Dockerfile for Agent_Guru Core Reasoning Engine
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[dev]"

# Copy application code
COPY Agent_Guru/ ./Agent_Guru/
COPY pyproject.toml ./

# Install pre-commit hooks
RUN pre-commit install || true

# Expose port for debugging/monitoring
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default command for development
CMD ["python", "-m", "pytest", "--cov", "-v"]
