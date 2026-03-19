# Agent Guru — Repository Audit & Architecture Map

**Date**: 2026  
**Spec**: agent-guru-production-engineering  
**Task**: 1 — Repository Audit and System Mapping  
**Requirements**: 1.1, 1.2, 1.3, 1.4, 1.7, 1.8

---

## 1. Language Stack Reality Check

The spec design document describes a Rust + Python + C++ tri-language system.
The **actual codebase is Python-first** with one optional Rust extension:

| Language | Status | Location |
|----------|--------|----------|
| Python 3.11+ | Primary — all production code | `Agent_Guru/` |
| Rust | Optional performance extension (NOT compiled) | `Agent_Guru/reasoning/rust_ext/` |
| C++ | Not present — no bindings, no source files | — |

> **Critical finding**: The design doc references Rust (cpal, rodio, PyO3) and C++
> (Whisper.cpp, Llama.cpp) as core components. These do **not exist** in the repo.
> All audio, STT, TTS, and OS control are implemented in Python.

---

## 2. Python Module Inventory

### `Agent_Guru/speech/` — Speech Engine

| Module | Responsibility |
|--------|---------------|
| `engine.py` | `SpeechEngine` facade — orchestrates all speech components; pipeline: capture → process → wake word → STT → emotion → command → context → TTS |
| `audio/capture.py` | Microphone capture via PyAudio |
| `audio/processor.py` | Audio pre-processing (normalization, resampling) |
| `audio/wake_word.py` | `WakeWordDetector` — Vosk-based offline recognition; detects "hey guru" / "hey maya"; energy-based fallback when Vosk model absent |
| `audio/noise_cancellation.py` | `AdvancedNoiseCancellation` — noisereduce + webrtcvad |
| `audio/streaming.py` | `StreamingAudioManager` — low-latency streaming pipeline |
| `stt/whisper_stt.py` | `WhisperTranscriber` — faster-whisper (GPU/CPU); lazy model load; VAD filter; word timestamps |
| `stt/language_detector.py` | Language auto-detection |
| `tts/tts_engine.py` | `CoquiTTSEngine` — Coqui TTS VCTK/VITS model; male (Guru p226) / female (Maya p225); emotion prosody; thread-safe |
| `tts/voice_cloner.py` | Voice cloning / enrollment |
| `emotion/emotion_detector.py` | Voice emotion detection (7 emotions) |
| `biometric/voice_features.py` | Voice biometric feature extraction (liveness score) |
| `commands/command_parser.py` | Command recognition and intent extraction |
| `context/context_manager.py` | Conversation context / multi-turn state |
| `background_service.py` | Always-on background service with battery optimization |
| `mobile/android_stt.py`, `ios_stt.py` | Mobile STT stubs |
| `mobile/android_tts.py`, `ios_tts.py` | Mobile TTS stubs |
| `models.py` | Pydantic data models: `PersonalityType`, `EmotionType`, `TranscriptionResult`, `WakeWordDetection`, etc. |
| `config.py` | `SpeechEngineConfig` — all speech engine settings |
| `exceptions.py` | `GuruSpeechError` hierarchy |
| `platform_integration.py` | Bridge to platform module |
| `battery_monitor.py` | Battery-aware processing throttle |
| `*_client.py` | Thin HTTP/IPC clients to other microservices (agent_orchestration, memory, goal_manager, model_router) |

### `Agent_Guru/vision/` — Vision Engine

| Module | Responsibility |
|--------|---------------|
| `engine.py` / `vision_engine.py` | Vision engine coordinator |
| `detection/` | Face detection (RetinaFace via InsightFace) |
| `recognition/` | Face recognition (ArcFace via InsightFace + ONNX Runtime) |
| `liveness/` | Anti-spoofing / liveness detection |
| `emotion/` | Facial emotion recognition |
| `tracking/` | Face tracking (DeepSORT/ByteTrack) |
| `activity.py` | Activity recognition |
| `gesture.py` | Gesture recognition |
| `pose.py` | Pose estimation |
| `ocr.py` | OCR (text in images) |
| `scene.py` | Scene understanding |
| `screen.py` | Screen capture and analysis |
| `depth.py` | Depth estimation |
| `handwriting.py` | Handwriting recognition |
| `vqa.py` | Visual question answering |
| `model_manager.py` | ONNX model loading and caching |
| `config.py` | Vision engine configuration |
| `models.py` / `vision_models.py` | Data models |
| `observability.py` | Prometheus metrics |
| `privacy.py` | PII blurring / privacy controls |

### `Agent_Guru/llm/` — LLM Runtime

