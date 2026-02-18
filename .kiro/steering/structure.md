# Agent Guru - Project Structure

## Root Directory Layout

```
Agent_Guru/
├── Agent_Guru/              # Main Python package (all implementation code)
├── .kiro/                   # Kiro IDE configuration and specifications
├── .github/                 # GitHub workflows and CI/CD
├── .hypothesis/             # Hypothesis property-based testing cache
├── assets/                  # Static assets (logos, images)
├── grafana/                 # Monitoring dashboards and provisioning
├── k8s/                     # Kubernetes deployment configs
├── htmlcov/                 # Test coverage reports (generated)
├── pyproject.toml           # Project metadata and tool configuration
├── requirements.txt         # Python dependencies (GPU)
├── requirements-cpu.txt     # Python dependencies (CPU-only)
├── pytest.ini               # Pytest configuration
├── mypy.ini                 # Type checking configuration
├── .pre-commit-config.yaml  # Pre-commit hooks
└── README.md                # Project documentation
```

## Main Package Structure (Agent_Guru/)

The `Agent_Guru/` directory contains all implementation code organized by functional domain:

```
Agent_Guru/
├── __init__.py              # Package initialization
│
├── speech/                  # Speech Engine - Voice I/O
│   ├── __init__.py
│   ├── wake_word.py         # Wake word detection (Guru/Maya)
│   ├── stt.py               # Speech-to-text (Whisper)
│   ├── tts.py               # Text-to-speech (gender-specific)
│   ├── biometric.py         # Voice biometrics
│   ├── vad.py               # Voice activity detection
│   └── engine.py            # Main speech engine coordinator
│
├── vision/                  # Vision Engine - Face recognition & emotion
│   ├── __init__.py
│   ├── detection.py         # Face detection (RetinaFace)
│   ├── recognition.py       # Face recognition (ArcFace)
│   ├── liveness.py          # Liveness detection (anti-spoofing)
│   ├── emotion.py           # Emotion recognition
│   ├── tracking.py          # Face tracking (DeepSORT/ByteTrack)
│   └── engine.py            # Main vision engine coordinator
│
├── llm/                     # LLM Runtime - Model execution
│   ├── __init__.py
│   ├── providers/           # LLM provider implementations
│   │   ├── __init__.py
│   │   ├── ollama.py        # Local Ollama (desktop only)
│   │   ├── openai.py        # OpenAI API
│   │   ├── gemini.py        # Google Gemini
│   │   └── anthropic.py     # Anthropic Claude
│   ├── router.py            # Intelligent model routing
│   ├── context.py           # Context management
│   └── runtime.py           # Main LLM runtime coordinator
│
├── platform/                # Platform Integration - OS control
│   ├── __init__.py
│   ├── windows.py           # Windows-specific integration
│   ├── macos.py             # macOS-specific integration
│   ├── linux.py             # Linux-specific integration
│   ├── android.py           # Android-specific integration
│   ├── ios.py               # iOS-specific integration
│   └── controller.py        # Cross-platform controller
│
├── agents/                  # Agent Orchestration - Multi-agent coordination
│   ├── __init__.py
│   └── orchestrator.py      # Agent coordination and task decomposition
│
├── memory/                  # Memory System - Knowledge and context
│   ├── __init__.py
│   ├── semantic_index.py    # Semantic search with vector embeddings
│   ├── temporal_graph.py    # Temporal knowledge graph
│   └── encryption.py        # Memory encryption
│
├── reasoning/               # Core Reasoning Engine (currently in development)
│   ├── __init__.py
│   ├── tests/               # Reasoning engine tests
│   └── ...                  # Reasoning components
│
├── deployment/              # Deployment System - Packaging & distribution
│   ├── __init__.py
│   ├── package_manager.py   # Package management
│   ├── installer_builder.py # Installer creation (MSI, DMG, APK, IPA)
│   └── onboarding.py        # User onboarding flow
│
├── security/                # Security & Cryptography - Trust & safety
│   ├── __init__.py
│   ├── crypto_identity.py   # Cryptographic identity (Ed25519)
│   ├── biometric_auth.py    # Biometric authentication
│   └── audit_log.py         # Security audit logging
│
├── policy/                  # Policy Engine - Governance & constraints
│   ├── __init__.py
│   └── policy_engine.py     # Policy evaluation and enforcement
│
└── avatar/                  # Avatar & Emotion - Personality & visualization
    ├── __init__.py
    ├── emotion_controller.py # Emotion engine and mood tracking
    └── avatar_renderer.py    # Avatar rendering and animation
```

## Specifications Directory (.kiro/specs/)

Complete specifications for all components following the spec-driven development methodology:

