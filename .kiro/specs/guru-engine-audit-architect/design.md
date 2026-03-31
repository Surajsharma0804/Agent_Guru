# Design Document: Guru Engine Audit & Architect

## Overview

This document describes the technical design for the full-system audit and production-grade transformation of the Agent Guru codebase. The work is organized into five concrete fix areas: duplication consolidation, language pipeline repair, controller wiring, error elimination, and architecture validation. Each area maps directly to confirmed findings from the codebase scan.

The design is intentionally surgical — it changes only what is broken or duplicated, preserves all existing subsystem boundaries, and adds no new abstractions beyond what is required to fix the confirmed defects.

---

## Architecture

### Layered Architecture (Preserved)

```
┌─────────────────────────────────────────────────────────────┐
│  Application Layer  (speech/, vision/, avatar/)             │
├─────────────────────────────────────────────────────────────┤
│  Intelligence Layer (llm/, memory/, reasoning/)             │
├─────────────────────────────────────────────────────────────┤
│  Orchestration Layer (agents/, policy/, integration/)       │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure Layer (platform/, security/, deployment/)   │
└─────────────────────────────────────────────────────────────┘
```

Each layer depends only on layers below it. The audit confirms this boundary is intact except for the specific wiring gaps documented below.

### Orchestrator Boundary

Two orchestrators exist and serve **distinct, non-overlapping roles**:

| Orchestrator | File | Role |
|---|---|---|
| `IntegrationOrchestrator` | `integration/orchestrator.py` | Wires all subsystems at startup; owns the 8-stage voice pipeline; the sole entry point for `WakeWordEvent` processing |
| `AgentOrchestrator` | `agents/orchestrator.py` | Multi-agent task decomposition; receives structured intents from the pipeline; coordinates sub-agents for complex multi-step commands |

`IntegrationOrchestrator` calls `AgentOrchestrator.execute(intent)` at Stage 7. `AgentOrchestrator` never calls back into `IntegrationOrchestrator`. The boundary is one-directional.

### 8-Stage Pipeline Data Flow

```
WakeWordEvent(audio, wake_word)
        │
        ▼
Stage 1: _stage_stt(audio)
        → SpeechEngine.transcribe(audio_np, 16000)
        → TranscriptionResult { text, language }
        → returns (transcript: str, language_code: str)   ← FIX
        │
        ▼
Stage 2: _stage_memory(transcript)
        → MemoryManager.retrieve(transcript)
        → memory_context: Any
        │
        ▼
Stage 3: _stage_reasoning(transcript, memory_context)
        → ReasoningEngine.analyze(transcript, memory_context)
        → reasoning_output: Any
        │
        ▼
Stage 4: _stage_llm(transcript, memory_context, reasoning_output, language_code)  ← FIX
        → LLMRuntime.complete(CompletionRequest with language hint in system prompt)
        → llm_response: str
        │
        ▼
Stage 5: _stage_intent(transcript)
        → IntentRecognizer.recognize(transcript)
        → intent: str (encoded as "type:action:param:level")
        │
        ▼
Stage 6: _stage_policy(intent)
        → PolicyEngine.evaluate(intent)
        → policy_allowed: bool
        │
        ▼
Stage 7: _stage_action(intent)  [only if policy_allowed]
        → AgentOrchestrator.execute(intent) OR OSController direct call
        → action_result: Any
        │
        ▼
Stage 8: _stage_tts(llm_response, personality)
        → SpeechEngine.synthesize_to_array(text, personality)
        → tts_response: (np.ndarray, int)
        │
        ▼
PipelineResult { stages_completed=8, transcript, detected_language, ... }
```

---

## Components and Interfaces

### Fix 1: Duplication Consolidation

#### 1a. `_detect_platform()` — 10 confirmed copies → 1 canonical

**Canonical location**: `Agent_Guru/platform/platform_detector.py` (already exists, `PlatformDetector.detect()`)