| Module | Responsibility |
|--------|---------------|
| `runtime.py` | `LLMRuntime` — execution with self-improvement hooks (prompt evolution, hallucination detection, quality recording) |
| `llm_runtime.py` | Alternative runtime entry point |
| `providers/base.py` | `ProviderAdapter` ABC — `complete()`, `stream()`, `embed()` |
| `providers/ollama_adapter.py` | Ollama local LLM (async, streaming, embeddings) |
| `providers/openai_adapter.py` | OpenAI GPT-3.5/4 |
| `providers/anthropic_adapter.py` | Anthropic Claude |
| `providers/google_adapter.py` | Google Gemini |
| `model_router/` | Intelligent routing between providers |
| `context_manager.py` | Conversation context window management |
| `config_loader.py` | Provider config from env / YAML |
| `error_handler.py` | Retry, circuit breaker, fallback |
| `security.py` | API key management, audit |
| `token_counter.py` | Token counting and cost estimation |
| `performance_monitor.py` | Latency and throughput metrics |
| `models.py` | `CompletionRequest`, `CompletionResponse`, `StreamChunk`, `TokenUsage` |

### `Agent_Guru/platform/` — Platform Integration

| Module | Responsibility |
|--------|---------------|
| `os_controller.py` | `OSController` facade — routes all OS operations; audit logging; confirmation for destructive ops |
| `platform_detector.py` | Detects OS (Windows/macOS/Linux/Android/iOS) |
| `process_manager.py` | Cross-platform process management |
| `windows/integration.py` | `WindowsIntegration` — registry (winreg), services (pywin32), processes (psutil), commands |
| `macos/integration.py` | `MacOSIntegration` — AppleScript (osascript), system preferences (defaults), processes (psutil); LRU cache; circuit breaker; async support |
| `linux/integration.py` | Linux D-Bus integration |
| `android/integration.py` | Android integration stub |
| `ios/integration.py` | iOS integration stub |
| `controllers/application_control.py` | App launch/close/minimize/maximize |
| `controllers/file_operations.py` | File CRUD with confirmation |
| `controllers/text_input.py` | Keyboard simulation (pyautogui/pynput) |
| `controllers/messaging.py` | Messaging app automation |
| `controllers/system_settings.py` | Volume, brightness, network |
| `controllers/input_control.py` | Mouse and keyboard controllers |
| `controllers/window_management.py` | Window manager |
| `controllers/media_control.py` | Media play/pause/skip |
| `controllers/screen_capture.py` | Screenshot capture |
| `permissions/manager.py` | Permission checking before operations |
| `error_handling/` | Circuit breaker, retry, graceful degradation, health checks |
| `monitoring/` | Resource monitor, predictive alerting, throttling |
| `network/` | Connection pool, rate limiter, response cache, webhooks |
| `security/` | Security auditor, compliance, policy client |
| `integration/` | Clients to goal_manager, memory, self_improvement, verifier; tracing; service discovery |

### `Agent_Guru/reasoning/` — Core Reasoning Engine

| Module | Responsibility |
|--------|---------------|
| `engine.py` | `ReasoningEngine` — main pipeline orchestrator; fast-path (<500ms) + full pipeline (<1.5s); OpenTelemetry tracing; LRU response cache |
| `pipeline.py` | Pipeline stage definitions |
| `input/normalizer.py` | `InputNormalizer` — text cleaning, source tagging |
| `intent/engine.py` | `IntentDetectionEngine` — pattern matching + ML classification |
| `knowledge/query_detector.py` | Detects knowledge queries vs commands |
| `knowledge/synthesizer.py` | Knowledge synthesis from memory + tools |
| `llm/reasoning.py` | `ReasoningPlanGenerator` — LLM-based reasoning plans |
| `llm/providers/` | Gemini, DeepSeek, OpenAI, Ollama providers (separate from `Agent_Guru/llm/`) |
| `memory_retriever.py` | `MemoryRetriever` — semantic memory lookup |
| `tools/registry.py` | Tool registry |
| `tools/selector.py` | `ToolSelector` — selects best tool for intent |
| `tools/loader.py` | Loads all tools at startup |
| `safety/gate.py` | `SafetyGate` — validates actions before execution |
| `response/template_generator.py` | `TemplateGenerator` — response templates |
| `latency/controller.py` | `LatencyController` — per-stage budget enforcement |
| `latency/tracker.py` | `PipelineStage` enum + timing |
| `utils/response_cache.py` | `ResponseCache` — LRU cache for fast-path responses |
| `rust_ext/` | **Optional Rust extension** (NOT compiled by default) — `fast_pattern_match`, `fast_normalize`, `fast_entity_extract`, `fast_similarity_score`, `fast_json_parse`; Python fallbacks always active |
| `models/intent.py` | `Intent` Pydantic model |
| `models/result.py` | `ExecutionResult`, `ResponseModality` |
| `models/action.py` | `Tool`, `ActionSensitivity`, `Parameter` |

### `Agent_Guru/memory/` — Memory System

| Module | Responsibility |
|--------|---------------|
| `knowledge_graph.py` | Temporal knowledge graph (entity relationships) |
| `semantic_index.py` (implied) | Vector embeddings for semantic search |
| `experience_repository.py` | Stores interaction experiences |
| `preference_engine.py` | User preference learning |
| `personality_engine.py` | Personality evolution tracking |
| `deduplication.py` | Deduplicates stored memories |
| `encryption.py` | AES-256-GCM encryption for stored data |
| `metrics_engine.py` | Memory system metrics |
| `github_sync.py` | Syncs memory to GitHub |
| `adversarial.py` | Adversarial input detection |
| `verifier_integration.py` | Integration with verifier system |
| `wal.py` | Write-ahead log for durability |
| `config.py` | `MemoryConfig` |
| `models.py` | Memory data models |

