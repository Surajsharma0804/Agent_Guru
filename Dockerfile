# AGENT_GURU Multi-stage Docker Build
# Enterprise-grade containerization with security hardening and optimization
# Zero-tolerance security standards with minimal attack surface

# ============================================================================
# BUILD STAGE - Rust compilation with security hardening
# ============================================================================
FROM rust:1.75-slim as rust-builder

# Security: Create non-root user for build
RUN groupadd -r builduser && useradd -r -g builduser builduser

# Install build dependencies with security updates
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    libssl-dev \
    libsodium-dev \
    libasound2-dev \
    libpulse-dev \
    libxcb1-dev \
    libxrandr-dev \
    libxss-dev \
    libglib2.0-dev \
    libgtk-3-dev \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set security-focused build environment
ENV RUSTFLAGS="-D warnings -D clippy::all -D clippy::pedantic -D clippy::nursery -C target-feature=+crt-static"
ENV CARGO_NET_GIT_FETCH_WITH_CLI=true
ENV CARGO_REGISTRIES_CRATES_IO_PROTOCOL=sparse

# Create secure build directory
WORKDIR /build
RUN chown builduser:builduser /build

# Copy dependency files first for better caching
COPY --chown=builduser:builduser Cargo.toml Cargo.lock ./
COPY --chown=builduser:builduser guru/Cargo.toml ./guru/

# Switch to non-root user
USER builduser

# Pre-build dependencies for caching
RUN cargo fetch

# Copy source code
COPY --chown=builduser:builduser . .

# Build with security optimizations
RUN cargo build --release --locked --offline \
    --target x86_64-unknown-linux-gnu \
    --bin agent-guru

# Strip debug symbols and optimize binary
RUN strip target/x86_64-unknown-linux-gnu/release/agent-guru

# ============================================================================
# PYTHON BUILD STAGE - Intelligence components
# ============================================================================
FROM python:3.11-slim as python-builder

# Security: Create non-root user
RUN groupadd -r pyuser && useradd -r -g pyuser pyuser

# Install Python build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create build directory
WORKDIR /build
RUN chown pyuser:pyuser /build

# Copy Python requirements
COPY --chown=pyuser:pyuser guru/intelligence/requirements.txt ./

# Switch to non-root user
USER pyuser

# Install Python dependencies with security flags
RUN pip install --no-cache-dir --user --upgrade pip \
    && pip install --no-cache-dir --user -r requirements.txt

# Copy and build Python components
COPY --chown=pyuser:pyuser guru/intelligence/ ./
RUN python -m py_compile *.py

# ============================================================================
# C++ BUILD STAGE - High-performance components
# ============================================================================
FROM ubuntu:22.04 as cpp-builder

# Security: Create non-root user
RUN groupadd -r cppuser && useradd -r -g cppuser cppuser

# Install C++ build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    ninja-build \
    libssl-dev \
    libsodium-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create build directory
WORKDIR /build
RUN chown cppuser:cppuser /build

# Copy C++ source
COPY --chown=cppuser:cppuser CMakeLists.txt ./
COPY --chown=cppuser:cppuser src/ ./src/

# Switch to non-root user
USER cppuser

# Build with security flags
RUN cmake -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_FLAGS="-Wall -Wextra -Wpedantic -Werror -O3 -D_FORTIFY_SOURCE=2 -fstack-protector-strong" \
    -DCMAKE_EXE_LINKER_FLAGS="-Wl,-z,relro,-z,now" \
    && cmake --build build --parallel

# ============================================================================
# SECURITY SCANNER STAGE - Vulnerability analysis
# ============================================================================
FROM aquasec/trivy:latest as security-scanner

# Copy built artifacts for scanning
COPY --from=rust-builder /build/target/x86_64-unknown-linux-gnu/release/agent-guru /scan/
COPY --from=python-builder /build/ /scan/python/
COPY --from=cpp-builder /build/build/ /scan/cpp/

# Run comprehensive security scan
RUN trivy fs --format sarif --output /scan-results.sarif /scan/

# ============================================================================
# RUNTIME STAGE - Minimal production image
# ============================================================================
FROM gcr.io/distroless/cc-debian12:latest as runtime

# Metadata labels for container registry
LABEL org.opencontainers.image.title="AGENT_GURU"
LABEL org.opencontainers.image.description="Sovereign AI Operating Companion"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.vendor="AGENT_GURU Project"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/agent-guru/agent-guru"
LABEL org.opencontainers.image.documentation="https://docs.agent-guru.com"

# Security: Run as non-root user (distroless provides nonroot user)
USER nonroot:nonroot

# Copy runtime dependencies
COPY --from=rust-builder --chown=nonroot:nonroot \
    /build/target/x86_64-unknown-linux-gnu/release/agent-guru \
    /usr/local/bin/agent-guru

COPY --from=python-builder --chown=nonroot:nonroot \
    /build/ \
    /opt/agent-guru/intelligence/

COPY --from=cpp-builder --chown=nonroot:nonroot \
    /build/build/lib/ \
    /usr/local/lib/

# Set runtime environment
ENV RUST_LOG=info
ENV RUST_BACKTRACE=1
ENV AGENT_GURU_CONFIG_PATH=/etc/agent-guru
ENV AGENT_GURU_DATA_PATH=/var/lib/agent-guru

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["/usr/local/bin/agent-guru", "--health-check"]

# Expose application port
EXPOSE 8080

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/agent-guru"]
CMD ["--daemon"]

# ============================================================================
# DEVELOPMENT STAGE - Development environment with tools
# ============================================================================
FROM rust:1.75-slim as development

# Install development tools
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    libssl-dev \
    libsodium-dev \
    libasound2-dev \
    libpulse-dev \
    python3 \
    python3-pip \
    git \
    curl \
    vim \
    gdb \
    valgrind \
    strace \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Rust development tools
RUN cargo install \
    cargo-audit \
    cargo-deny \
    cargo-tarpaulin \
    cargo-nextest \
    cargo-criterion \
    cargo-flamegraph

# Install Python development tools
RUN pip3 install \
    pytest \
    pytest-cov \
    hypothesis \
    pylint \
    black \
    mypy

# Create development user
RUN groupadd -r devuser && useradd -r -g devuser -s /bin/bash devuser
RUN mkdir -p /home/devuser && chown devuser:devuser /home/devuser

# Set development environment
ENV RUST_LOG=debug
ENV RUST_BACKTRACE=full
ENV CARGO_HOME=/home/devuser/.cargo
ENV PATH="/home/devuser/.cargo/bin:${PATH}"

# Create workspace
WORKDIR /workspace
RUN chown devuser:devuser /workspace

USER devuser

# Development entrypoint
ENTRYPOINT ["/bin/bash"]

# ============================================================================
# TESTING STAGE - Comprehensive testing environment
# ============================================================================
FROM development as testing

# Install additional testing tools
USER root
RUN apt-get update && apt-get install -y \
    lcov \
    gcovr \
    cppcheck \
    clang-tidy \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install specialized testing tools
RUN cargo install \
    cargo-fuzz \
    cargo-mutants \
    cargo-geiger

USER devuser

# Set testing environment
ENV RUST_TEST_THREADS=1
ENV PROPTEST_CASES=10000
ENV HYPOTHESIS_MAX_EXAMPLES=10000

# Testing entrypoint
ENTRYPOINT ["cargo", "test"]