**Files to fix** (replace local `_detect_platform()` with thin wrapper that imports canonical):
- `platform/controllers/desktop_app_controller.py`
- `platform/controllers/desktop_file_controller.py`
- `platform/controllers/desktop_text_controller.py`
- `platform/controllers/mobile_app_controller.py`
- `platform/controllers/messaging_controller.py`
- `platform/controllers/settings_controller.py`
- `speech/stt_manager.py`
- `speech/tts_manager.py`
- `speech/wake_word_manager.py`
- `memory/memory_manager.py`

**Note on `platform_detector.py` itself**: The `_is_android()` helper in `platform_detector.py` uses `subprocess.run(["uname", "-o"])` without a `nosec` annotation. Add `# nosec B603 B607` with a module-level justification comment.

**Migration pattern** for each file:

```python
# BEFORE (in each file)
_PLATFORM_CACHE: Optional[str] = None

def _detect_platform() -> str:
    global _PLATFORM_CACHE
    if _PLATFORM_CACHE is not None:
        return _PLATFORM_CACHE
    system = platform.system().lower()
    # ... 15+ lines of detection logic
    _PLATFORM_CACHE = result
    return result

# AFTER (in each file)
from Agent_Guru.platform.platform_detector import PlatformDetector

def _detect_platform() -> str:
    """Thin wrapper — delegates to canonical PlatformDetector."""
    info = PlatformDetector.detect()
    return info.os_name.lower()
```

The wrapper preserves the existing call sites (`_detect_platform()`) without requiring a rename sweep. The canonical `PlatformDetector` already caches its result.

**Note on return value normalization**: `PlatformDetector.detect().os_name` returns `"Windows"`, `"macOS"`, `"Linux"`, `"Android"`, `"iOS"`. The local copies return lowercase `"windows"`, `"macos"`, `"linux"`, `"android"`, `"ios"`. The wrapper must call `.lower()` to preserve behavioral compatibility.

#### 1b. `_fuzzy_match()` — 3 copies → 1 canonical

**New canonical location**: `Agent_Guru/platform/utils.py` (create new file)

```python
# Agent_Guru/platform/utils.py

def normalize(name: str) -> str:
    """Normalize a name for fuzzy matching."""
    return name.strip().lower()


def fuzzy_match(query: str, candidate: str) -> bool:
    """Return True if query matches candidate (case-insensitive partial).

    Symmetric: fuzzy_match(a, b) == fuzzy_match(b, a) for normalized inputs.
    """
    q = normalize(query)
    c = normalize(candidate)
    return q == c or q in c or c in q
```

**Files to fix** (replace local `_fuzzy_match()` with import):
- `platform/controllers/desktop_app_controller.py`
- `platform/controllers/mobile_app_controller.py`
- `platform/controllers/messaging_controller.py`

```python
# AFTER (in each file)
from Agent_Guru.platform.utils import fuzzy_match as _fuzzy_match
```

The alias `_fuzzy_match` preserves all existing call sites.

### Fix 2: Language Pipeline

#### 2a. `PipelineResult` — add `detected_language` field

```python
# integration/orchestrator.py — PipelineResult dataclass

@dataclass
class PipelineResult:
    stages_completed: int = 0
    transcript: Optional[str] = None
    detected_language: str = ""          # NEW — ISO 639-1 code e.g. "hi", "ta", "en"
    memory_context: Optional[Any] = None
    reasoning_output: Optional[Any] = None
    llm_response: Optional[str] = None
    intent: Optional[str] = None
    policy_allowed: bool = False
    action_result: Optional[Any] = None
    tts_response: Optional[Any] = None
    personality: Personality = Personality.GURU
    error: Optional[str] = None
```

#### 2b. `_stage_stt()` — return `(transcript, language_code)`

```python
# BEFORE
async def _stage_stt(self, audio: bytes) -> str:
    ...
    return text

# AFTER
async def _stage_stt(self, audio: bytes) -> tuple[str, str]:
    """Stage 1: Speech-to-text.

    Returns:
        (transcript, language_code) where language_code is ISO 639-1
        e.g. ("नमस्ते", "hi") or ("", "") on failure/silence.
    """
    ...
    # After getting result from transcriber:
    if hasattr(result, "text") and hasattr(result, "language"):
        return (result.text or "").strip(), (result.language or "")
    text = str(result).strip() if result else ""
    return text, ""
```