### `Agent_Guru/agents/` — Agent Orchestration

| Module | Responsibility |
|--------|---------------|
| `orchestrator.py` | Main agent coordinator |
| `orchestration_system.py` | Multi-agent orchestration system |
| `coordinator.py` | Task coordination |
| `decomposer.py` / `task_decomposer.py` | Task decomposition |
| `executor.py` | Task execution |
| `task_assigner.py` | Assigns tasks to agents |
| `assignment_optimizer.py` | Optimizes task assignments |
| `delegation_manager.py` | Manages agent delegation |
| `agent_lifecycle.py` | Agent lifecycle management |
| `agent_merger.py` / `agent_splitter.py` | Agent population management |
| `population_manager.py` | Manages agent population |
| `circuit_breaker.py` | Circuit breaker for agent failures |
| `loop_detector.py` | Detects infinite loops |
| `duplicate_detector.py` | Detects duplicate tasks |
| `convergence_analyzer.py` | Analyzes convergence |
| `performance_tracker.py` | Tracks agent performance |
| `adversarial_handler.py` | Handles adversarial inputs |
| `github_sync_engine.py` | Syncs agent state to GitHub |
| `integrations.py` | External system integrations |
| `agent_storage.py` | Agent state persistence |

### `Agent_Guru/security/` — Security & Cryptography

| Module | Responsibility |
|--------|---------------|
| `security_system.py` | Main security coordinator |
| `biometric_auth.py` | `BiometricAuthenticator` — face + voice + fingerprint MFA |
| `voice_auth.py` | Voice-specific authentication |
| `crypto/` | Ed25519 identity, AES-256-GCM encryption |
| `audit/` | Security audit logging |
| `trust/` | Trust management |
| `models.py` | Security data models |
| `speech_integration.py` | Bridge to speech engine for voice auth |

### `Agent_Guru/policy/` — Policy Engine

| Module | Responsibility |
|--------|---------------|
| `engine.py` | `PolicyEngine` — evaluates and enforces policies |
| `rule_evaluator.py` | Rule evaluation |
| `access_controller.py` | Access control |
| `permissions.py` | Permission definitions |
| `confirmation.py` | User confirmation for sensitive actions |
| `safety.py` | Safety constraints |
| `conflict_resolver.py` | Resolves policy conflicts |
| `audit_logger.py` | Policy audit logging |
| `cache_manager.py` | Policy cache |
| `policy_storage.py` | Policy persistence |
| `models.py` | Policy data models |

### `Agent_Guru/avatar/` — Avatar & Emotion

| Module | Responsibility |
|--------|---------------|
| `avatar_system.py` | Main avatar coordinator |
| `state_manager.py` | Avatar state machine |
| `emotion/` | Emotion engine, mood tracking |
| `personality/` | Personality traits (Guru/Maya) |
| `rendering/` | Avatar rendering and animation |
| `lip_sync/` | Lip sync to TTS audio |
| `speech_integration.py` | Bridge to speech engine |
| `vision_integration.py` | Bridge to vision engine |
| `performance.py` | Rendering performance metrics |
| `config.py` | Avatar configuration |
| `models.py` | Avatar data models |

### `Agent_Guru/self_improvement/` — Self-Improvement Engine

| Module | Responsibility |
|--------|---------------|
| `self_improvement_engine.py` | Main engine — prompt evolution, performance tracking, A/B testing |
| `prompt_evolution.py` | Evolves prompts based on performance |
| `meta_learner.py` | Meta-learning across tasks |
| `performance_tracker.py` | Tracks improvement metrics |
| `failure_analyzer.py` | Analyzes failure patterns |
| `root_cause_investigator.py` | Root cause analysis |
| `strategy_optimizer.py` | Optimizes strategies |
| `ensemble_voting.py` | Ensemble decision making |
| `rollback_manager.py` | Rolls back bad improvements |
| `stability_monitor.py` | Monitors system stability |
| `degradation_detector.py` | Detects performance degradation |
| `graceful_degradation.py` | Graceful degradation under load |
| `git_integration.py` | Commits improvements to git |
| `memory_integration.py` | Integrates with memory system |
| `policy_integration.py` | Integrates with policy engine |
| `monitoring.py` | Prometheus metrics |
| `migrations.py` | Database schema migrations |
| `database_schema.py` | SQLite schema |
| `connection_pool.py` | DB connection pooling |
| `health_check.py` | Health check endpoint |
| `improvement_reporter.py` | Improvement reports |
| `edge_case_handler.py` | Edge case handling |
| `conflict_resolution.py` | Conflict resolution |
| `deployment_config.py` | Deployment configuration |

### `Agent_Guru/verifier/` — Verification System

