# Agent Guru — Module Dependency Graph
**Generated:** Audit Phase 1

## Circular Import Resolution

### Issue Found & Fixed
- **Chain:** `speech/engine.py` → `speech/tts/voice_cloner.py` → `security/__init__.py` → `security/biometric_auth.py` → `speech/engine.py`
- **Fix:** Converted top-level `from Agent_Guru.speech.engine import SpeechEngine` in `biometric_auth.py` to local imports inside `enroll_voice()` and `authenticate_voice()` methods.
- **Status:** ✅ RESOLVED

## Import Dependency Layers

```
Layer 0 (no internal deps):
  Agent_Guru/integration/gpu_pool.py
  Agent_Guru/policy/models.py
  Agent_Guru/speech/models.py
  Agent_Guru/llm/models.py
  Agent_Guru/security/models.py

Layer 1 (depend on Layer 0):
  Agent_Guru/policy/engine.py
  Agent_Guru/llm/providers/*.py
  Agent_Guru/speech/audio/wake_word.py
  Agent_Guru/speech/stt/whisper_stt.py
  Agent_Guru/speech/tts/tts_engine.py

Layer 2 (depend on Layer 1):
  Agent_Guru/speech/engine.py
  Agent_Guru/llm/llm_runtime.py
  Agent_Guru/platform/os_controller.py
  Agent_Guru/memory/memory_manager.py
  Agent_Guru/security/biometric_auth.py  [uses local import for SpeechEngine]

Layer 3 (depend on Layer 2):
  Agent_Guru/integration/orchestrator.py
  Agent_Guru/core/agent_guru.py

Layer 4 (top-level):
  main.py
```

## Cross-Module Interfaces

| From | To | Interface |
|------|----|-----------|
| orchestrator | speech_engine | `transcribe(audio, sr)`, `synthesize_to_array(text, personality)` |
| orchestrator | llm_runtime | `complete(CompletionRequest)` |
| orchestrator | memory | `search(query)` |
| orchestrator | policy | `evaluate_policy(principal, resource, action)` |
| orchestrator | platform | `open_application(name)`, `set_volume(n)` |
| orchestrator | reasoning | `process(RawInput)` |
| biometric_auth | speech_engine | local import — `extract_voice_features(audio)` |
| biometric_auth | vision | `extract_face_embedding(image)` |
