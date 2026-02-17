# Core Reasoning Engine

Production-ready reasoning engine for Agent_Guru that rivals Alexa/Siri in 2026.

## Overview

The Core Reasoning Engine is the central decision-making system for Agent_Guru, designed as a production-grade pipeline that transforms user inputs into executed actions with appropriate responses.

## Target Performance

- Average response time: <1.0s (vs 1.3-1.5s for competitors)
- P95 latency: <1.5s
- Intent detection accuracy: >95%
- Uptime: 99.9%

## Technology Stack

- Python 3.11+
- Hybrid LLM (local Llama 3.2 + cloud GPT-4)
- Fine-tuned neural models
- Kubernetes deployment

## Project Structure

```
Agent_Guru/
└── reasoning/              # Core Reasoning Engine
    ├── models/            # Data models and schemas (Pydantic)
    ├── state/             # Conversation state management
    ├── tools/             # Tool registry and execution
    ├── config/            # Configuration management
    ├── tests/             # Test suite (unit + property-based)
    ├── __init__.py        # Package initialization
    └── README.md          # This file
```

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git
- Docker (optional, for containerized development)

### Quick Start

#### Linux/macOS

```bash
# Run the setup script
chmod +x setup_dev.sh
./setup_dev.sh

# Activate virtual environment
source venv/bin/activate

# Run tests
pytest
```

#### Windows

```cmd
# Run the setup script
setup_dev.bat

# Activate virtual environment
venv\Scripts\activate.bat

# Run tests
pytest
```

### Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate.bat  # Windows

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest --cov
```

### Docker Development

```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f reasoning-engine

# Run tests in container
docker-compose exec reasoning-engine pytest

# Stop services
docker-compose down
```

## Development Workflow

### Code Quality

The project uses several tools to maintain code quality:

- **Black**: Code formatting (line length: 100)
- **Ruff**: Fast Python linter
- **Mypy**: Static type checking (strict mode)
- **Pre-commit**: Automated checks before commits

```bash
# Format code
black Agent_Guru/reasoning

# Lint code
ruff check Agent_Guru/reasoning

# Type check
mypy Agent_Guru/reasoning

# Run all checks
pre-commit run --all-files
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test file
pytest Agent_Guru/reasoning/tests/test_intent.py

# Run property-based tests only
pytest -k "property"

# Run with verbose output
pytest -v
```

### Type Checking

The project uses strict mypy configuration:

```bash
# Check all files
mypy Agent_Guru/reasoning

# Check specific file
mypy Agent_Guru/reasoning/engine.py
```

## Documentation

- **Requirements**: `.kiro/specs/core-reasoning-engine/requirements.md`
- **Design**: `.kiro/specs/core-reasoning-engine/design.md`
- **Tasks**: `.kiro/specs/core-reasoning-engine/tasks.md`

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and quality checks
4. Commit (pre-commit hooks will run automatically)
5. Push and create a pull request

## CI/CD

The project uses GitHub Actions for continuous integration:

- Linting (black, ruff, mypy)
- Unit tests with coverage (80% minimum)
- Property-based tests (Hypothesis)
- Security scanning (bandit, safety)

See `.github/workflows/ci.yml` for details.