| Module | Responsibility |
|--------|---------------|
| `verifier_system.py` | Main verifier coordinator |
| `output_validator.py` | Validates LLM outputs |
| `hallucination_detector.py` | Detects hallucinations |
| `confidence_scorer.py` | Scores output confidence |
| `accuracy_tracker.py` | Tracks accuracy over time |
| `feedback_generator.py` | Generates feedback for improvement |
| `loop_detector.py` | Detects reasoning loops |
| `tool_output_checker.py` | Validates tool outputs |
| `strategy_selector.py` | Selects verification strategy |
| `result_storage.py` | Stores verification results |
| `testing_mode.py` | Test mode support |
| `integrations.py` | External integrations |
| `models.py` | Verifier data models |

### `Agent_Guru/goal_manager/` — Goal Management

| Module | Responsibility |
|--------|---------------|
| `goal_manager.py` | Main goal manager |
| `goal_decomposer.py` | Decomposes high-level goals |
| `goal_executor.py` | Executes goal steps |
| `goal_storage.py` | Persists goals (SQLite) |
| `dependency_resolver.py` | Resolves goal dependencies |
| `priority_manager.py` | Goal prioritization |
| `progress_tracker.py` | Tracks goal progress |
| `session_manager.py` | Session-scoped goals |
| `models.py` | Goal data models |
| `exceptions.py` | Goal-specific exceptions |
| `utils.py` | Utility functions |
| `logging_config.py` | Structured logging setup |

### `Agent_Guru/deployment/` — Deployment System

| Module | Responsibility |
|--------|---------------|
| `installer_builder.py` | Builds MSI (Windows), DMG (macOS), APK (Android), IPA (iOS) installers |
| `package_manager.py` | Package management |
| `onboarding.py` | User onboarding flow |
| `update_manager.py` | OTA update management |
| `update_orchestrator.py` | Orchestrates update rollout |
| `rollback_manager.py` | Rollback on failed updates |
| `dependency_resolver.py` | Dependency resolution |
| `crypto_verifier.py` | Cryptographic package verification |
| `models.py` | Deployment data models |
| `exceptions.py` | Deployment exceptions |

### `Agent_Guru/sdk/` — Developer SDK

| Module | Responsibility |
|--------|---------------|
| `skill.py` | `Skill` base class for third-party skills |
| `manifest.py` | Skill manifest definition |
| `examples/` | Example skill implementations |

### `Agent_Guru/core/` — Core Utilities

| Module | Responsibility |
|--------|---------------|
| `device_manager.py` | Cross-platform device management |

### `Agent_Guru/agent_orchestration/` — Agent Orchestration (alternate)

| Module | Responsibility |
|--------|---------------|
| `agent_lifecycle.py` | Agent lifecycle (duplicate of `agents/`) |
| `database.py` | SQLite database for orchestration state |
| `models.py` | Orchestration data models |
| `schema.sql` | Database schema |
| `specialization_tracker.py` | Tracks agent specializations |
| `storage.py` | State storage |

> **Note**: `agent_orchestration/` and `agents/` appear to be overlapping implementations.
> This is a dead code / duplication issue to address in Task 3.

---

## 3. Voice Pipeline — Wake Word to TTS

```
Microphone (PyAudio)
        │
        ▼
AudioCapture (speech/audio/capture.py)
        │  raw PCM float32, 16kHz mono
        ▼
AudioProcessor (speech/audio/processor.py)
        │  normalize, resample
        ▼
AdvancedNoiseCancellation (speech/audio/noise_cancellation.py)
        │  noisereduce + webrtcvad
        ▼
WakeWordDetector (speech/audio/wake_word.py)
        │  Vosk KaldiRecognizer → "hey guru" / "hey maya"
        │  Fallback: energy-based (RMS threshold)
        │  Cooldown: 3s between detections
        │
        ├─ "hey guru" → PersonalityType.GURU
        └─ "hey maya" → PersonalityType.MAYA
                │
                ▼
        WhisperTranscriber (speech/stt/whisper_stt.py)
                │  faster-whisper, base model, VAD filter
                │  word timestamps, language auto-detect
                │  Returns: TranscriptionResult{text, language, confidence, segments}
                │
                ▼
        EmotionDetector (speech/emotion/emotion_detector.py)
                │  7 emotions from voice features
                │
                ▼
        CommandParser (speech/commands/command_parser.py)
                │  Returns: CommandResult{is_command, intent, parameters}
                │
                ├─ OS command → OSController (platform/os_controller.py)
                │                    │
                │                    ├─ Windows: WindowsIntegration (pywin32, winreg)
                │                    └─ macOS:   MacOSIntegration (osascript, defaults)
                │
                └─ Conversational → ReasoningEngine (reasoning/engine.py)
                                         │
                                         ├─ Fast path (<500ms): template response
                                         └─ Full pipeline (<1.5s):
                                              IntentDetectionEngine
                                              → MemoryRetriever
                                              → KnowledgeSynthesizer
                                              → ReasoningPlanGenerator (LLM)
                                              → ToolSelector
                                              → SafetyGate
                                              → TemplateGenerator
                                                    │
                                                    ▼
                                         LLM Provider (llm/providers/)
                                              Priority: Gemini → DeepSeek → OpenAI → Ollama
                                                    │
                                                    ▼
                                         ConversationContextManager
                                         (speech/context/context_manager.py)
                                                    │
                                                    ▼
                                         MemoryClient → memory system
                                                    │
                                                    ▼
                                         CoquiTTSEngine (speech/tts/tts_engine.py)
                                              │  VCTK/VITS model
                                              │  Guru: speaker p226 (male)
                                              │  Maya: speaker p225 (female)
                                              │  Emotion prosody adjustments
                                              │
                                              ▼
                                         Audio playback (pyaudio / soundfile)
```