```
.kiro/specs/
├── README.md                        # Specifications overview
├── VERIFICATION_COMPLETE.md         # Requirements verification
│
├── guru-complete-integration/       # Master integration spec (START HERE)
│   ├── requirements.md              # Integration requirements
│   ├── design.md                    # Integration architecture
│   └── tasks.md                     # 29 executable tasks
│
├── guru-speech-engine/              # Speech engine specification
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md                     # 28 tasks
│
├── guru-llm-runtime/                # LLM runtime specification
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
│
├── guru-platform-integration/       # Platform integration specification
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md                     # 20 tasks
│
├── guru-agent-orchestration/        # Agent orchestration specification
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
│
├── guru-memory-system/              # Memory system specification
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
│
├── guru-deployment-system/          # Deployment specification
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
│
├── guru-security-cryptography/      # Security specification
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
│
├── guru-policy-engine/              # Policy engine specification
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
│
├── avatar-emotion-system/           # Avatar & emotion specification
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md                     # 23 tasks
│
├── guruvision-facial-recognition/   # Vision system specification
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
│
├── self-improvement-engine/         # Self-improvement specification
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
│
├── model-router/                    # Model routing specification
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
│
├── goal-manager/                    # Goal management specification
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
│
├── verifier-system/                 # Verification system specification
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
│
└── core-reasoning-engine/           # Core reasoning specification
    ├── requirements.md
    ├── design.md
    └── tasks.md
```

## Specification File Structure

Each spec follows a consistent three-file pattern:

1. **requirements.md**: What needs to be built
   - User stories
   - Acceptance criteria
   - Functional requirements
   - Non-functional requirements

2. **design.md**: How to build it
   - Architecture overview
   - Component interfaces
   - Data models
   - Correctness properties (for property-based testing)
   - Implementation details

3. **tasks.md**: Step-by-step implementation
   - Numbered tasks with clear objectives
   - Sub-tasks for complex work
   - Testing requirements per task
   - Task status tracking ([ ], [x], [-], [~])

## Module Organization Principles

### Separation of Concerns
Each top-level module handles a distinct functional domain:
- `speech/`: All voice interaction
- `vision/`: All visual processing
- `llm/`: All language model operations
- `platform/`: All OS-specific operations
- `agents/`: All multi-agent coordination
- `memory/`: All knowledge storage and retrieval
- `security/`: All cryptography and authentication
- `policy/`: All permission and governance
- `avatar/`: All personality and emotion
- `deployment/`: All packaging and distribution

### Coordinator Pattern
Each major module has an `engine.py` or `controller.py` that:
- Coordinates sub-components
- Provides high-level API
- Manages lifecycle and state
- Handles error recovery

### Platform Abstraction
Platform-specific code isolated in `platform/`:
- `windows.py`, `macos.py`, `linux.py` for desktop
- `android.py`, `ios.py` for mobile
- `controller.py` provides unified cross-platform API

### Provider Pattern
Multiple implementations for external services in `llm/providers/`:
- Each provider implements common interface
- Router selects optimal provider
- Easy to add new providers

## Testing Structure

Tests co-located with implementation or in dedicated test directories:

```
Agent_Guru/reasoning/tests/
├── test_*.py                # Unit tests
├── test_*_property.py       # Property-based tests
└── conftest.py              # Pytest fixtures
```

Test markers for organization:
- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.property`: Property-based tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.slow`: Long-running tests

## Configuration Files Location

- Root level: Project-wide configuration
  - `pyproject.toml`: Python project metadata, dependencies, tool configs
  - `pytest.ini`: Test framework configuration
  - `mypy.ini`: Type checker configuration
  - `.pre-commit-config.yaml`: Pre-commit hooks

- `.kiro/`: Kiro IDE specific
  - `.kiro/specs/`: All specifications
  - `.kiro/steering/`: Steering documents (this file)

## Import Conventions

Use absolute imports from package root:

```python
# Good
from Agent_Guru.speech import engine
from Agent_Guru.llm.providers import openai
from Agent_Guru.platform import controller

# Avoid relative imports for clarity
```

## File Naming Conventions

- Python modules: `snake_case.py`
- Test files: `test_*.py` or `*_test.py`
- Configuration: lowercase with extensions (`.yaml`, `.toml`, `.ini`)
- Documentation: `UPPERCASE.md` for important docs, `lowercase.md` for others
- Specs: `requirements.md`, `design.md`, `tasks.md` (consistent across all specs)

## Development Workflow

1. Start with spec: Read `.kiro/specs/{component}/requirements.md` and `design.md`
2. Follow tasks: Implement according to `.kiro/specs/{component}/tasks.md`
3. Write code: Add implementation to `Agent_Guru/{module}/`
4. Write tests: Add tests with 80%+ coverage
5. Run quality checks: `black`, `ruff`, `mypy`, `pytest`
6. Commit and push: After each completed task

## Key Architectural Layers

```
┌─────────────────────────────────────────────────────────┐
│  Application Layer (speech, vision, avatar)             │
├─────────────────────────────────────────────────────────┤
│  Intelligence Layer (llm, memory, reasoning)            │
├─────────────────────────────────────────────────────────┤
│  Orchestration Layer (agents, policy, verifier)         │
├─────────────────────────────────────────────────────────┤
│  Infrastructure Layer (platform, security, deployment)  │
└─────────────────────────────────────────────────────────┘
```

Each layer depends only on layers below it, maintaining clean separation.