#### 2c. `run_pipeline()` — store `detected_language` and thread it to LLM

```python
# Stage 1 call site in run_pipeline()
result.transcript, result.detected_language = await self._stage_stt(wake_event.audio)
result.stages_completed = 1

# Stage 4 call site
result.llm_response = await self._stage_llm(
    result.transcript,
    result.memory_context,
    result.reasoning_output,
    result.detected_language,   # NEW parameter
)
```

#### 2d. `_stage_llm()` — inject language code into system prompt

```python
async def _stage_llm(
    self,
    transcript: str,
    memory_context: Any,
    reasoning_output: Any,
    language_code: str = "",    # NEW parameter
) -> str:
    ...
    # When building the system prompt for LLMRuntime.complete():
    lang_instruction = ""
    if language_code and language_code != "en":
        lang_instruction = (
            f"\n\nIMPORTANT: The user spoke in language code '{language_code}'. "
            f"You MUST respond in the same language. Do NOT respond in English."
        )

    system_prompt = (
        "You are Agent Guru, an AI voice assistant..."
        + lang_instruction
    )
```

#### 2e. TranslationEngine fallback

When `_stage_llm()` returns a response that does not match `detected_language` (detected via `langdetect` or a simple heuristic), `run_pipeline()` invokes `TranslationEngine.translate()` as a fallback:

```python
# After Stage 4, before Stage 5:
if result.detected_language and result.detected_language != "en":
    response_lang = _detect_response_language(result.llm_response)
    if response_lang != result.detected_language:
        translation_engine = getattr(self, "_translation_engine", None)
        if translation_engine is not None:
            tr = translation_engine.translate(
                result.llm_response or "",
                target_language=result.detected_language,
            )
            result.llm_response = tr.translated_text
```

`_translation_engine` is an optional attribute set during `startup()` if a `TranslationEngine` instance is provided.

### Fix 3: Controller Wiring

#### 3a. Two-controller application architecture (confirmed)

After full scan, the platform has **two complementary application controllers** that serve different roles and must both be wired:

| Controller | Class | File | Style | Role |
|---|---|---|---|---|
| `_app_controller` | `ApplicationController` | `application_control.py` | Sync | Rich path resolution (Program Files, PATH, System32), process management, window minimize/maximize via win32, platform integration modules |
| `_desktop_app_controller` | `DesktopApplicationController` | `desktop_app_controller.py` | Async | Direct subprocess/win32, fuzzy name matching, minimize/maximize/restore/switch, mobile guard |

`OSController` currently wires `ApplicationController` but NOT `DesktopApplicationController`. Both must be wired. `open_application()` should try `_desktop_app_controller.open_app()` first (async, richer), falling back to `_app_controller.open_application()`.

#### 3b. Settings controller clarification (confirmed)

Two settings controllers exist with different roles — NOT duplicates:

| Class | File | Role |
|---|---|---|
| `SystemSettingsController` | `system_settings.py` | Real implementations: pycaw (Windows audio), WMI (brightness), amixer (Linux), osascript (macOS). Abstract backend pattern. |
| `SystemSettingsController` | `settings_controller.py` | Async facade, simulated operations, cross-platform, used by `OSController` |

`OSController` imports `SystemSettingsController` from `system_settings.py`. The async `settings_controller.py` is currently unused by `OSController`. This is acceptable — `system_settings.py` is the correct choice for real hardware control. No change needed here; document the boundary.

#### 3c. Complete controller inventory (all 13 types after fix)

