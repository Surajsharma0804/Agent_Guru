# Core Reasoning Engine - Project Structure

## Directory Layout

```
Agent_Guru/
└── reasoning/                          # Core Reasoning Engine Package
    ├── __init__.py                     # Package initialization
    ├── README.md                       # Documentation
    ├── STRUCTURE.md                    # This file
    │
    ├── models/                         # Data Models & Schemas
    │   ├── __init__.py
    │   ├── intent.py                   # Intent, IntentType, Entity
    │   ├── action.py                   # Action, Tool, Parameter
    │   ├── result.py                   # ExecutionResult, Response
    │   ├── error.py                    # Error, ErrorType, FallbackStrategy
    │   └── conversation.py             # ConversationState, ConversationTurn
    │
    ├── state/                          # Conversation State Management
    │   ├── __init__.py
    │   ├── manager.py                  # ConversationStateManager
    │   ├── persistence.py              # SQLite/PostgreSQL persistence
    │   └── cache.py                    # Redis caching layer
    │
    ├── tools/                          # Tool Registry & Execution
    │   ├── __init__.py
    │   ├── registry.py                 # Tool registration and discovery
    │   ├── selector.py                 # Tool selection engine
    │   ├── executor.py                 # Action execution controller
    │   └── builtin/                    # Built-in tools
    │       ├── timer.py
    │       ├── weather.py
    │       ├── messaging.py
    │       └── music.py
    │
    ├── config/                         # Configuration Management
    │   ├── __init__.py
    │   ├── settings.py                 # Application settings
    │   ├── llm_config.py               # LLM backend configuration
    │   └── latency_budgets.py          # Performance budgets
    │
    └── tests/                          # Test Suite
        ├── __init__.py
        ├── conftest.py                 # Pytest fixtures
        ├── test_models.py              # Model tests
        ├── test_state.py               # State management tests
        ├── test_tools.py               # Tool tests
        └── property/                   # Property-based tests
            ├── test_intent_properties.py
            ├── test_state_properties.py
            └── test_execution_properties.py
```

## Design Pattern

This structure follows the **modular package pattern** used throughout Agent_Guru:

- **Self-contained**: All reasoning engine components are within `Agent_Guru/reasoning/`
- **Clear separation**: Each subdirectory has a specific responsibility
- **Testable**: Tests are co-located with the code they test
- **Extensible**: Easy to add new models, tools, or state managers

## Comparison with Other Agent_Guru Components

```
Agent_Guru/
├── speech/                    # Speech Engine
│   ├── stt/                   # Speech-to-text
│   ├── tts/                   # Text-to-speech
│   ├── biometric/             # Voice biometrics
│   └── tests/                 # Tests
│
├── vision/                    # Vision Engine
│   ├── detection/             # Face detection
│   ├── recognition/           # Face recognition
│   ├── emotion/               # Emotion recognition
│   └── tests/                 # Tests
│
└── reasoning/                 # Reasoning Engine (NEW)
    ├── models/                # Data models
    ├── state/                 # State management
    ├── tools/                 # Tool execution
    ├── config/                # Configuration
    └── tests/                 # Tests
```

## Benefits of This Structure

1. **Consistency**: Matches the pattern used by `speech/`, `vision/`, etc.
2. **Encapsulation**: All reasoning logic is self-contained
3. **Discoverability**: Easy to find related code
4. **Maintainability**: Clear boundaries between components
5. **Scalability**: Easy to add new submodules as needed

## Import Patterns

```python
# Import models
from Agent_Guru.reasoning.models.intent import Intent, IntentType
from Agent_Guru.reasoning.models.action import Action, Tool

# Import state management
from Agent_Guru.reasoning.state.manager import ConversationStateManager

# Import tools
from Agent_Guru.reasoning.tools.registry import ToolRegistry
from Agent_Guru.reasoning.tools.executor import ActionExecutor

# Import configuration
from Agent_Guru.reasoning.config.settings import Settings
```

## Future Expansion

As the reasoning engine grows, we can add:

```
reasoning/
├── intent/                    # Intent detection engine
│   ├── detector.py
│   ├── classifier.py
│   └── ner.py
│
├── llm/                       # LLM reasoning core
│   ├── router.py
│   ├── prompts.py
│   └── backends/
│
├── safety/                    # Safety gate
│   ├── validator.py
│   ├── permissions.py
│   └── audit.py
│
└── response/                  # Response generation
    ├── generator.py
    └── templates/
```

This structure provides a solid foundation for building a production-grade reasoning engine!