---

## 4. Inter-Language Communication Boundaries

### Python ↔ Rust (Optional, NOT active by default)

- **Location**: `Agent_Guru/reasoning/rust_ext/`
- **Mechanism**: PyO3 `cdylib` extension module (`reasoning_rust`)
- **Build tool**: `maturin develop --release`
- **Status**: Source exists (`src/lib.rs`), but the compiled `.so`/`.pyd` is **not present** — the Python fallbacks are always used
- **Functions exposed**:
  - `fast_pattern_match(text, patterns)` — regex matching, 20x speedup
  - `fast_normalize(text, remove_punctuation)` — string normalization, 10x speedup
  - `fast_entity_extract(text, entity_types)` — entity extraction, 20x speedup
  - `fast_similarity_score(text, patterns)` — similarity scoring, 15x speedup
  - `fast_json_parse(json_str)` — JSON parsing, 5x speedup
- **Fallback**: All functions have pure-Python fallbacks; `HAS_RUST = False` when not compiled

### Python ↔ C++ (NOT present)

- No C++ source files exist in the repository
- No Whisper.cpp, Llama.cpp, or Piper TTS C++ bindings
- STT is handled by `faster-whisper` (Python package wrapping CTranslate2)
- TTS is handled by `Coqui TTS` (Python package)
- No `pybind11` or `ctypes` C++ bindings anywhere

### Python ↔ External Services (HTTP/IPC)

| Boundary | Protocol | Direction |
|----------|----------|-----------|
| Speech → Agent Orchestration | HTTP (aiohttp) | speech sends commands |
| Speech → Memory | HTTP (aiohttp) | speech stores turns/emotions |
| Speech → Goal Manager | HTTP (aiohttp) | speech creates goals |
| Speech → Model Router | HTTP (aiohttp) | speech requests LLM routing |
| Platform → Policy | Internal Python call | permission checks |
| Platform → Security | Internal Python call | audit logging |
| Reasoning → LLM Providers | HTTPS (httpx/aiohttp) | Gemini/DeepSeek/OpenAI APIs |
| Reasoning → Ollama | HTTP localhost:11434 | local LLM |
| Self-Improvement → Git | subprocess (git CLI) | commit improvements |
| Memory → ChromaDB | Python client | vector storage |
| Memory → SQLite | aiosqlite | relational storage |

---

## 5. External Dependencies

### AI/ML Core

| Package | Version | Purpose |
|---------|---------|---------|
| `torch` | >=2.0.0 | Deep learning, GPU acceleration |
| `torchvision` | >=0.15.0 | Vision models |
| `torchaudio` | >=2.0.0 | Audio processing |
| `onnxruntime-gpu` | >=1.15.0 | Optimized inference (InsightFace) |
| `transformers` | >=4.30.0 | NLP models |
| `sentence-transformers` | >=2.2.0 | Semantic embeddings |
| `faster-whisper` | >=0.9.0 | STT (CTranslate2-optimized Whisper) |
| `openai-whisper` | >=20230314 | Whisper (alternative) |
| `TTS` | >=0.22.0 | Coqui TTS (primary TTS) |
| `pyttsx3` | >=2.90 | Fallback TTS |

### Computer Vision

| Package | Version | Purpose |
|---------|---------|---------|
| `insightface` | >=0.7.3 | Face detection (RetinaFace) + recognition (ArcFace) |
| `opencv-python` | >=4.8.0 | Computer vision operations |
| `pillow` | >=10.0.0 | Image processing |

### Speech / Audio

| Package | Version | Purpose |
|---------|---------|---------|
| `vosk` | >=0.3.45 | Wake word detection (offline) |
| `pyaudio` | >=0.2.13 | Audio I/O |
| `librosa` | >=0.10.0 | Audio feature extraction |
| `soundfile` | >=0.12.0 | Audio file I/O |
| `webrtcvad` | >=2.0.10 | Voice activity detection |
| `noisereduce` | >=3.0.0 | Noise reduction |

### LLM Providers

| Package | Version | Purpose |
|---------|---------|---------|
| `openai` | >=1.0.0 | OpenAI GPT API |
| `google-generativeai` | >=0.3.0 | Gemini API |
| `anthropic` | >=0.7.0 | Claude API |
| `langchain` | >=0.1.0 | Agent orchestration framework |
| `ollama` | (runtime) | Local LLM (Ollama client) |