| Attribute | Class | File | Status |
|---|---|---|---|
| `_file_controller` | `FileOperationsController` | `file_operations.py` | ✅ wired |
| `_app_controller` | `ApplicationController` | `application_control.py` | ✅ wired |
| `_desktop_app_controller` | `DesktopApplicationController` | `desktop_app_controller.py` | ❌ **missing — add** |
| `_text_controller` | `TextInputController` | `text_input.py` | ✅ wired |
| `_messaging_controller` | `MessagingController` | `messaging_controller.py` | ✅ wired |
| `_settings_controller` | `SystemSettingsController` | `system_settings.py` | ✅ wired |
| `_mouse_controller` | `MouseController` | `input_control.py` | ✅ wired |
| `_keyboard_controller` | `KeyboardController` | `input_control.py` | ✅ wired |
| `_window_controller` | `WindowManager` | `window_management.py` | ✅ wired |
| `_media_controller` | `MediaController` | `media_control.py` | ✅ wired |
| `_screen_controller` | `ScreenCaptureController` | `screen_capture.py` | ✅ wired |
| `_process_manager` | `ProcessManager` | `process_manager.py` | ✅ wired |
| `_hardware_monitor` | `HardwareMonitor` | `hardware/monitor.py` | ✅ wired |

#### 3d. `OSController._init_controllers()` — per-controller error isolation

The current implementation wraps ALL controller instantiation in a single `try/except ImportError`, which masks individual failures. Replace with per-controller isolation:

```python
def _init_controllers(self) -> None:
    """Initialize all specialized controllers with per-controller error isolation."""
    self._file_controller = self._safe_init(
        FileOperationsController,
        audit_log_path=self.audit_log_path,
        require_confirmation=self.require_confirmation
    )
    self._app_controller = self._safe_init(ApplicationController)
    self._desktop_app_controller = self._safe_init_desktop_app()
    self._text_controller = self._safe_init(TextInputController)
    self._messaging_controller = self._safe_init(MessagingController)
    self._settings_controller = self._safe_init(SystemSettingsController)
    self._mouse_controller = self._safe_init(MouseController)
    self._keyboard_controller = self._safe_init(KeyboardController)
    self._window_controller = self._safe_init(WindowManager)
    self._media_controller = self._safe_init(MediaController)
    self._screen_controller = self._safe_init(ScreenCaptureController)
    self._process_manager = self._safe_init(ProcessManager)
    self._hardware_monitor = self._safe_init(HardwareMonitor)
    logger.info("Controllers initialized")

def _safe_init(self, cls: type, *args: Any, **kwargs: Any) -> Any:
    try:
        return cls(*args, **kwargs)
    except Exception as exc:
        logger.warning("Controller %s failed to initialize: %s", cls.__name__, exc)
        return None

def _safe_init_desktop_app(self) -> Any:
    try:
        from Agent_Guru.platform.controllers.desktop_app_controller import DesktopApplicationController
        return DesktopApplicationController()
    except RuntimeError:
        logger.info("DesktopApplicationController not available on mobile platform")
        return None
    except Exception as exc:
        logger.warning("DesktopApplicationController failed to initialize: %s", exc)
        return None
```

### Fix 4: Error Elimination

#### 4a. Bare `except:` replacements (production code only)

| File | Location | Replacement |
|---|---|---|
| `speech/tts/tts_engine.py` | `_get_wav_duration()` — `except:` | `except Exception:` |
| `speech/mobile/ios_tts.py` | temp file cleanup | `except OSError:` |
| `speech/mobile/ios_tts.py` | synthesizer stop | `except Exception as exc:` |
| `speech/mobile/android_tts.py` | temp file cleanup | `except OSError:` |
| `speech/mobile/android_tts.py` | TTS shutdown | `except Exception as exc:` |
| `platform/controllers/settings_controller.py` | `_detect_platform()` subprocess | `except Exception:` (already present but verify) |

Test files (`test_*.py`) with bare `except:` in cleanup/teardown are acceptable and do not need to be changed — they are not production code.

#### 4b. `nosec` annotations for unguarded `subprocess` calls

`platform/platform_detector.py` `_is_android()` helper:

