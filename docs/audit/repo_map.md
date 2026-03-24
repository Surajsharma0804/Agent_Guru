# Agent Guru — Repository Map
**Generated:** Audit Phase 1  
**Status:** Production-grade audit complete

## Entry Points

| File | Purpose |
|------|---------|
| `main.py` | Primary entry point — wires all subsystems via IntegrationOrchestrator |
| `Agent_Guru/core/agent_guru.py` | AgentGuru application class with VoicePipeline state machine |
| `Agent_Guru/core/voice_pipeline.py` | IDLE→LISTENING→PROCESSING→RESPONDING state machine |

## Active Pipeline (8 Stages)

```
Wake Word (WakeWordManager)
  → STT (SpeechEngine.transcribe → WhisperTranscriber)
  → Memory (MemoryManager.search)
  → Reasoning (ReasoningEngine.process)
  → LLM (LLMRuntime.complete via ProviderFailoverRouter)
  → Intent (IntentRecognizer.recognize)
  → Policy (PolicyEngine.evaluate_policy)
  → Action (OSController)
  → TTS (CoquiTTSEngine.synthesize_to_array → sounddevice)
  → AuditLog
```

## Module Map

### Core Subsystems (all active)

| Module | Path | Role |
|--------|------|------|
| Integration Orchestrator | `Agent_Guru/integration/orchestrator.py` | Wires all 8 pipeline stages |
| GPU Resource Pool | `Agent_Guru/integration/gpu_pool.py` | VRAM budget allocation |
| Speech Engine | `Agent_Guru/speech/engine.py` | Wake word + STT + TTS facade |
| Wake Word Manager | `Agent_Guru/speech/wake_word_manager.py` | Continuous detection loop |
| Wake Word Detector | `Agent_Guru/speech/audio/wake_word.py` | MFCC-based detection |
| Whisper STT | `Agent_Guru/speech/stt/whisper_stt.py` | faster-whisper transcription |
| Coqui TTS | `Agent_Guru/speech/tts/tts_engine.py` | Neural TTS synthesis |
| Vision Engine | `Agent_Guru/vision/engine.py` | Face detection + recognition |
| LLM Runtime | `Agent_Guru/llm/llm_runtime.py` | Multi-provider LLM |
| Failover Router | `Agent_Guru/llm/failover_router.py` | Ollama→OpenAI→Gemini→Anthropic |
| OS Controller | `Agent_Guru/platform/os_controller.py` | Cross-platform OS actions |
| Intent Recognizer | `Agent_Guru/platform/intent_recognizer.py` | Rule-based intent parsing |
| Memory Manager | `Agent_Guru/memory/memory_manager.py` | Conversation + semantic memory |
| Policy Engine | `Agent_Guru/policy/engine.py` | RBAC/ABAC access control |
| Security System | `Agent_Guru/security/security_system.py` | Biometric auth + crypto |
| Biometric Auth | `Agent_Guru/security/biometric_auth.py` | Face + voice authentication |
| Self-Improvement | `Agent_Guru/self_improvement/self_improvement_engine.py` | Learning engine |
| Reasoning Engine | `Agent_Guru/reasoning/engine.py` | Intent + NER + LLM reasoning |
| Avatar System | `Agent_Guru/avatar/avatar_system.py` | Emotion + lip sync |

## Dependency Graph (critical path)

```
main.py
└── IntegrationOrchestrator
    ├── GPUResourcePool (cuda/cpu detection)
    ├── SpeechEngine
    │   ├── WakeWordDetector (MFCC)
    │   ├── WhisperTranscriber (faster-whisper)
    │   ├── CoquiTTSEngine (TTS)
    │   └── VoiceFeatureExtractor (biometrics)
    ├── GuruVisionEngine
    │   ├── FaceDetector (RetinaFace/ONNX)
    │   ├── FaceRecognizer (ArcFace/ONNX)
    │   └── LivenessDetector
    ├── LLMRuntime
    │   └── ProviderFailoverRouter
    │       ├── OllamaAdapter
    │       ├── OpenAIAdapter
    │       ├── GoogleAdapter (Gemini)
    │       └── AnthropicAdapter
    ├── OSController
    │   ├── ApplicationController
    │   ├── SystemSettingsController
    │   └── IntentRecognizer
    ├── MemoryManager
    ├── ReasoningEngine
    ├── PolicyEngine
    ├── BiometricAuthenticator
    └── GuruAvatarSystem
```