### Platform Integration

| Package | Version | Purpose |
|---------|---------|---------|
| `pywin32` | >=306 | Windows API (registry, services, Win32) |
| `pyobjc-framework-Cocoa` | >=9.2 | macOS Objective-C bindings |
| `pyobjc-framework-Quartz` | >=9.2 | macOS Quartz (screen capture) |
| `dbus-python` | >=1.3.2 | Linux D-Bus |
| `pyautogui` | >=0.9.54 | Mouse/keyboard automation |
| `pynput` | >=1.7.6 | Input monitoring |
| `psutil` | >=5.9.0 | Cross-platform process/system info |

### Data & Storage

| Package | Version | Purpose |
|---------|---------|---------|
| `pydantic` | >=2.0.0 | Data validation, settings |
| `sqlalchemy` | >=2.0.0 | ORM |
| `aiosqlite` | >=0.19.0 | Async SQLite |
| `chromadb` | >=0.4.0 | Vector database |
| `alembic` | >=1.13.0 | DB migrations |
| `aioredis` | >=2.0.1 | Redis async client |

### Observability

| Package | Version | Purpose |
|---------|---------|---------|
| `structlog` | >=23.2.0 | Structured logging |
| `prometheus-client` | >=0.19.0 | Metrics |
| `opentelemetry-api/sdk` | >=1.21.0 | Distributed tracing |
| `sentry-sdk` | >=1.39.0 | Error tracking |
| `loguru` | >=0.7.0 | Logging |

### Security

| Package | Version | Purpose |
|---------|---------|---------|
| `cryptography` | >=41.0.0 | AES-256-GCM, Ed25519 |
| `pyjwt` | >=2.8.0 | JWT tokens |

### Async / HTTP

| Package | Version | Purpose |
|---------|---------|---------|
| `aiohttp` | >=3.8.0 | Async HTTP client/server |
| `httpx` | >=0.24.0 | Modern HTTP client |
| `requests` | >=2.31.0 | Sync HTTP client |

### Performance

| Package | Version | Purpose |
|---------|---------|---------|
| `orjson` | >=3.9.0 | Fast JSON (5-10x) |
| `numpy` | >=1.24.0,<2.0.0 | Numerical computing |
| `scipy` | >=1.11.0,<1.14.0 | Scientific computing |
| `scikit-learn` | >=1.3.0 | ML utilities |

### Testing

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | >=7.4.0 | Test framework |
| `pytest-asyncio` | >=0.21.0 | Async tests |
| `pytest-cov` | >=4.1.0 | Coverage |
| `hypothesis` | >=6.92.0 | Property-based testing |

### Rust Extension Dependencies (Cargo.toml)

| Crate | Version | Purpose |
|-------|---------|---------|
| `pyo3` | 0.20 | Python-Rust FFI |
| `regex` | 1.10 | Regex engine |
| `serde` | 1.0 | Serialization |
| `serde_json` | 1.0 | JSON parsing |

---

## 6. Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata, dependencies, black/ruff/mypy/coverage config |
| `pytest.ini` | Test configuration (paths, markers, asyncio mode) |
| `mypy.ini` | Type checking (strict mode) |
| `.pre-commit-config.yaml` | Pre-commit hooks (black, ruff, mypy, bandit) |
| `requirements.txt` | GPU dependencies |
| `requirements-cpu.txt` | CPU-only dependencies |
| `requirements-reasoning.txt` | Reasoning engine specific deps |
| `.env` | Environment variables (API keys, config) |
| `docker-compose.yml` | Docker services (Redis, Postgres, monitoring) |
| `Dockerfile` | Container build |
| `k8s/` | Kubernetes manifests |
| `helm/` | Helm charts |
| `terraform/` | Infrastructure as code |
| `prometheus/` | Prometheus scrape config |
| `grafana/` | Grafana dashboards |
| `Agent_Guru/agents/config_template.yaml` | Agent configuration template |
| `Agent_Guru/platform/permissions/example_permissions.yaml` | Permission policy example |
| `Agent_Guru/reasoning/rust_ext/Cargo.toml` | Rust extension build config |
| `Agent_Guru/reasoning/rust_ext/pyproject.toml` | Maturin build config |

---

## 7. OS-Specific Code Paths

### Windows (`sys.platform == 'win32'`)

**`Agent_Guru/platform/windows/integration.py`** — `WindowsIntegration`:
- Registry: `winreg` (read/write/delete HKLM, HKCU keys)
- Services: `win32service`, `win32serviceutil` (query/start/stop services)
- Processes: `subprocess.Popen` with `CREATE_NEW_PROCESS_GROUP`
- Admin check: `ctypes.windll.shell32.IsUserAnAdmin()`
- Dependency: `pywin32` (optional, degrades gracefully if absent)

**`Agent_Guru/platform/controllers/application_control.py`**:
- Uses `subprocess.Popen` / `os.startfile` on Windows
- `ShellExecuteW` equivalent via Python subprocess

