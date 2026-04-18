# Agent Guru — Module Dependency Graph
*Generated: 2026-04-18*

## Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Application Layer                                      │
│  speech  vision  avatar  emotion  translation           │
├─────────────────────────────────────────────────────────┤
│  Intelligence Layer                                     │
│  reasoning  llm  memory  learning  self_improvement     │
├─────────────────────────────────────────────────────────┤
│  Orchestration Layer                                    │
│  agents  goal_manager  policy  verifier  integration    │
├─────────────────────────────────────────────────────────┤
│  Infrastructure Layer                                   │
│  platform  security  deployment  health  resilience     │
└─────────────────────────────────────────────────────────┘
```

## Critical Dependencies

```
integration/orchestrator.py
  ├── speech/engine.py
  │     ├── speech/audio/wake_word.py
  │     ├── speech/stt_manager.py
  │     └── speech/tts_manager.py
  ├── vision/engine.py
  │     ├── vision/detection/detector.py
  │     ├── vision/recognition/recognizer.py
  │     └── vision/emotion/recognizer.py
  ├── llm/llm_runtime.py
  │     ├── llm/providers/openai_adapter.py
  │     ├── llm/providers/google_adapter.py
  │     ├── llm/providers/anthropic_adapter.py
  │     └── llm/providers/ollama_adapter.py
  ├── reasoning/engine.py
  │     ├── reasoning/intent/engine.py
  │     ├── reasoning/execution/executor.py
  │     └── reasoning/knowledge/synthesizer.py
  ├── memory/memory_manager.py
  │     ├── memory/knowledge_graph.py
  │     └── memory/conversation_memory.py
  ├── agents/orchestrator.py
  │     └── platform/os_controller.py
  ├── security/security_system.py
  │     ├── security/biometric_auth.py
  │     └── security/crypto/identity.py
  └── policy/engine.py
```

## Zero-Dependency Modules (leaf nodes)

- `utils/path_utils.py`
- `security/path_utils.py`
- `training/seed_utils.py`
- `resilience/cache.py`

## Circular Dependency Check

No circular imports detected. All dependencies flow downward through layers.
