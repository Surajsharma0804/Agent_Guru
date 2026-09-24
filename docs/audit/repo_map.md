# Agent Guru - Repository Map
*Generated: 2026-04-18*

## Entry Points

| File | Purpose |
|------|---------|
| `main.py` | Primary entry point - starts full voice assistant pipeline |
| `Agent_Guru/vision/train.py` | Vision model training (ArcFace, RetinaFace) |
| `installer/verify_requirements.py` | System requirements verification |

## Core Pipeline (8 Stages)

```
Microphone → Wake Word → STT → Memory Retrieval → Reasoning/LLM
    → Policy Check → OS Action → TTS → Audit Log
```

Implemented in: `Agent_Guru/integration/orchestrator.py`

## Module Map

| Module | Purpose | Entry Point |
|--------|---------|-------------|
| `speech/` | Wake word, STT, TTS, voice biometrics | `speech/engine.py` |
| `vision/` | Face detection, recognition, emotion | `vision/engine.py` |
| `llm/` | Multi-provider LLM runtime | `llm/llm_runtime.py` |
| `reasoning/` | Intent detection, execution, knowledge | `reasoning/engine.py` |
| `platform/` | Cross-platform OS control | `platform/os_controller.py` |
| `agents/` | Multi-agent orchestration | `agents/orchestrator.py` |
| `memory/` | Knowledge graph, preferences | `memory/memory_manager.py` |
| `security/` | Biometric auth, encryption | `security/security_system.py` |
| `policy/` | Governance, permissions | `policy/engine.py` |
| `avatar/` | Personality, emotion, rendering | `avatar/avatar_system.py` |
| `integration/` | Pipeline orchestration | `integration/orchestrator.py` |
| `self_improvement/` | Continuous learning | `self_improvement/self_improvement_engine.py` |
| `goal_manager/` | Goal decomposition | `goal_manager/goal_manager.py` |
| `verifier/` | Output validation | `verifier/verifier_system.py` |
| `deployment/` | Packaging, distribution | `deployment/production.py` |
| `health/` | System health monitoring | `health/engine.py` |

## Duplicate/Redundant Modules

| Module | Status | Action |
|--------|--------|--------|
| `agent_orchestration/` | Superseded by `agents/` | Kept for backward compat |
| `emotion/` | Overlaps with `avatar/emotion/` | Separate concerns |
| `learning/` | Federated learning (distinct from `self_improvement/`) | Keep both |

## Dependency Order (initialization)

1. `security/` - auth, encryption
2. `platform/` - OS abstraction
3. `llm/` - LLM runtime
4. `speech/` - speech engine
5. `vision/` - vision engine
6. `memory/` - depends on security
7. `reasoning/` - depends on LLM, memory
8. `agents/` - depends on platform, reasoning
9. `policy/` - depends on security
10. `avatar/` - depends on speech, vision
11. `integration/` - wires all subsystems
