# Requirements Document

## Introduction

Agent Guru is a Python 3.11+ AI voice assistant competing directly against Alexa, Siri, Google Assistant, ChatGPT Desktop, Claude Desktop, Open Interpreter, and OpenVoiceOS. The system spans 30+ modules across speech, vision, LLM, reasoning, memory, security, policy, avatar, agents, platform, deployment, and integration layers.

This specification defines the requirements for a **world-class audit, optimization, integration validation, and competitive analysis** of the entire Agent Guru repository. The audit covers all 9 phases: repository intelligence scan, world-leader comparison, bug and failure detection, extreme performance optimization, architectural cleanup, integration validation, world-class code quality, deployment and production readiness, and a final master audit report.

The enforcement standard is zero-tolerance: 0 errors, 0 warnings, 0 failures, 0 unused code, 0 redundant logic, 0 broken imports, 0 race conditions, 0 memory leaks, 0 dead code, 0 placeholder implementations.

---

## Glossary

- **Audit_System**: The automated and manual audit toolchain that scans, validates, and reports on the Agent Guru codebase.
- **Voice_Pipeline**: The end-to-end processing chain: Microphone → VAD → Wake Word → STT → Intent → LLM → TTS → Speaker.
- **Integration_Orchestrator**: The `Agent_Guru/integration/orchestrator.py` component that wires all subsystems together.
- **WakeWordManager**: The `Agent_Guru/speech/wake_word_manager.py` component responsible for always-on wake word detection.
- **ReasoningEngine**: The `Agent_Guru/reasoning/engine.py` component that classifies intent and routes to actions.
- **LLMRuntime**: The `Agent_Guru/llm/llm_runtime.py` component that manages LLM provider selection and inference.
- **OSController**: The `Agent_Guru/platform/os_controller.py` component that executes OS-level actions.
- **KnowledgeGraph**: The `Agent_Guru/memory/knowledge_graph.py` component that stores and retrieves semantic memory.
- **ConversationMemory**: The `Agent_Guru/memory/conversation_memory.py` component that stores conversation turns with LRU eviction.
- **GuruVisionEngine**: The `Agent_Guru/vision/engine.py` component that performs face detection, recognition, and emotion analysis.
- **GuruAvatarSystem**: The `Agent_Guru/avatar/avatar_system.py` component that renders the animated avatar.
- **PolicyEngine**: The `Agent_Guru/policy/engine.py` component that enforces RBAC and safety rules.
- **GuruSecuritySystem**: The `Agent_Guru/security/security_system.py` component that manages cryptographic identity and biometric auth.
- **Dead_Code**: Any Python module, class, function, or import that is never referenced by any live execution path.
- **Duplicate_Implementation**: Two or more modules that implement the same logical responsibility (e.g., `llm/llm_runtime.py` vs `llm/runtime.py`).
- **Race_Condition**: A concurrency defect where the outcome depends on the non-deterministic ordering of async tasks or threads.
- **Memory_Leak**: A resource allocation that is never released, causing unbounded growth over time.
- **Competitive_Baseline**: The published latency, accuracy, and resource metrics for Alexa, Siri, Google Assistant, ChatGPT Desktop, Claude Desktop, Open Interpreter, and OpenVoiceOS.
- **EARS_Pattern**: Easy Approach to Requirements Syntax — one of six structured patterns (Ubiquitous, Event-driven, State-driven, Unwanted event, Optional feature, Complex).
- **P95_Latency**: The 95th-percentile latency measured across 1,000 representative production-condition samples.
- **GPU_Pool**: The `Agent_Guru/integration/gpu_pool.py` component that allocates VRAM across concurrent subsystems.
- **Silero_VAD**: The production-grade voice activity detection model used for end-of-speech detection in the command capture loop.
- **pvporcupine**: The Picovoice Porcupine wake word engine — purpose-built, <1 MB model, <5% CPU — the required replacement for the current Vosk-based wake word detector.

