# Requirements Document

## Introduction

This specification defines the full-system audit and production-grade transformation of the Agent Guru repository. The system is a Python 3.11+ AI voice assistant with dual personalities (Guru/Maya), GPU acceleration, cross-platform support (Windows/macOS/Linux/Android/iOS), and integrations with OpenAI, Gemini, Claude, and local Ollama LLMs.

The audit covers ten phases: repository scan, architecture validation, no-duplication enforcement, control capability validation, multilingual intelligence, voice+action pipeline integrity, error/warning elimination, performance optimization, safe cleanup, and final integration verification.

## Glossary

- **System**: The Agent Guru codebase and all its modules collectively.
- **Orchestrator**: `Agent_Guru/integration/orchestrator.py` — the `IntegrationOrchestrator` class that wires all subsystems into the 8-stage voice pipeline.
- **OSController**: `Agent_Guru/platform/os_controller.py` — the unified facade for all OS-level operations.
- **SpeechEngine**: `Agent_Guru/speech/engine.py` — the facade coordinating STT, TTS, wake word, emotion, and biometric components.
- **Pipeline**: The 8-stage voice processing sequence: STT → Memory → Reasoning → LLM → Intent → Policy → Action → TTS.
- **Controller**: Any class in `Agent_Guru/platform/controllers/` responsible for a specific OS capability (desktop apps, messaging, input, media, etc.).
- **LLMRuntime**: `Agent_Guru/llm/llm_runtime.py` — the coordinator for all LLM provider calls.
- **TranslationEngine**: `Agent_Guru/translation/engine.py` — the multilingual translation and language-detection component.
- **Personality**: One of two assistant modes — Guru (professional, male voice) or Maya (warm, female voice).
- **GPU_Pool**: `Agent_Guru/integration/gpu_pool.py` — the VRAM allocation coordinator for Whisper, ONNX, and Torch subsystems.
- **Audit_Logger**: `Agent_Guru/security/audit/logger.py` — the security event recorder used by the Orchestrator.
- **Intent_Recognizer**: `Agent_Guru/platform/intent_recognizer.py` — the component that maps transcripts to structured intents.
- **Dead_File**: Any Python module with no import references anywhere in the codebase and no direct execution entry point.
- **Duplicate_Logic**: Any block of ≥10 lines that is functionally identical to another block in a different module.

---

## Requirements

### Requirement 1: Full Repository Scan and Architecture Understanding

**User Story:** As a developer, I want a complete map of all module relationships, data flows, and execution paths, so that I can understand the system before making any changes.

#### Acceptance Criteria

1. THE System SHALL produce a module dependency graph covering all packages under `Agent_Guru/` with directed edges representing import relationships.
2. THE System SHALL identify every entry point (files with `if __name__ == "__main__"` blocks or CLI scripts) and trace their call chains to subsystem boundaries.
3. THE System SHALL document the data flow for the 8-stage Pipeline, naming the exact class and method invoked at each stage.
4. WHEN a module imports another module that does not exist on disk, THE System SHALL flag that import as a broken reference.
5. THE System SHALL identify all circular import chains of depth ≥ 2.
6. THE System SHALL document which subsystems the Orchestrator wires together and confirm each wired subsystem has a reachable `initialize()` method.

---

### Requirement 2: Architecture Validation

**User Story:** As a developer, I want all module connections validated against the intended layered architecture, so that no layer violates its dependency boundaries.

#### Acceptance Criteria

1. THE System SHALL verify that Application Layer modules (`speech/`, `vision/`, `avatar/`) do not import from Infrastructure Layer modules (`platform/`, `security/`, `deployment/`) directly, except through defined coordinator interfaces.
2. THE System SHALL verify that the Orchestrator is the sole module that wires all subsystem coordinators together at startup.
3. WHEN duplicate orchestration logic is found outside `integration/orchestrator.py`, THE System SHALL flag it as an architecture violation.
4. THE System SHALL confirm that `agents/orchestrator.py` and `integration/orchestrator.py` serve distinct roles and document the boundary between them.
5. THE System SHALL verify that every Controller in `platform/controllers/` is reachable from OSController and that no Controller is instantiated outside of OSController or its tests.
6. IF a subsystem coordinator exposes a public method that duplicates a method already on OSController, THEN THE System SHALL flag it as a duplication candidate for consolidation.

