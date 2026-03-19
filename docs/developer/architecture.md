# Agent Guru - Architecture

## Overview

Agent Guru is a Python 3.11+ voice assistant with a layered architecture:

```
┌─────────────────────────────────────────────────────────┐
│  Application Layer  (speech, vision, avatar)            │
├─────────────────────────────────────────────────────────┤
│  Intelligence Layer (llm, memory, reasoning)            │
├─────────────────────────────────────────────────────────┤
│  Orchestration Layer (agents, policy, verifier)         │
├─────────────────────────────────────────────────────────┤
│  Infrastructure Layer (platform, security, deployment)  │
└─────────────────────────────────────────────────────────┘
```

## Voice Pipeline

The core voice pipeline is a state machine:

```
IDLE → LISTENING → PROCESSING → RESPONDING → IDLE
         ↓              ↓             ↓
       PAUSED         PAUSED        PAUSED
         ↓              ↓             ↓
       STOPPED        STOPPED       STOPPED
```

**States:**
- `IDLE` - Waiting for wake word
- `LISTENING` - Capturing speech after wake word
- `PROCESSING` - STT + intent parsing + action/LLM
- `RESPONDING` - TTS synthesis + audio playback
- `PAUSED` - User said "stop listening"
- `STOPPED` - Terminal state

**Key file:** `Agent_Guru/core/voice_pipeline.py`

## Component Flow

```
Microphone → RingBuffer → WakeWordDetector
                                ↓
                         VoicePipeline (IDLE→LISTENING)
                                ↓
                         AudioCapture → STT (Whisper)
                                ↓
                         IntentParser
                          ↙         ↘
                   OSController    LLMRuntime
                          ↘         ↙
                         TTS Synthesis
                                ↓
                         AudioPlayback
```

## Module Map

| Module | Path | Purpose |
|--------|------|---------|
| Voice Pipeline | `Agent_Guru/core/voice_pipeline.py` | State machine coordinator |
| Error Handler | `Agent_Guru/core/error_handler.py` | Centralized error handling |
| Performance | `Agent_Guru/core/performance.py` | Latency tracking |
| Wake Word | `Agent_Guru/speech/wake_word/` | Wake word detection |
| STT | `Agent_Guru/speech/stt.py` | Speech-to-text (Whisper) |
| TTS | `Agent_Guru/speech/tts/synthesis_engine.py` | Text-to-speech |
| Audio Pipeline | `Agent_Guru/speech/audio/pipeline.py` | Audio I/O |
| Intent Parser | `Agent_Guru/llm/intent_parser.py` | Intent classification |
| LLM Runtime | `Agent_Guru/llm/runtime.py` | LLM provider management |
| OS Controller | `Agent_Guru/platform/controller.py` | Cross-platform OS control |
| Memory | `Agent_Guru/memory/conversation_memory.py` | Conversation history |
| Security | `Agent_Guru/security/privacy_controls.py` | Privacy and security |
| Error Handler | `Agent_Guru/core/error_handler.py` | Error handling + retry |

## Key Design Patterns

### Coordinator Pattern
Each major module has an `engine.py` or `controller.py` that coordinates sub-components and provides a high-level API.

### Provider Pattern
LLM providers implement a common interface. The router selects the optimal provider with automatic failover:
`Ollama → OpenAI → Gemini → Claude → Rule-based fallback`

### State Machine
The `VoicePipeline` uses an explicit state machine with defined transitions. Invalid transitions are silently ignored (no crashes).

### Property-Based Testing
All correctness properties are validated with Hypothesis (100+ examples each). Properties are defined in `design.md` for each component.

## Performance Targets

| Stage | Target | Measurement |
|-------|--------|-------------|
| Wake word | <200ms | 95th percentile |
| STT | <1s | 95th percentile |
| Intent | <50ms | 95th percentile |
| LLM first token | <300ms | 95th percentile |
| TTS synthesis | <200ms | 95th percentile |
| End-to-end | <2.5s | 95th percentile |
| Startup | <5s | Cold start |