---

## Requirements

---

### Requirement 1: Complete Repository Intelligence Scan

**User Story:** As a lead engineer, I want a complete machine-readable inventory of every file, module, class, function, import, dependency, runtime flow, memory flow, IPC boundary, voice pipeline stage, AI orchestration path, threading model, and startup/shutdown lifecycle in the Agent Guru repository, so that every subsequent audit phase has a verified, accurate baseline to work from.

#### Acceptance Criteria

1. THE Audit_System SHALL produce a structured inventory listing every Python module under `Agent_Guru/` with its file path, line count, public class count, public function count, and import count.
2. WHEN Python modules exist under `Agent_Guru/`, THE Audit_System SHALL map every inter-module import dependency and produce a directed acyclic graph (DAG) of module dependencies, flagging any cycles that are actually present.
3. THE Audit_System SHALL trace the complete Voice_Pipeline data flow from `speech/audio/capture.py` through `speech/audio/wake_word.py`, `speech/stt/whisper_stt.py`, `reasoning/engine.py`, `llm/llm_runtime.py`, `speech/tts/tts_engine.py`, and back to audio playback, documenting every function call boundary and data type at each stage.
4. THE Audit_System SHALL identify every asyncio task, thread, and subprocess spawned during the startup sequence in `main.py` and document their lifecycle (creation, execution, cancellation, cleanup).
5. THE Audit_System SHALL enumerate every external service boundary (OpenAI, Anthropic, Google Gemini, Ollama, sounddevice, pywin32, pyobjc, dbus-python) with the protocol, library, and error-handling strategy at each boundary.
6. THE Audit_System SHALL identify every configuration entry point (`.env`, `pyproject.toml`, `pytest.ini`, `mypy.ini`, per-module `config.py` files) and document which subsystem consumes each configuration key.
7. WHEN the inventory scan is complete, THE Audit_System SHALL write the full inventory to `AUDIT_REPORT_MASTER.md` under a dedicated "Repository Intelligence" section.
8. THE Audit_System SHALL count and list every `__pycache__` directory and `.pyc` file present in the repository tree, confirming they are excluded from all quality checks.

---

### Requirement 2: World-Leader Competitive Analysis

**User Story:** As a product owner, I want a rigorous, metric-by-metric comparison of Agent Guru against Siri, Alexa, Google Assistant, ChatGPT Desktop, Claude Desktop, Open Interpreter, and OpenVoiceOS across latency, accuracy, resource usage, capability breadth, privacy, and offline support, so that I can identify every gap where Agent Guru falls short and every area where it leads.

#### Acceptance Criteria

1. THE Audit_System SHALL produce a competitive matrix comparing Agent Guru against each of the seven Competitive_Baseline systems across: wake word P95_Latency, STT word-error-rate, end-to-end response P95_Latency, idle CPU usage, idle RAM usage, offline capability, multi-platform support, and open API availability.
2. THE Audit_System SHALL identify every metric where Agent Guru's current implementation does not yet meet its own stated target from `quality.md` (e.g., wake word <200ms, STT <1s, end-to-end <2.5s).
3. THE Audit_System SHALL identify every capability present in at least one competitor but absent or incomplete in Agent Guru — where "incomplete" means the capability exists in code but does not meet its stated target in `quality.md` (e.g., pvporcupine wake word, streaming TTS, multi-turn interruption handling).
4. THE Audit_System SHALL identify every capability present in Agent Guru but absent in all competitors (e.g., dual personality, multi-factor biometric auth, self-improvement engine, local LLM with Ollama), documenting these as competitive advantages to preserve.
5. WHEN the competitive analysis is complete, THE Audit_System SHALL append the competitive matrix and gap analysis to `AUDIT_REPORT_MASTER.md` under a "Competitive Analysis" section; IF the report update fails, THEN THE Audit_System SHALL emit an error message stating the failure reason, exit with a non-zero status code, and write no partial content to the report.
6. THE Audit_System SHALL produce a prioritized remediation list ordered by competitive impact score (gap magnitude × number of platforms affected), where each item specifies the gap, the affected module, the required change, and the expected metric improvement expressed as an absolute delta with unit and percentile (e.g., "−80ms at P95 wake word latency").