---

### Requirement 3: Strict No-Duplication Enforcement

**User Story:** As a developer, I want zero duplicate files or logic in the codebase, so that every change only needs to be made in one place.

#### Acceptance Criteria

1. THE System SHALL scan all Python files and report any file whose full content is a subset of another file's content.
2. THE System SHALL detect all function or method bodies of ≥ 10 lines that are textually identical (modulo variable names) across different modules.
3. WHEN platform-detection logic (`_detect_platform()`) is found in more than one module, THE System SHALL consolidate it into `Agent_Guru/platform/platform_detector.py` and replace all 10 confirmed copies with a thin wrapper that delegates to `PlatformDetector.detect()`.
4. THE System SHALL verify that `_detect_platform()` exists in exactly one canonical location after consolidation.
5. FOR ALL pairs of files where duplication is detected, THE System SHALL produce a refactoring plan that eliminates the duplication without changing observable behavior.
6. THE System SHALL verify that the `_fuzzy_match()` helper exists in exactly one location and is imported wherever needed.

---

### Requirement 4: Control Capability Validation

**User Story:** As a user, I want the agent to open any application, perform UI actions (click, type, navigate), and execute complex multi-step commands, so that I can control my entire computer through voice.

#### Acceptance Criteria

1. WHEN the user issues a voice command to open an application by name, THE OSController SHALL launch that application within 2 seconds on Windows, macOS, and Linux.
2. WHEN the user issues a voice command to type text, THE OSController SHALL deliver the text to the active window within 500ms of the command being processed.
3. WHEN the user issues a multi-step command (e.g., "Open VS Code, create a folder named project, start coding"), THE Orchestrator SHALL decompose it into sequential sub-intents and execute each in order, confirming completion before proceeding to the next.
4. THE OSController SHALL support click, double-click, right-click, scroll, drag, and keyboard shortcut operations on all desktop platforms.
5. WHEN a requested application is not found by exact name, THE OSController SHALL attempt fuzzy matching against installed application names before returning a failure.
6. IF an application launch fails after two attempts, THEN THE OSController SHALL return a structured error with the application name, platform, and failure reason.
7. THE System SHALL verify that `DesktopApplicationController`, `MessagingController`, and all other controllers in `platform/controllers/` are correctly wired into OSController with no missing instantiation. `DesktopApplicationController` (async, `desktop_app_controller.py`) and `ApplicationController` (sync, `application_control.py`) serve complementary roles and BOTH must be wired. `SystemSettingsController` in `system_settings.py` (real hardware backend) and `SystemSettingsController` in `settings_controller.py` (async simulated facade) are NOT duplicates — `system_settings.py` is the correct wiring target for `OSController`.

---

### Requirement 5: Multilingual Intelligence

**User Story:** As a user who speaks Hindi, Bhojpuri, Kannada, Tamil, Telugu, Malayalam, Gujarati, English, French, German, or Persian, I want the agent to automatically detect my language and respond in the same language with natural tone and emotional expression, so that I can interact in my native language without configuration.

#### Acceptance Criteria

1. WHEN audio input is received, THE SpeechEngine SHALL detect the spoken language within the STT transcription step using Whisper's built-in language detection.
2. THE SpeechEngine SHALL support transcription in at minimum: English (en), Hindi (hi), Bhojpuri (bho), Kannada (kn), Tamil (ta), Telugu (te), Malayalam (ml), Gujarati (gu), French (fr), German (de), and Persian (fa).
3. WHEN a transcript is produced in a non-English language, THE LLMRuntime SHALL receive the transcript with the detected language code and generate a response in the same language.
4. THE System SHALL verify that the detected language code is passed from the STT stage through the Pipeline to the LLM stage without being dropped or overwritten.
5. WHEN the LLM response is in a non-English language, THE SpeechEngine TTS SHALL synthesize speech in that language using a voice appropriate to the Personality.
6. THE TranslationEngine SHALL be invoked as a fallback WHEN the primary LLM cannot generate a response in the detected language.
7. WHILE processing a multi-turn conversation, THE System SHALL maintain language consistency across turns unless the user explicitly switches languages.
8. THE System SHALL preserve natural tone, emotional expression, and context awareness in all supported languages — responses SHALL NOT be mechanical translations of English output.

