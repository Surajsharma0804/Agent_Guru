# Agent Guru - API Reference

## Core Components

### AgentGuru (`Agent_Guru.core.agent_guru`)

Main application class. Coordinates all subsystems.

```python
from Agent_Guru.core.agent_guru import AgentGuru

app = AgentGuru(personality="guru", enable_auth=True, enable_policy=True)
app.initialize()
app.run_as_background_service()  # blocks until shutdown()
```

**Methods**:
- `initialize()` - Load all subsystems
- `run_as_background_service()` - Start always-on service (blocking)
- `shutdown()` - Graceful shutdown
- `on_wake_word(personality)` - Signal wake word detected
- `on_speech_captured(transcript)` - Signal STT result
- `on_response_ready(response)` - Signal LLM response
- `on_playback_complete()` - Signal TTS finished
- `on_error(error)` - Signal error

---

### VoicePipeline (`Agent_Guru.core.voice_pipeline`)

State machine: IDLE → LISTENING → PROCESSING → RESPONDING → IDLE

```python
from Agent_Guru.core.voice_pipeline import VoicePipeline

pipeline = VoicePipeline()
pipeline.on_state_change(lambda old, new: print(f"{old} → {new}"))
pipeline.wake_word_detected()
pipeline.speech_captured("open calculator")
pipeline.response_ready("Opening calculator")
pipeline.playback_complete()
```

---

### AuthManager (`Agent_Guru.security.auth_manager`)

Multi-platform biometric authentication.

```python
from Agent_Guru.security.auth_manager import AuthManager

auth = AuthManager(face_threshold=0.75, voice_threshold=0.85)
auth.initialize()
auth.enroll("user_1", face_image=img_bytes)
result = auth.authenticate("user_1", face_image=img_bytes)
print(result.authenticated, result.confidence)
```

---

### PolicyManager (`Agent_Guru.policy.policy_manager`)

Permission checking and dangerous operation confirmation.

```python
from Agent_Guru.policy.policy_manager import PolicyManager

pm = PolicyManager()
pm.initialize()
pm.grant_permission("user_1", "files", ["read", "write"])
allowed = pm.check_permission("user_1", "files", "read")
if pm.requires_confirmation("files", "delete"):
    confirmed = pm.request_confirmation("Delete this file?")
```

---

### OnboardingWizard (`Agent_Guru.deployment.onboarding_wizard`)

Step-by-step user onboarding.

```python
from Agent_Guru.deployment.onboarding_wizard import OnboardingWizard
from Agent_Guru.deployment.onboarding import OnboardingStep

wizard = OnboardingWizard()
if wizard.needs_onboarding():
    wizard.run()
    wizard.complete_step(OnboardingStep.PROFILE, {
        "name": "Alice", "gender": "female", "age": 30,
        "date_of_birth": "1994-01-15"
    })
```

---

### PerformanceOptimizer (`Agent_Guru.core.performance_optimizer`)

Latency tracking and LLM response caching.

```python
from Agent_Guru.core.performance_optimizer import PerformanceOptimizer

opt = PerformanceOptimizer()
with opt.measure("stt"):
    transcript = stt_engine.transcribe(audio)
report = opt.get_report()
bottlenecks = opt.get_bottlenecks()
```

---

### InstallerBuilder (`Agent_Guru.deployment.installer_builder`)

Generate platform-specific installer configs.

```python
from Agent_Guru.deployment.installer_builder import InstallerBuilder, WindowsInstallerConfig
from pathlib import Path

builder = InstallerBuilder(Path("dist"))
config = WindowsInstallerConfig(app_name="AgentGuru", version="1.0.0", manufacturer="Team")
builder.generate_windows_wix(config)
```

---

## Performance Targets

| Stage | Target (p95) |
|-------|-------------|
| Wake word detection | <200ms |
| Speech-to-text | <1000ms |
| Intent recognition | <100ms |
| LLM response | <2000ms |
| Text-to-speech | <500ms |
| End-to-end | <4000ms |