---

### Requirement 3: Full Bug and Failure Detection

**User Story:** As a quality engineer, I want every compile error, runtime error, race condition, memory leak, deadlock, circular import, broken import, thread-safety violation, async issue, resource leak, unused code path, and security risk in the Agent Guru codebase detected and documented with file path, line number, severity, and remediation, so that the codebase reaches zero known defects.

#### Acceptance Criteria

1. THE Audit_System SHALL run `python -m py_compile` on every `.py` file under `Agent_Guru/` and report any file that fails to compile with its exact error message and line number.
2. THE Audit_System SHALL run `ruff check Agent_Guru/ --select ALL` and report every linting violation with file path, line number, rule code, and description.
3. THE Audit_System SHALL run `mypy Agent_Guru/ --strict` and report every type error with file path, line number, and error message.
4. THE Audit_System SHALL run `bandit -r Agent_Guru/ -ll` and report every HIGH and MEDIUM severity security issue with file path, line number, issue type, and CWE reference.
5. THE Audit_System SHALL detect every circular import by analysing the module dependency DAG produced in Requirement 1 and report each cycle as an ordered list of module paths.
6. THE Audit_System SHALL detect every broken import — any `import` or `from ... import` statement that references a module, class, or function that does not exist at the referenced path — and report each with file path, line number, and the missing symbol.
7. THE Audit_System SHALL detect every asyncio anti-pattern: (a) blocking I/O inside `async def` functions (e.g., `requests.get`, `time.sleep`, synchronous `open()`, `subprocess.run` without `asyncio.create_subprocess_exec`), (b) missing `await` on coroutines, and (c) `asyncio.gather` calls where `return_exceptions=False` (the default) is used and no per-task exception handler is present, causing the first exception to cancel all remaining tasks silently.
8. THE Audit_System SHALL detect every potential race condition in shared mutable state accessed from multiple asyncio tasks or threads without a synchronization primitive — where accepted primitives are `asyncio.Lock`, `asyncio.Semaphore`, `threading.Lock`, `threading.RLock`, and `threading.Semaphore` — and report each with the shared variable name, the accessing coroutines/threads, and the file paths.
9. THE Audit_System SHALL detect every resource leak: file handles, database connections, HTTP sessions, audio streams, and GPU memory allocations that are opened but not closed in all code paths (including exception paths).
10. THE Audit_System SHALL detect every unused import using `ruff --select F401` and every unused variable using `ruff --select F841`, reporting each with file path and line number.
11. IF a Duplicate_Implementation is detected — defined as two or more modules sharing at least 2 public symbols with identical names and type signatures — THEN THE Audit_System SHALL report both file paths, the overlapping public API surface, and a recommended consolidation strategy that specifies: the canonical file to retain, the file to remove, and the import path changes required for all callers.
12. THE Audit_System SHALL verify that every platform-specific import (`pywin32`, `pyobjc`, `dbus-python`) is guarded by a `sys.platform` check or a `try/except ImportError` block, and report any unguarded platform import.
13. WHEN all bug detection passes are complete, THE Audit_System SHALL append a "Bug and Failure Report" section to `AUDIT_REPORT_MASTER.md` with a severity-sorted table of all findings.

---

### Requirement 4: Extreme Performance Optimization

**User Story:** As a performance engineer, I want every hot path in the Agent Guru system — CPU, GPU, RAM, thread scheduling, I/O, IPC, audio streaming, model inference, event handling, render pipeline, memory allocation, lock contention, startup time, and shutdown time — benchmarked before and after optimization, so that Agent Guru meets or beats every performance target in `quality.md`.