---

### Requirement 6: Voice and Action Pipeline Integrity

**User Story:** As a developer, I want the full Voice Input → STT → LLM → Intent → Action → TTS → Response pipeline verified end-to-end, so that every stage is connected and no broken links exist.

#### Acceptance Criteria

1. THE Orchestrator SHALL execute all 8 pipeline stages in order for every `WakeWordEvent` received.
2. WHEN Stage 1 (STT) produces an empty transcript, THE Orchestrator SHALL skip Stages 2–7 and proceed directly to Stage 8 with a clarification prompt.
3. WHEN Stage 6 (Policy) denies an intent, THE Orchestrator SHALL skip Stage 7 (Action) and proceed to Stage 8 with a denial message.
4. THE System SHALL verify that the `_stt_fn` cache is populated during `startup()` and that `_stage_stt()` never calls `inspect.signature()` at pipeline invocation time.
5. THE System SHALL verify that the `_tts_fn` cache is populated during `startup()` and that `_stage_tts()` never resolves the TTS callable at pipeline invocation time.
6. WHEN `handle_concurrent_event()` is called, THE Orchestrator SHALL dispatch vision and speech pipelines as independent `asyncio` tasks and await both with `asyncio.gather()`.
7. THE System SHALL confirm that the Intent_Recognizer is initialized before the first pipeline run and that `_stage_intent()` does not silently return an empty string due to an uninitialized recognizer.
8. IF any pipeline stage raises an unhandled exception, THEN THE Orchestrator SHALL catch it, log it to the Audit_Logger, populate `PipelineResult.error`, and return the partial result rather than propagating the exception.
9. THE System SHALL verify that the `sleep()` and `wake()` methods correctly gate pipeline execution so that a sleeping Orchestrator does not process audio beyond wake-word detection.

---

### Requirement 7: Error and Warning Elimination

**User Story:** As a developer, I want zero compile errors, zero mypy type errors, and zero bandit security warnings in the codebase, so that the system is production-ready and safe.

#### Acceptance Criteria

1. THE System SHALL produce zero `mypy --strict` errors across all modules under `Agent_Guru/`.
2. THE System SHALL produce zero `ruff check` violations after applying auto-fixes.
3. THE System SHALL produce zero `bandit -r` HIGH or MEDIUM severity findings.
4. WHEN an `import` statement references a module that does not exist, THE System SHALL either create the missing module with a correct stub or remove the import.
5. THE System SHALL eliminate all uses of bare `except:` clauses and replace them with specific exception types.
6. THE System SHALL eliminate all `# type: ignore` comments that suppress real type errors rather than known third-party stub gaps.
7. WHEN a function has no return type annotation, THE System SHALL add the correct annotation.
8. THE System SHALL verify that all `Optional[X]` usages are replaced with `X | None` syntax (Python 3.10+ style) for consistency.
9. THE System SHALL eliminate all `subprocess` calls that are not guarded with `nosec` comments and a documented justification.

---

### Requirement 8: Performance Optimization

**User Story:** As a user, I want the agent to respond within 2.5 seconds end-to-end, so that interactions feel natural and faster than competing assistants.

#### Acceptance Criteria