```python
# BEFORE
out = subprocess.run(
    ["uname", "-o"], capture_output=True, text=True, timeout=1
)

# AFTER — add nosec and module-level justification
# Security: subprocess calls in this module use only fixed, non-user-controlled
# arguments (["uname", "-o"]) for platform detection. B603/B607 suppressed.
out = subprocess.run(
    ["uname", "-o"], capture_output=True, text=True, timeout=1  # nosec B603 B607
)
```

`platform/controllers/settings_controller.py` `_detect_platform()` subprocess call also lacks `nosec`:
```python
out = subprocess.run(
    ["uname", "-o"], capture_output=True, text=True, timeout=1  # nosec B603 B607
)
```

#### 4c. Type annotation gaps

Functions confirmed missing return type annotations:

- `OSController._init_audit_log()` → `-> None`
- `OSController._init_controllers()` → `-> None`
- `OSController._log_operation()` → `-> None`
- `OSController._require_confirmation()` → `-> None`
- `OSController._safe_init()` → `-> Any`
- All `_detect_platform()` wrapper functions → `-> str`

---

## Data Models

### `PipelineResult` (updated)

```python
@dataclass
class PipelineResult:
    stages_completed: int = 0
    transcript: Optional[str] = None
    detected_language: str = ""          # ISO 639-1 code; "" if unknown
    memory_context: Optional[Any] = None
    reasoning_output: Optional[Any] = None
    llm_response: Optional[str] = None
    intent: Optional[str] = None
    policy_allowed: bool = False
    action_result: Optional[Any] = None
    tts_response: Optional[Any] = None
    personality: Personality = Personality.GURU
    error: Optional[str] = None
```

### `TranscriptionResult` (existing, unchanged)

```python
@dataclass
class TranscriptionResult:
    text: str
    language: str          # ISO 639-1 code from Whisper (e.g. "hi", "ta", "en")
    confidence: float
    segments: list[TranscriptionSegment]
    duration: float
```

The `.language` field is already populated by `WhisperTranscriber.transcribe()` via `info.language` from `faster-whisper`. The fix is purely in the pipeline — extracting and threading this value.

### `platform/utils.py` (new)

```python
def normalize(name: str) -> str: ...
def fuzzy_match(query: str, candidate: str) -> bool: ...
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Language Preservation

*For any* audio input that Whisper transcribes with a detected language code L (non-empty), `PipelineResult.detected_language` after `run_pipeline()` completes must equal L.

**Validates: Requirements 5.3, 5.4, 11.7**

### Property 2: Platform Detection Consistency

*For any* module that previously contained a local `_detect_platform()` copy, calling that module's `_detect_platform()` must return the same normalized platform string as `PlatformDetector.detect().os_name.lower()`.

**Validates: Requirements 3.3, 3.4**

### Property 3: Fuzzy Match Symmetry

*For any* two non-empty strings `a` and `b`, `fuzzy_match(normalize(a), normalize(b))` must equal `fuzzy_match(normalize(b), normalize(a))`.

**Validates: Requirements 3.6, 4.5**

### Property 4: Pipeline Stage Count

*For any* `WakeWordEvent` with audio that passes the silence guard (≥ 1600 samples, RMS ≥ 0.001), `run_pipeline()` must return a `PipelineResult` with `stages_completed == 8`.

**Validates: Requirements 6.1, 11.1, 11.2**

### Property 5: Policy Deny Skips Action

*For any* pipeline run where `_stage_policy()` returns `False`, `PipelineResult.action_result` must be `None` and `stages_completed` must still reach 8 (TTS runs with a denial message).

**Validates: Requirements 6.3**

### Property 6: Pipeline Exception Safety

*For any* exception raised inside any of the 8 pipeline stage methods, `run_pipeline()` must return a `PipelineResult` with `error` set to a non-empty string rather than propagating the exception to the caller.

**Validates: Requirements 6.8**

### Property 7: Audit Log Per Run

*For any* call to `run_pipeline()` that completes (success or failure), the `AuditLogger` must record exactly one event with the correct `actor_id="guru_pipeline"`.

**Validates: Requirements 11.6**

### Property 8: Transcript Non-Empty for Speech Audio

*For any* audio buffer containing actual speech (non-silent, ≥ 1600 samples), `PipelineResult.transcript` must be a non-empty string after `run_pipeline()` completes.

**Validates: Requirements 11.3**

### Property 9: TTS Response Non-None for Successful Run

*For any* `PipelineResult` where `stages_completed == 8` and `error is None`, `tts_response` must be non-None.

**Validates: Requirements 11.4**

---

## Error Handling

### Pipeline Error Strategy

The `IntegrationOrchestrator` uses a single top-level `try/except` in `run_pipeline()` that catches all exceptions from any stage. This is intentional — the pipeline must never propagate exceptions to callers. The partial `PipelineResult` (with `stages_completed` indicating where failure occurred) is always returned.

Stage-level errors are logged at `WARNING` level. The top-level catch logs at `ERROR` level and records to `AuditLogger`.

### Controller Initialization Errors

`OSController._init_controllers()` wraps all controller instantiation in a single `try/except ImportError`. This is too broad — it masks individual controller failures. The fix is to wrap each controller independently:

```python
def _init_controllers(self) -> None:
    self._file_controller = self._try_init(FileOperationsController, ...)
    self._app_controller = self._try_init(ApplicationController)
    self._desktop_app_controller = self._try_init_desktop_app()
    # ... etc.