#### Acceptance Criteria

1. THE Audit_System SHALL benchmark the Voice_Pipeline end-to-end P95_Latency before any optimization and record the baseline in `AUDIT_REPORT_MASTER.md`.
2. THE Audit_System SHALL replace the Vosk-based wake word detector in `speech/audio/wake_word.py` with pvporcupine, achieving wake word P95_Latency below 200ms and idle CPU usage below 10%.
3. THE Audit_System SHALL implement a lock-free ring buffer of at least 10 seconds of 16kHz float32 audio in `speech/audio/capture.py` to replace the current blocking `sd.rec()` call, enabling continuous wake word monitoring without audio gaps.
4. THE Audit_System SHALL implement lazy model loading with pre-warming for every ML model — Whisper (target: <1s STT P95), Coqui TTS (target: <500ms TTS P95), InsightFace (target: <50ms face recognition P95), ONNX models (target: <50ms emotion detection P95) — so that the first inference call after startup completes within each model's stated latency target.
5. THE Audit_System SHALL implement GPU memory pooling via `integration/gpu_pool.py` so that concurrent subsystems (STT, TTS, vision, avatar) share VRAM without reallocation, achieving GPU utilization above 80% during active processing.
6. THE Audit_System SHALL implement asyncio batching for LLM token streaming so that the first token from `llm/llm_runtime.py` reaches the TTS engine within 500ms of the LLM call being issued.
7. THE Audit_System SHALL implement response caching in `reasoning/response/response_cache.py` with an LRU policy (maximum 1,024 entries, TTL 300 seconds) so that repeated identical queries return within 1ms.
8. THE Audit_System SHALL profile startup time from `main.py` invocation to "Listening for wake words" log line on a machine with an NVIDIA GPU (CUDA 11.8+), Ollama running with `llama3.2` loaded, and reduce startup time to below 10 seconds.
9. THE Audit_System SHALL benchmark idle RAM usage and reduce it to below 500MB by deferring initialization of all non-critical subsystems — defined as vision, avatar, deployment, and self-improvement — until first use.
10. THE Audit_System SHALL benchmark and optimize the `reasoning/intent/fast_router.py` trie lookup to achieve intent classification P95_Latency below 50ms for the 200 most common commands.
11. WHEN all optimizations are applied, THE Audit_System SHALL re-benchmark every metric and append a "Before/After Performance Table" to `AUDIT_REPORT_MASTER.md` showing the improvement for each metric; all optimized metrics SHALL be at least 10% below each target defined in `quality.md` (i.e., meaningfully exceed, not merely meet, the targets).
12. THE Audit_System SHALL verify that no optimization introduces a correctness regression by running `pytest Agent_Guru/ -x --tb=short` after each optimization and confirming zero test failures.

---

### Requirement 5: Architectural Cleanup

**User Story:** As a software architect, I want every truly unused file, dead code path, redundant logic, broken experimental module, and duplicate implementation removed from the Agent Guru codebase — without removing any future-critical infrastructure — so that the codebase is lean, navigable, and free of confusion.

#### Acceptance Criteria