1. THE SpeechEngine STT stage SHALL complete within 1 second at the 95th percentile when using GPU acceleration.
2. THE LLMRuntime inference stage SHALL complete within 2 seconds at the 95th percentile for responses under 200 tokens.
3. THE SpeechEngine TTS stage SHALL complete within 500ms at the 95th percentile for responses under 50 words.
4. THE Orchestrator `startup()` SHALL complete within 10 seconds by initializing all subsystems concurrently via `asyncio.gather()`.
5. THE System SHALL eliminate all blocking I/O calls (`time.sleep`, synchronous `requests`, synchronous file reads) from async pipeline stage methods.
6. THE GPU_Pool SHALL allocate device configurations to Whisper, ONNX, and Torch subsystems before `asyncio.gather()` is called in `startup()`, ensuring no subsystem initializes on CPU when a GPU is available.
7. THE System SHALL verify that the `_stt_fn` and `_tts_fn` caches eliminate repeated `getattr` and `inspect.signature()` calls during pipeline execution.
8. WHEN the audio buffer passed to STT is shorter than 1600 samples or has RMS below 0.001, THE System SHALL skip STT processing and return an empty transcript immediately.
9. THE System SHALL remove all redundant `asyncio.get_running_loop()` calls that are invoked more than once within the same coroutine.

---

### Requirement 9: Safe Cleanup of Unused Files

**User Story:** As a developer, I want all 100% unused files removed from the repository, so that the codebase is clean and navigable without dead weight.

#### Acceptance Criteria

1. THE System SHALL identify every Python file that has zero import references from any other module and is not a test file, entry point, or `__init__.py`.
2. BEFORE deleting any file, THE System SHALL verify the file has no references by searching all `.py` files for its module path.
3. THE System SHALL NOT delete any file that is referenced in `pyproject.toml`, `pytest.ini`, `requirements.txt`, or any CI/CD configuration.
4. THE System SHALL NOT delete any `__init__.py`, `conftest.py`, or file whose name matches `test_*.py` or `*_test.py`.
5. WHEN a file is confirmed unused by all checks, THE System SHALL move it to a `.archive/` directory rather than permanently deleting it, until a final review confirms deletion.
6. THE System SHALL produce a deletion manifest listing each removed file, its last-modified date, and the verification evidence that it was unused.

---

### Requirement 10: File Naming and Humanization

**User Story:** As a developer, I want all files to have meaningful, consistent names that reflect their purpose, so that navigating the codebase is intuitive.

#### Acceptance Criteria

1. THE System SHALL audit all Python filenames against the `snake_case.py` convention and flag any violations.
2. WHEN a filename does not reflect the primary class or function it contains, THE System SHALL propose a rename with a justification.
3. THE System SHALL NOT rename any file unless the rename improves clarity AND all import references can be updated atomically.
4. WHEN a file is renamed, THE System SHALL update every `import` and `from ... import` statement that references the old name across the entire codebase.
5. THE System SHALL verify that no rename introduces a naming collision with an existing module in the Python standard library or installed packages.
6. THE System SHALL NOT rename files in `.kiro/`, `.github/`, `k8s/`, `grafana/`, or any non-Python configuration directory.

---

### Requirement 11: Final End-to-End Integration Verification

**User Story:** As a developer, I want a verified end-to-end test that confirms the full pipeline works — user speaks, agent listens, understands, acts, and responds — so that I can be confident the system is production-ready.

#### Acceptance Criteria

1. THE System SHALL execute a synthetic end-to-end test where a `WakeWordEvent` with a pre-recorded audio payload is passed to `Orchestrator.run_pipeline()` and all 8 stages complete without error.
2. THE System SHALL verify that `PipelineResult.stages_completed == 8` for a valid audio input.
3. THE System SHALL verify that `PipelineResult.transcript` is a non-empty string for audio containing speech.
4. THE System SHALL verify that `PipelineResult.tts_response` is non-None after a successful pipeline run.
5. WHEN the pipeline is run with a multi-step OS command intent (e.g., open application + type text), THE System SHALL verify that `PipelineResult.action_result` is non-None and reflects the completed action.
6. THE System SHALL verify that the Audit_Logger records exactly one event per pipeline run.
7. FOR ALL supported languages listed in Requirement 5, THE System SHALL verify that a transcript in that language produces an LLM response in the same language.
8. THE System SHALL verify that the `demo_live.py` entry point loads OSController without import errors on the target platform.
9. WHEN `OSController` is initialized with `require_confirmation=False`, THE System SHALL verify that all 12 controller types are instantiated without raising exceptions on the target platform.