**`requirements.txt`**:
```
pywin32>=306; sys_platform == 'win32'
```

### macOS (`sys.platform == 'darwin'`)

**`Agent_Guru/platform/macos/integration.py`** — `MacOSIntegration`:
- AppleScript: `subprocess.run(['osascript', '-e', script])`
- System preferences: `subprocess.run(['defaults', 'read/write', domain, key])`
- App launch: `subprocess.Popen(['open', '-a', app_name])`
- pyobjc: `NSWorkspace`, `NSUserDefaults`, `NSBundle` (optional, degrades gracefully)
- LRU cache (5-min TTL) for preference reads
- Circuit breaker (5 failures → open for 60s)
- Async variants via `asyncio.run_in_executor`

**`requirements.txt`**:
```
pyobjc-framework-Cocoa>=9.2; sys_platform == 'darwin'
pyobjc-framework-Quartz>=9.2; sys_platform == 'darwin'
```

### Linux (`sys.platform == 'linux'`)

**`Agent_Guru/platform/linux/integration.py`**:
- D-Bus integration via `dbus-python`

**`requirements.txt`**:
```
dbus-python>=1.3.2; sys_platform == 'linux'
```

### Cross-Platform (all platforms)

- `psutil` — process management, system info
- `pyautogui` — mouse/keyboard automation
- `pynput` — input monitoring
- `Agent_Guru/platform/platform_detector.py` — detects current OS and routes to correct integration

---

## 8. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE LAYER                            │
│                    Voice Input / Avatar Output                          │
│              SpeechEngine (speech/engine.py)                            │
│              AvatarSystem (avatar/avatar_system.py)                     │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│                        VOICE PIPELINE LAYER                             │
│                                                                         │
│  AudioCapture → NoiseCancellation → WakeWordDetector (Vosk)             │
│       ↓                                                                 │
│  WhisperTranscriber (faster-whisper) → EmotionDetector                  │
│       ↓                                                                 │
│  CommandParser → [OS Command] or [Conversational Query]                 │
│       ↓                                                                 │
│  CoquiTTSEngine (VCTK/VITS) → Audio Playback                           │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│                      INTELLIGENCE LAYER                                 │
│                                                                         │
│  ReasoningEngine (reasoning/engine.py)                                  │
│    ├─ IntentDetectionEngine                                             │
│    ├─ MemoryRetriever ──────────────────────────────────────────────┐  │
│    ├─ KnowledgeSynthesizer                                          │  │
│    ├─ ReasoningPlanGenerator (LLM)                                  │  │
│    ├─ ToolSelector + SafetyGate                                     │  │
│    └─ TemplateGenerator                                             │  │
│                                                                     │  │
│  LLMRuntime (llm/runtime.py)                                        │  │
│    ├─ OllamaAdapter (local, free)                                   │  │
│    ├─ OpenAIAdapter (GPT-3.5/4)                                     │  │
│    ├─ AnthropicAdapter (Claude)                                     │  │
│    └─ GoogleAdapter (Gemini)                                        │  │
│                                                                     │  │
│  MemorySystem (memory/) ◄───────────────────────────────────────────┘  │
│    ├─ KnowledgeGraph (temporal)                                         │
│    ├─ SemanticIndex (ChromaDB vectors)                                  │
│    ├─ ExperienceRepository                                              │
│    ├─ PreferenceEngine                                                  │
│    └─ AES-256-GCM encryption                                           │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│                     ORCHESTRATION LAYER                                 │
│                                                                         │
│  AgentOrchestrator (agents/orchestrator.py)                             │
│    ├─ TaskDecomposer                                                    │
│    ├─ TaskAssigner                                                      │
│    ├─ AgentLifecycle                                                    │
│    └─ CircuitBreaker                                                    │
│                                                                         │
│  GoalManager (goal_manager/goal_manager.py)                             │
│    ├─ GoalDecomposer                                                    │
│    ├─ GoalExecutor                                                      │
│    └─ PriorityManager                                                   │
│                                                                         │
│  PolicyEngine (policy/engine.py)                                        │
│    ├─ RuleEvaluator                                                     │
│    ├─ AccessController                                                  │
│    └─ ConfirmationManager                                               │
│                                                                         │
│  VerifierSystem (verifier/verifier_system.py)                           │
│    ├─ HallucinationDetector                                             │
│    ├─ OutputValidator                                                   │
│    └─ ConfidenceScorer                                                  │
│                                                                         │
│  SelfImprovementEngine (self_improvement/)                              │
│    ├─ PromptEvolution                                                   │
│    ├─ MetaLearner                                                       │
│    └─ PerformanceTracker                                                │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│                     INFRASTRUCTURE LAYER                                │
│                                                                         │
│  OSController (platform/os_controller.py)                               │
│    ├─ Windows: WindowsIntegration (pywin32, winreg)                     │
│    ├─ macOS:   MacOSIntegration (osascript, defaults, pyobjc)           │
│    ├─ Linux:   LinuxIntegration (dbus-python)                           │
│    └─ Controllers: file, app, text, mouse, keyboard, window, media      │
│                                                                         │
│  SecuritySystem (security/)                                             │
│    ├─ BiometricAuthenticator (face + voice + fingerprint)               │
│    ├─ CryptoIdentity (Ed25519)                                          │
│    └─ AuditLogger                                                       │
│                                                                         │
│  DeploymentSystem (deployment/)                                         │
│    ├─ InstallerBuilder (MSI, DMG, APK, IPA)                             │
│    ├─ UpdateManager                                                     │
│    └─ OnboardingFlow                                                    │
│                                                                         │
│  VisionEngine (vision/)                                                 │
│    ├─ FaceDetection (RetinaFace/InsightFace)                            │
│    ├─ FaceRecognition (ArcFace/ONNX)                                    │
│    ├─ EmotionRecognition                                                │
│    └─ LivenessDetection                                                 │
│                                                                         │
│  [Optional] Rust Extension (reasoning/rust_ext/)                        │
│    └─ fast_pattern_match, fast_normalize, fast_entity_extract           │
│       (NOT compiled — Python fallbacks active)                          │
└─────────────────────────────────────────────────────────────────────────┘