1. THE Audit_System SHALL identify and remove `llm/llm_runtime.py` if it is a duplicate of `llm/runtime.py`, or consolidate both into a single canonical `llm/runtime.py` that preserves all non-duplicate functionality.
2. THE Audit_System SHALL identify and consolidate `vision/engine.py` and `vision/vision_engine.py` into a single canonical `vision/engine.py`, preserving all non-duplicate public API surface.
3. THE Audit_System SHALL identify and consolidate `agents/orchestrator.py` and `agents/orchestration_system.py` into a single canonical `agents/orchestrator.py`.
4. THE Audit_System SHALL identify and consolidate `agents/decomposer.py` and `agents/task_decomposer.py` into a single canonical `agents/task_decomposer.py`.
5. THE Audit_System SHALL identify and remove Dead_Code functions and classes that have zero callers across the entire codebase, confirmed by `vulture Agent_Guru/ --min-confidence 80`; WHEN no dead code is found at 80% confidence, this requirement SHALL be considered satisfied.
6. THE Audit_System SHALL remove every unused import identified in Requirement 3 from every file.
7. THE Audit_System SHALL remove `memory/github_sync.py` and `llm/github_sync.py` if they have zero callers (confirmed by `grep -r` across `Agent_Guru/`) and zero integration test files that import them (confirmed by `grep -r` across `Agent_Guru/*/tests/`), documenting the removal rationale.
8. THE Audit_System SHALL remove every file under `speech/examples/` where the file contains no function or class that is imported by any file outside `speech/examples/` and no function or class that is called by any test file, as confirmed by static import analysis.
9. IF a module is identified as future-critical infrastructure (e.g., `reasoning/rust_ext/`, `deployment/installer_builder.py`, `self_improvement/`), THEN THE Audit_System SHALL preserve it and document in `AUDIT_REPORT_MASTER.md` the specific future capability it enables and the estimated timeline for activation.
10. WHEN all cleanup is complete, THE Audit_System SHALL run `ruff check Agent_Guru/ --select F401,F811` and confirm zero unused import or redefined symbol violations remain.
11. THE Audit_System SHALL run `pytest Agent_Guru/ -x --tb=short` after removing each individual file and SHALL NOT proceed to the next removal if any test fails, confirming no live dependency was broken.

---

### Requirement 6: Integration Validation

**User Story:** As an integration engineer, I want the complete Voice → STT → Intent → LLM → Planner → Automation → TTS → Avatar → Memory → Policy → Observability → Security pipeline validated end-to-end with automated tests, so that every stage handoff is verified to produce correct output types, correct data, and correct error handling.

#### Acceptance Criteria

1. THE Audit_System SHALL verify that `integration/orchestrator.py` correctly wires all 11 subsystems (speech, vision, llm, platform, agents, memory, reasoning, security, policy, avatar, deployment) and that `orch.startup()` completes without exception on a clean environment — defined as a process with no prior `orch.startup()` call and no subsystem state carried over from a previous run.
2. THE Audit_System SHALL verify that a wake word detection event from `WakeWordManager` correctly triggers the `_on_wake_word` callback in `main.py`, which captures audio via `_capture_command_with_vad`, and passes a `WakeWordEvent` to `Integration_Orchestrator.run_pipeline()`.
3. THE Audit_System SHALL verify that `speech/stt/whisper_stt.py` produces a `TranscriptionResult` with non-empty `text`, `language`, and `confidence` fields for any audio input with RMS above 0.005.
4. THE Audit_System SHALL verify that `reasoning/engine.py` produces an `Intent` with a non-null `type` and `confidence` above 0.5 for every `TranscriptionResult` with non-empty text.
5. THE Audit_System SHALL verify that `llm/llm_runtime.py` produces a non-empty string response for every `Intent` that routes to the LLM provider, within the P95_Latency target of 2 seconds.
6. THE Audit_System SHALL verify that `speech/tts/tts_engine.py` produces non-empty WAV bytes for every non-empty string response from the LLM, and that those bytes are played back through `sounddevice` without error.
7. THE Audit_System SHALL verify that `memory/conversation_memory.py` stores every completed conversation turn (user transcript + assistant response) and that the LRU eviction policy correctly discards the oldest turn when the 50-turn limit is reached.
8. THE Audit_System SHALL verify that a policy DENY result prevents the action from executing — observable as: the action's execution callable is not invoked and the pipeline returns a result with a DENY status — noting that actions MAY also be blocked by other mechanisms (e.g., security checks, OS permissions) beyond policy decisions alone.
9. THE Audit_System SHALL verify that `security/security_system.py` logs every action to the audit trail and that the audit trail is tamper-evident (each entry includes a cryptographic hash of the previous entry).
10. THE Audit_System SHALL verify that `avatar/avatar_system.py` updates its `current_emotion` attribute in response to both voice emotion signals from `speech/emotion/emotion_detector.py` and face emotion signals from `vision/emotion/recognizer.py`.
11. THE Audit_System SHALL verify that every Prometheus metric registered in `reasoning/config/metrics.py` is incremented at least once during a complete pipeline run, confirming observability coverage.
12. THE Audit_System SHALL verify that a simulated LLM provider failure causes the `llm/model_router/fallback_manager.py` to route to the next available provider within 500ms — observable as: no exception propagated to the pipeline caller and no error message delivered via TTS to the user.
13. WHEN all 12 integration validation checks are explicitly confirmed as passed — each check's result recorded as PASS in the validation tracking dict before this criterion is evaluated — THE Audit_System SHALL append an "Integration Validation Report" section to `AUDIT_REPORT_MASTER.md` with a pass/fail table for each check.