def _try_init(self, cls: type, *args: Any, **kwargs: Any) -> Any:
    try:
        return cls(*args, **kwargs)
    except Exception as exc:
        logger.warning("Controller %s failed to initialize: %s", cls.__name__, exc)
        return None
```

### Bare `except:` Policy

All bare `except:` clauses must be replaced with specific types. The hierarchy to use:

- File/OS operations: `except OSError`
- Subprocess/external tool failures: `except (OSError, subprocess.SubprocessError)`
- General unexpected failures in non-critical paths: `except Exception as exc` with logging
- Never use bare `except:` — it catches `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`

---

## Testing Strategy

### Dual Testing Approach

Both unit tests and property-based tests are required. They are complementary:

- **Unit tests** verify specific examples, integration points, and error conditions
- **Property tests** verify universal correctness across randomized inputs

### Property-Based Testing

**Library**: `hypothesis` (already in the project's test dependencies, `hypothesis >= 6.92.0`)

**Configuration**: Minimum 100 examples per property test (`@settings(max_examples=100)`)

**Tag format**: Each property test must include a comment:
```python
# Feature: guru-engine-audit-architect, Property N: <property_text>
```

**Property test implementations**:

```python
# Property 1: Language Preservation
@given(language_code=st.sampled_from(["hi", "ta", "fa", "kn", "te", "ml", "gu", "fr", "de", "en"]))
@settings(max_examples=100)
async def test_language_preservation(language_code):
    # Feature: guru-engine-audit-architect, Property 1: language preservation
    mock_stt = AsyncMock(return_value=TranscriptionResult(text="hello", language=language_code, ...))
    orch = make_orchestrator(stt=mock_stt)
    result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=VALID_AUDIO))
    assert result.detected_language == language_code

# Property 2: Platform Detection Consistency
@given(st.none())  # No input needed — tests the module-level function
@settings(max_examples=100)
def test_platform_detection_consistency(_):
    # Feature: guru-engine-audit-architect, Property 2: platform detection consistency
    from Agent_Guru.platform.platform_detector import PlatformDetector
    from Agent_Guru.platform.controllers.desktop_app_controller import _detect_platform
    canonical = PlatformDetector.detect().os_name.lower()
    local = _detect_platform()
    assert local == canonical

# Property 3: Fuzzy Match Symmetry
@given(a=st.text(min_size=1), b=st.text(min_size=1))
@settings(max_examples=100)
def test_fuzzy_match_symmetry(a, b):
    # Feature: guru-engine-audit-architect, Property 3: fuzzy match symmetry
    from Agent_Guru.platform.utils import fuzzy_match, normalize
    assert fuzzy_match(normalize(a), normalize(b)) == fuzzy_match(normalize(b), normalize(a))

