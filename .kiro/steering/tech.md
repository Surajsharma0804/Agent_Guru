# Agent Guru - Technical Stack

## Language & Architecture

**Primary Language**: Python 3.11+ (AI/ML optimized, Python-first architecture)

Python chosen for:
- Best AI/ML ecosystem (speech, vision, LLM)
- GPU acceleration built-in (PyTorch, ONNX Runtime)
- Rapid development (10x faster than alternatives)
- Massive library ecosystem for all components

## Core Technologies

### AI/ML Frameworks
- **PyTorch** (>=2.0.0): Deep learning with CUDA support
- **ONNX Runtime GPU** (>=1.15.0): Optimized inference
- **Transformers** (>=4.30.0): NLP models
- **OpenAI Whisper**: Speech-to-text with GPU acceleration
- **faster-whisper** (>=0.9.0): Optimized Whisper inference

### Computer Vision
- **InsightFace** (>=0.7.3): Face recognition (ArcFace, RetinaFace)
- **OpenCV** (>=4.8.0): Computer vision operations
- **ONNX Runtime**: Real-time face detection and recognition

### Speech Processing
- **pvporcupine**: Wake word detection ("Hey Guru", "Hey Maya")
- **librosa** (>=0.10.0): Audio processing
- **pyaudio** (>=0.2.13): Audio I/O
- **webrtcvad** (>=2.0.10): Voice activity detection

### LLM Integration
- **openai** (>=1.0.0): OpenAI API client
- **google-generativeai** (>=0.3.0): Gemini API
- **anthropic** (>=0.7.0): Claude API
- **ollama**: Local LLM runtime (desktop only)

### Platform Integration
- **pywin32** (>=306): Windows API (Windows only)
- **pyobjc**: macOS Objective-C bindings (macOS only)
- **dbus-python** (>=1.3.2): Linux D-Bus (Linux only)
- **psutil** (>=5.9.0): Cross-platform system info

### Data & Storage
- **pydantic** (>=2.5.0): Data validation and settings
- **SQLAlchemy** (>=2.0.0): Database ORM
- **aiosqlite** (>=0.19.0): Async SQLite
- **chromadb / faiss**: Vector databases for semantic search

### Async & Concurrency
- **asyncio**: Built-in async/await support
- **aiohttp** (>=3.8.0): Async HTTP client
- **httpx** (>=0.24.0): Modern HTTP client

### Monitoring & Observability
- **structlog** (>=23.2.0): Structured logging
- **prometheus-client** (>=0.19.0): Metrics collection
- **opentelemetry**: Distributed tracing
- **sentry-sdk** (>=1.39.0): Error tracking

### Security
- **cryptography** (>=41.0.0): Encryption and crypto operations
- **pyjwt** (>=2.8.0): JWT tokens
- **keyring**: Secure key storage in OS keychain

## GPU Acceleration

**CUDA Support**: NVIDIA GPU acceleration for:
- Speech recognition (Whisper): 10-50x faster
- Face recognition: 30-60 FPS real-time
- Emotion detection: <50ms latency

**Installation**:
```bash
# CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

## Code Quality Tools

### Formatting & Linting
- **black** (>=23.0.0): Code formatter (line-length=100)
- **ruff** (>=0.1.9): Fast Python linter
- **isort** (>=5.12.0): Import sorting

### Type Checking
- **mypy** (>=1.8.0): Static type checker (strict mode enabled)
- Type stubs for external libraries

### Security
- **bandit** (>=1.7.6): Security issue scanner
- **safety** (>=2.3.5): Dependency vulnerability checker

### Pre-commit Hooks
Configured in `.pre-commit-config.yaml`:
- Trailing whitespace removal
- End-of-file fixer
- YAML/JSON/TOML validation
- Black formatting
- Ruff linting with auto-fix
- Mypy type checking
- Bandit security scanning

## Testing Framework

### Test Tools
- **pytest** (>=7.4.0): Test framework
- **pytest-asyncio** (>=0.21.0): Async test support
- **pytest-cov** (>=4.1.0): Coverage reporting
- **hypothesis** (>=6.92.0): Property-based testing

### Test Configuration
- Test paths: `Agent_Guru/reasoning/tests`
- Coverage target: 80% minimum
- Async mode: auto
- Markers: property, unit, integration, slow

### Property-Based Testing
- Hypothesis max_examples: 100
- Derandomize in CI for reproducibility
- All correctness properties must be validated with PBT

## Common Commands

### Development Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install dependencies (GPU)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt

# Install dev dependencies
pip install -r requirements.txt[dev]

# Setup pre-commit hooks
pre-commit install
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=Agent_Guru --cov-report=html

# Run specific test types
pytest -m unit          # Unit tests only
pytest -m property      # Property-based tests only
pytest -m integration   # Integration tests only

# Run tests for specific module
pytest Agent_Guru/reasoning/tests/
```

### Code Quality
```bash
# Format code
black Agent_Guru/

# Lint code
ruff check Agent_Guru/ --fix

# Type check
mypy Agent_Guru/

# Security scan
bandit -r Agent_Guru/

# Run all pre-commit hooks
pre-commit run --all-files
```

### GPU Verification
```bash
# Verify GPU setup
python verify_setup.py

# Check CUDA availability
python -c "import torch; print(torch.cuda.is_available())"
```

### Build & Package
```bash
# Build package
python -m build

# Install in editable mode
pip install -e .
```

## Performance Targets

- Wake word detection: <200ms latency
- Speech recognition: <1s (with GPU)
- LLM response: <2s end-to-end
- Face recognition: 30-60 FPS
- Emotion detection: <50ms
- Avatar rendering: 60 FPS

## Configuration Files

- `pyproject.toml`: Project metadata, dependencies, tool configs
- `pytest.ini`: Test configuration
- `mypy.ini`: Type checking configuration
- `.pre-commit-config.yaml`: Pre-commit hooks
- `requirements.txt`: GPU dependencies
- `requirements-cpu.txt`: CPU-only dependencies