---

### Requirement 7: World-Class Code Quality

**User Story:** As a senior engineer, I want every module in Agent Guru to meet world-class code quality standards — correct naming, clear architecture, single module ownership, tight separation of concerns, low coupling, high cohesion, explicit interfaces, security-first design, complete type annotations, and full docstring coverage — so that any engineer can understand, extend, and maintain any module without tribal knowledge.

#### Acceptance Criteria

1. THE Audit_System SHALL run `black --check Agent_Guru/` and confirm zero formatting violations across all Python files.
2. THE Audit_System SHALL run `ruff check Agent_Guru/` with all rules enabled and confirm zero linting violations.
3. THE Audit_System SHALL run `mypy Agent_Guru/ --strict` and confirm zero type errors.
4. THE Audit_System SHALL run `bandit -r Agent_Guru/ -ll` and confirm zero HIGH or MEDIUM severity security issues.
5. THE Audit_System SHALL verify that every public function and class in every module under `Agent_Guru/` has a Google-style docstring with at minimum a one-line summary, `Args:` section (if parameters exist), and `Returns:` section (if non-None return type).
6. THE Audit_System SHALL verify that every module has a module-level docstring stating its purpose, the subsystem it belongs to, and its primary public API — where "primary public API" means all names exported via `__all__`, or all module-level names not prefixed with an underscore if `__all__` is not defined.
7. THE Audit_System SHALL verify that no module has a cyclomatic complexity above 10 for any single function, as measured by `ruff --select C901`.
8. THE Audit_System SHALL verify that no function exceeds 50 statements (excluding docstrings and blank lines), as measured by `ruff --select PLR0915` with `max-statements = 50`.
9. THE Audit_System SHALL verify that no class exceeds 300 lines of code, measured by counting non-blank, non-comment lines within the class body.
10. THE Audit_System SHALL verify that every platform-specific code path (Windows, macOS, Linux, Android, iOS) is isolated behind a platform abstraction interface — defined as an `abc.ABC` subclass or `typing.Protocol` — and that no platform-specific library (`pywin32`, `pyobjc`, `dbus-python`, `android`, `pyobjus`) is imported at module level without a `sys.platform` guard or `try/except ImportError` block.
11. THE Audit_System SHALL verify that no module in the Intelligence Layer (`llm/`, `memory/`, `reasoning/`) imports from the Infrastructure Layer (`platform/`, `deployment/`) directly, enforcing the layered architecture defined in `ARCHITECTURE.md`.
12. THE Audit_System SHALL verify that every `async def` function that performs I/O uses `await` on every I/O call and does not call any of the following blocking functions: `time.sleep`, `requests.get`, `requests.post`, `requests.put`, `requests.delete`, `urllib.request.urlopen`, synchronous `open()` outside a `run_in_executor` call, `subprocess.run`, `subprocess.call`, `subprocess.check_output`.
13. THE Audit_System SHALL verify that every secret (API key, password, private key) is loaded from environment variables or the OS keychain and that no secret value appears as a string literal in any source file.
14. WHEN every individual tool (black, ruff, mypy, bandit) passes with zero violations, THE Audit_System SHALL append a "Code Quality Report" section to `AUDIT_REPORT_MASTER.md` with the output of each tool and a summary of all violations found and fixed.