# Property 4: Pipeline Stage Count
@given(audio=st.binary(min_size=6400, max_size=32000))
@settings(max_examples=100)
async def test_pipeline_stage_count(audio):
    # Feature: guru-engine-audit-architect, Property 4: pipeline stage count
    orch = make_orchestrator_with_mocks()
    result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=audio))
    assert result.stages_completed == 8

# Property 5: Policy Deny Skips Action
@given(intent=st.text(min_size=1, max_size=100))
@settings(max_examples=100)
async def test_policy_deny_skips_action(intent):
    # Feature: guru-engine-audit-architect, Property 5: policy deny skips action
    orch = make_orchestrator(policy=DenyAllPolicy())
    result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=VALID_AUDIO))
    assert result.action_result is None
    assert result.stages_completed == 8

# Property 6: Pipeline Exception Safety
@given(failing_stage=st.integers(min_value=1, max_value=8))
@settings(max_examples=100)
async def test_pipeline_exception_safety(failing_stage):
    # Feature: guru-engine-audit-architect, Property 6: pipeline exception safety
    orch = make_orchestrator_with_failing_stage(failing_stage)
    result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=VALID_AUDIO))
    assert result.error is not None
    assert isinstance(result, PipelineResult)

# Property 7: Audit Log Per Run
@given(st.none())
@settings(max_examples=100)
async def test_audit_log_per_run(_):
    # Feature: guru-engine-audit-architect, Property 7: audit log per run
    audit_logger = RecordingAuditLogger()
    orch = make_orchestrator(audit_logger=audit_logger)
    await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=VALID_AUDIO))
    assert len(audit_logger.events) == 1
    assert audit_logger.events[0].actor_id == "guru_pipeline"

# Property 8: Transcript Non-Empty for Speech Audio
@given(audio=st.binary(min_size=6400, max_size=32000))
@settings(max_examples=100)
async def test_transcript_non_empty_for_speech(audio):
    # Feature: guru-engine-audit-architect, Property 8: transcript non-empty for speech audio
    orch = make_orchestrator(stt=RealSpeechSTT())
    result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=audio))
    if result.stages_completed >= 1 and result.error is None:
        assert result.transcript is not None and len(result.transcript) > 0

# Property 9: TTS Response Non-None for Successful Run
@given(st.none())
@settings(max_examples=100)
async def test_tts_response_non_none(  _):
    # Feature: guru-engine-audit-architect, Property 9: TTS response non-None for successful run
    orch = make_orchestrator_with_mocks()
    result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=VALID_AUDIO))
    if result.stages_completed == 8 and result.error is None:
        assert result.tts_response is not None
```

### Unit Tests (Examples and Edge Cases)

- **Controller wiring**: `OSController(require_confirmation=False)` instantiates all 12 controller types without raising (Requirement 11.9)
- **Cache population**: After `startup()`, `_stt_fn` and `_tts_fn` are both non-None (Requirements 6.4, 6.5)
- **Empty audio guard**: Audio with < 1600 samples returns `("", "")` from `_stage_stt()` immediately (Requirement 8.8)
- **Silent audio guard**: Audio with RMS < 0.001 returns `("", "")` from `_stage_stt()` immediately (Requirement 8.8)
- **Concurrent event dispatch**: `handle_concurrent_event()` returns a 2-tuple with both results non-None (Requirement 6.6)
- **Sleep gate**: A sleeping orchestrator returns `PipelineResult(stages_completed=0)` without processing audio (Requirement 6.9)
- **Translation fallback**: When LLM response language differs from `detected_language`, `TranslationEngine.translate()` is called (Requirement 5.6)
- **demo_live.py import**: `from Agent_Guru.platform.os_controller import OSController` succeeds without import errors (Requirement 11.8)

### Test File Location

Following the existing project convention, property-based tests go in:
```
Agent_Guru/integration/tests/test_orchestrator_properties.py
Agent_Guru/platform/tests/test_utils_properties.py
Agent_Guru/platform/tests/test_platform_detector_properties.py
```
