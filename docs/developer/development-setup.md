# Agent Guru - Development Setup

## Prerequisites

- Python 3.11+
- Git
- NVIDIA GPU with CUDA 11.8+ (optional but recommended)

## Setup

```bash
# Clone repository
git clone https://github.com/agent-guru/agent-guru.git
cd agent-guru

# Create virtual environment
python -m venv venv
venv\Scripts\activate     # Windows
source venv/bin/activate  # macOS/Linux

# Install GPU dependencies (CUDA 11.8)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install project dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install -e ".[dev]"

# Setup pre-commit hooks
pre-commit install

# Verify setup
python installer/verify_requirements.py
```

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=Agent_Guru --cov-report=html

# Specific test types
pytest -m unit          # Unit tests
pytest -m property      # Property-based tests (Hypothesis)
pytest -m integration   # Integration tests

# Specific module
pytest Agent_Guru/core/tests/
pytest Agent_Guru/security/tests/

# Single run (no watch mode)
pytest --no-header -q
```

## Code Quality

```bash
# Format
black Agent_Guru/ --line-length 100

# Lint
ruff check Agent_Guru/ --fix

# Type check
mypy Agent_Guru/ --strict

# Security scan
bandit -r Agent_Guru/ -ll

# All pre-commit hooks
pre-commit run --all-files
```

## Project Structure

```
Agent_Guru/
├── core/           # Pipeline, error handling, performance
├── speech/         # Wake word, STT, TTS, audio pipeline
├── vision/         # Face recognition, emotion detection
├── llm/            # LLM providers, intent parser, router
├── platform/       # OS-specific controllers
├── agents/         # Multi-agent orchestration
├── memory/         # Conversation memory
├── security/       # Privacy controls, auth
├── policy/         # Policy engine
├── avatar/         # Emotion and avatar rendering
└── deployment/     # Packaging and distribution

installer/          # Windows NSIS + macOS DMG installers
docs/               # User and developer documentation
.kiro/specs/        # Spec-driven development specs
```

## Adding a New Feature

1. Create spec in `.kiro/specs/{feature-name}/`
2. Write `requirements.md`, `design.md`, `tasks.md`
3. Implement in `Agent_Guru/{module}/`
4. Write property-based tests with Hypothesis
5. Run `pytest -m property` to validate
6. Run `pre-commit run --all-files`
7. Open PR with spec + implementation

## Spec-Driven Development

All features follow the spec workflow:
1. **Requirements** - What to build (user stories, acceptance criteria)
2. **Design** - How to build it (architecture, correctness properties)
3. **Tasks** - Step-by-step implementation with PBT validation

See `.kiro/specs/` for all existing specs.

## Property-Based Testing

All correctness properties use Hypothesis:

```python
from hypothesis import given, settings, strategies as st

@given(n=st.integers(min_value=1, max_value=100))
@settings(max_examples=100, deadline=None)
def test_my_property(n: int) -> None:
    # Property must hold for all valid inputs
    result = my_function(n)
    assert invariant(result)
```

Minimum 100 examples per property. Use `deadline=None` for slow operations.