---

### Requirement 8: Deployment and Production Readiness

**User Story:** As a DevOps engineer, I want Agent Guru to be fully production-ready on Windows, macOS, and Linux — with working installers, clean startup, runtime crash recovery, structured logging, Prometheus metrics, Sentry error tracking, Ollama model loading, voice stack initialization, and automation stack initialization — so that the system can be deployed, monitored, and recovered without manual intervention.

#### Acceptance Criteria

1. THE Audit_System SHALL verify that `main.py` starts cleanly on Windows 10/11 with Python 3.11, CUDA 11.8+, and Ollama running, reaching the "Listening for wake words" state within 10 seconds.
2. THE Audit_System SHALL verify that `main.py` implements the auto-restart loop and that a simulated subsystem crash (e.g., raising an unhandled exception in a subsystem coroutine) causes the process to flush all in-flight conversation memory and security audit log entries to disk before restarting, prioritizing zero data loss over restart speed.
3. THE Audit_System SHALL verify that every log message emitted during startup and runtime uses `structlog` with JSON format, includes a `timestamp`, `level`, `module`, and `message` field, and contains no raw `print()` calls in production code paths.
4. THE Audit_System SHALL verify that the Prometheus metrics endpoint (if enabled) exposes at minimum: `guru_pipeline_latency_seconds`, `guru_wake_word_detections_total`, `guru_stt_errors_total`, `guru_llm_requests_total`, `guru_llm_latency_seconds`, and `guru_tts_latency_seconds`.
5. WHEN `SENTRY_DSN` is set in the environment and Sentry is properly initialized, THE Audit_System SHALL verify that every unhandled exception in the pipeline is captured with full stack trace and user context; WHILE `SENTRY_DSN` is not set, local exception logging SHALL be the only capture mechanism.
6. THE Audit_System SHALL verify that `deployment/installer_builder.py` produces a valid Windows MSI installer, a valid macOS DMG, and a valid Linux `.deb` package for the current version of Agent Guru.
7. THE Audit_System SHALL verify that the Ollama adapter in `llm/providers/ollama_adapter.py` correctly loads the model specified by `OLLAMA_MODEL` environment variable, falls back to `llama3.2` if the variable is unset, and retries the connection up to 3 times with exponential backoff if Ollama is not yet running.
8. THE Audit_System SHALL verify that the voice stack (microphone capture, VAD, wake word, STT, TTS) initializes without error on a machine with a standard audio device, and that a missing audio device causes a graceful degradation with a clear error log rather than a crash.
9. THE Audit_System SHALL verify that `deployment/rollback_manager.py` can roll back to the previous version within 60 seconds when invoked, and that the rollback preserves all user data in `memory/` and `security/`.
10. THE Audit_System SHALL verify that the `k8s/` Kubernetes manifests are syntactically valid YAML and that the resource requests and limits are set for every container.
11. WHEN all deployment checks pass, THE Audit_System SHALL append a "Deployment and Production Readiness Report" section to `AUDIT_REPORT_MASTER.md` with a pass/fail table for each of the 10 checks above.

---

### Requirement 9: Final Master Audit Report

**User Story:** As a project stakeholder, I want a single, comprehensive, machine-readable audit report at `/AUDIT_REPORT_MASTER.md` that consolidates all findings from all 8 audit phases, with a prioritized remediation backlog, a before/after metrics table, a competitive positioning summary, and a production readiness checklist, so that the team has a single source of truth for the state of the codebase and a clear action plan.

#### Acceptance Criteria