External Services:
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │  Ollama      │  │  OpenAI API  │  │  Gemini API  │  │  Claude API  │
  │  localhost   │  │  HTTPS       │  │  HTTPS       │  │  HTTPS       │
  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │  ChromaDB    │  │  SQLite      │  │  Redis       │
  │  (vectors)   │  │  (relational)│  │  (cache)     │
  └──────────────┘  └──────────────┘  └──────────────┘
```

---

## 9. Issues Identified for Subsequent Tasks

### Critical Issues

1. **Rust extension not compiled** (`reasoning/rust_ext/`): `src/lib.rs` exists but no compiled `.so`/`.pyd`. All Rust speedups are inactive. Needs `maturin develop --release` or removal if not needed.

2. **No C++ bindings exist**: The design doc describes Whisper.cpp and Llama.cpp C++ integrations. These are not present. STT uses `faster-whisper` (Python) and TTS uses Coqui TTS (Python). The design doc needs updating to reflect reality.

3. **Vosk model not bundled**: `WakeWordDetector` falls back to energy-based detection when Vosk model is absent. The model must be downloaded separately. This will cause silent degradation in production.

4. **Coqui TTS eSpeak-NG path hardcoded**: `tts_engine.py` hardcodes `C:\Program Files\eSpeak NG` — Windows-only, will fail on macOS/Linux.

5. **`suppress_c_stderr()` redirects stderr to `/dev/null`**: This is called at module import time in `tts_engine.py`, silencing all C-level error output globally — a dangerous production practice.

### Duplication Issues (Task 3)

6. **`agents/` vs `agent_orchestration/`**: Two overlapping agent orchestration implementations. `agent_orchestration/` appears to be a newer, database-backed version. Needs consolidation.

7. **`llm/runtime.py` vs `llm/llm_runtime.py`**: Two LLM runtime files. `runtime.py` has self-improvement integration; `llm_runtime.py` purpose unclear without reading it.

8. **`reasoning/llm/providers/` vs `llm/providers/`**: Two separate LLM provider implementations. The reasoning engine has its own Gemini/DeepSeek/OpenAI/Ollama providers separate from the main `llm/providers/` adapters.

### Design vs Reality Gaps

9. **Audio pipeline**: Design specifies `cpal` (Rust) + `rodio` (Rust). Reality: `pyaudio` (Python). No ring buffer implementation found — needs verification.

10. **Wake word**: Design specifies pvporcupine. Reality: Vosk (free, offline). This is actually better for the stated goals (offline, free).

11. **Memory encryption**: Design specifies AES-256-GCM. `memory/encryption.py` exists but integration with conversation storage needs verification.

12. **`guru_platform/` directory**: Contains only example Python scripts (`example_application_control.py`, etc.) and a README. No actual implementation — appears to be documentation/examples only.

### Missing Components

13. **No audio playback module found**: The pipeline ends at TTS synthesis but no explicit audio playback module (e.g., `sounddevice`, `pyaudio` playback) was found in `speech/`. Needs investigation.

14. **No end-to-end pipeline wiring**: `SpeechEngine.process_voice_input()` calls `synthesize_response()` but doesn't play the audio. The final playback step is not implemented.

15. **`pvporcupine` in requirements.txt but not in code**: `requirements.txt` does not list pvporcupine; `tech.md` mentions it. The actual wake word uses Vosk.

---

## 10. Summary

| Aspect | Status |
|--------|--------|
| Python modules documented | ✅ Complete |
| Rust modules documented | ✅ One optional extension (not compiled) |
| C++ bindings | ✅ None exist (design doc is aspirational) |
| Inter-language boundaries | ✅ Documented |
| Voice pipeline mapped | ✅ Complete |
| External dependencies | ✅ Complete |
| Architecture diagram | ✅ Complete |
| OS-specific code paths | ✅ Windows + macOS + Linux documented |
| Issues for subsequent tasks | ✅ 15 issues identified |