1. THE Audit_System SHALL create or overwrite `AUDIT_REPORT_MASTER.md` at the repository root with a structured document containing exactly 9 top-level sections: Repository Intelligence, Competitive Analysis, Bug and Failure Report, Performance Optimization, Architectural Cleanup, Integration Validation, Code Quality, Deployment Readiness, and Executive Summary.
2. THE Audit_System SHALL include in the Executive Summary: total files scanned, total bugs found, total bugs fixed, total dead code removed (line count), total performance improvements (before/after table), total test coverage percentage, and overall production readiness verdict (READY / NOT READY).
3. THE Audit_System SHALL include a prioritized remediation backlog in the Executive Summary, where each item has: ID, phase, severity (CRITICAL / HIGH / MEDIUM / LOW), affected module, description, and estimated effort (hours).
4. THE Audit_System SHALL include a "Zero Tolerance Checklist" in the Executive Summary with a checkbox for each of the following: 0 compile errors, 0 mypy errors, 0 ruff violations, 0 bandit HIGH/MEDIUM issues, 0 broken imports, 0 circular imports, 0 unused imports, 0 duplicate implementations, 0 race conditions detected, 0 resource leaks detected, 0 blocking calls in async functions, 0 hardcoded secrets.
5. THE Audit_System SHALL include a "Competitive Readiness Matrix" in the Executive Summary showing Agent Guru's current status (MET / NOT MET / EXCEEDS) for each of the 12 performance and accuracy targets in `quality.md`.
6. WHEN the report is written, THE Audit_System SHALL verify that `AUDIT_REPORT_MASTER.md` is valid Markdown (no broken links, no unclosed code blocks, no malformed tables) and that it renders correctly.
7. THE Audit_System SHALL include a "Test Coverage Summary" section showing per-module coverage percentages from `pytest --cov=Agent_Guru --cov-report=term-missing`, with modules below 80% highlighted.
8. THE Audit_System SHALL include a "Next Steps" section listing the top 10 highest-priority actions required to reach full production readiness, ordered by competitive impact.

---

### Requirement 10: Enforcement Rules (Non-Negotiable Constraints)

**User Story:** As the engineering lead, I want strict enforcement rules applied throughout the entire audit and remediation process, so that the audit produces real fixes rather than documentation of problems.

#### Acceptance Criteria

1. THE Audit_System SHALL fix every issue it detects in the original source file — it SHALL NOT create new files named `*_v2.py`, `*_optimized.py`, `*_fixed.py`, or any variant that shadows the original.
2. THE Audit_System SHALL preserve all existing functionality, integrations, and downstream dependencies when modifying any file — every change SHALL be validated by running the full test suite before and after.
3. THE Audit_System SHALL benchmark every performance-sensitive change before and after applying it, regardless of whether the change modifies the original file or any other file, and SHALL NOT apply a change that degrades any metric.
4. THE Audit_System SHALL NOT introduce any placeholder, TODO comment, mock logic, or stub implementation as a permanent fix — every fix SHALL be a complete, production-quality implementation.
5. THE Audit_System SHALL NOT remove any module that is referenced by a live test, a live import, or a live configuration entry, even if the module appears unused by static analysis alone.
6. WHEN a fix requires a breaking change to a public API, THE Audit_System SHALL update every caller of that API in the same commit, ensuring the codebase remains in a consistent, runnable state at all times.
7. THE Audit_System SHALL run `pytest Agent_Guru/ -x --tb=short` after every batch of changes and SHALL NOT proceed to the next batch if any test fails.
8. THE Audit_System SHALL run `black Agent_Guru/ && ruff check Agent_Guru/ --fix && mypy Agent_Guru/ --strict` after every batch of changes and SHALL NOT proceed if any tool reports a violation.
9. IF a required fix cannot be completed without introducing a temporary regression, THEN THE Audit_System SHALL document the regression, its scope, and the remediation plan in `AUDIT_REPORT_MASTER.md` before proceeding.
10. THE Audit_System SHALL produce a git-compatible diff summary for every file modified, showing the before and after state of each change.
