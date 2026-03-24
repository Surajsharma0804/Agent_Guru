# Bugfix Requirements Document

## Introduction

A full system audit of the Agent Guru codebase identified 15 distinct issues spanning security vulnerabilities, resource leaks, deprecated API usage, performance anti-patterns, a missing pipeline integration, and accumulated dead code. Left unaddressed, these issues represent production blockers (exposed credentials, file descriptor leaks, Windows crashes), performance degradations (N+1 queries, per-call reflection), and an incomplete audit trail. This document captures the defective behaviors, the correct behaviors that must replace them, and the existing behaviors that must be preserved throughout remediation.

---

## Bug Analysis

### Current Behavior (Defect)

**Security**

1.1 WHEN the repository is cloned or the `.env` file is read THEN the system exposes a committed `GEMINI_API_KEY` value and `.env` is not listed in `.gitignore`, making the secret visible to anyone with repository access.

1.2 WHEN `docker-compose.yml` is read THEN the system reveals `POSTGRES_PASSWORD: dev_password` as a hardcoded plaintext string in the `postgres` service definition, making the database credential visible in version control.

**Resource Leaks**

1.3 WHEN any caller invokes `AgentStorage._get_conn()` directly (outside of a `with closing(...)` block) THEN the system returns a raw `sqlite3.Connection` that is never guaranteed to be closed, leaking a file descriptor on every call.

**Deprecated / Platform-Broken APIs**

1.4 WHEN `main.py _on_wake_word` executes on Python 3.10 or later THEN the system calls `asyncio.get_event_loop()` inside a running coroutine, which is deprecated and emits a `DeprecationWarning`; on Python 3.12+ it raises a `RuntimeError`.

1.5 WHEN `main.py run()` registers signal handlers on Windows THEN the system calls `loop.add_signal_handler()`, which raises `NotImplementedError` on Windows; the current `try/except NotImplementedError` block catches it correctly but the outer `except` is overly broad and would silently swallow unrelated errors.

**Performance Anti-Patterns**

1.6 WHEN `AgentStorage.query_agents()` or `AgentStorage.get_active_agents()` is called THEN the system issues one `SELECT` query per agent row to fetch performance records (`get_performance_records()` called inside a loop), producing an N+1 query pattern that degrades linearly with agent count.

1.7 WHEN `IntegrationOrchestrator._stage_stt()` is invoked THEN the system calls `inspect.signature(fn)` on every single STT invocation to determine which parameters the transcription function accepts, incurring reflection overhead on every pipeline run.

1.8 WHEN `IntegrationOrchestrator._stage_tts()` is invoked THEN the system resolves the correct TTS method via a chain of `getattr` calls on every invocation instead of resolving and caching the method reference once at startup.

**Private Attribute Access**

1.9 WHEN `main.py _on_wake_word` captures command audio THEN the system accesses `wake_manager._audio_capture` directly, violating encapsulation and coupling `main.py` to the internal implementation of `WakeWordManager`.

**Missing Timeout**

1.10 WHEN `LLMRuntime.complete()` calls a provider adapter that hangs (network stall, model overload) THEN the system blocks the entire async pipeline indefinitely with no timeout, preventing any further pipeline execution.

**Missing Audit Logging**

1.11 WHEN `IntegrationOrchestrator.run_pipeline()` completes all 8 stages THEN the system does not write any entry to the security audit logger (`security/audit/logger.py`), leaving every pipeline execution unrecorded in the audit trail.

**Dead Code and Artifacts**

1.12 WHEN the repository is inspected THEN the system contains the following files that serve no runtime or test purpose and add noise to the codebase: `yolov8n.pt`, `bandit_results.json`, `fix_b108_nosec.py`, `fix_tmp_paths.py`, `check_mic.py`, `pipeline_test.py`, `examples/application_control_demo.py`, `FULL_REPOSITORY_AUDIT_REPORT.txt`, `htmlcov/`, `.benchmarks/`, `.mypy_cache/`, `.ruff_cache/`, `test_logs/`.

1.13 WHEN the module structure is inspected THEN the system contains duplicate modules providing the same functionality under different names: `llm/runtime.py` duplicates `llm/llm_runtime.py`; `deployment/onboarding_wizard.py` duplicates `deployment/onboarding.py`; `platform/controllers/messaging.py` duplicates `messaging_controller.py`.

1.14 WHEN the `reasoning/` module directory is inspected THEN the system contains test artifacts (`.coverage`, `.benchmarks/`, `.hypothesis/`) co-located inside the module directory rather than at the project root or a designated test-output location.

**Broad Exception Swallowing**

1.15 WHEN any `_load_*` function in `main.py` encounters an exception loading a critical subsystem (speech engine, LLM runtime) THEN the system logs the error but returns a stub and continues, silently degrading without re-raising, making it impossible to distinguish a misconfigured environment from a healthy one at startup.

---

### Expected Behavior (Correct)

**Security**

2.1 WHEN the repository is cloned or the `.env` file is read THEN the system SHALL NOT contain any committed API key values; `.env` SHALL be listed in `.gitignore`; only `.env.example` with placeholder values SHALL be tracked in version control.

2.2 WHEN `docker-compose.yml` is read THEN the system SHALL reference the database password via an environment variable (e.g. `${POSTGRES_PASSWORD}`) with no hardcoded fallback value in the compose file; the actual secret SHALL be supplied via Docker secrets or a `.env` file excluded from version control.

**Resource Leaks**

2.3 WHEN any code path opens a SQLite connection via `AgentStorage._get_conn()` THEN the system SHALL ensure the connection is always closed by wrapping every call site in a `with closing(self._get_conn()) as conn:` block (or by making `_get_conn` itself a context manager), guaranteeing no file descriptor is leaked regardless of exceptions.

**Deprecated / Platform-Broken APIs**

2.4 WHEN `main.py _on_wake_word` needs to run a blocking call in an executor THEN the system SHALL call `asyncio.get_running_loop()` instead of `asyncio.get_event_loop()`, which is the correct API for use inside a running coroutine on Python 3.10+.

2.5 WHEN `main.py run()` registers signal handlers THEN the system SHALL attempt `loop.add_signal_handler()` and catch only `NotImplementedError` (not bare `Exception`) so that only the expected Windows incompatibility is handled silently while all other errors propagate.

**Performance Anti-Patterns**

2.6 WHEN `AgentStorage.query_agents()` or `AgentStorage.get_active_agents()` fetches multiple agents THEN the system SHALL retrieve all performance records for the full set of agent IDs in a single `WHERE agent_id IN (...)` query and map them to agents in memory, eliminating the N+1 pattern.

2.7 WHEN `IntegrationOrchestrator` is initialized THEN the system SHALL call `inspect.signature()` once per transcription function during `__init__` or `startup()` and cache the result, so that `_stage_stt()` reads from the cache on every invocation without incurring reflection overhead.

2.8 WHEN `IntegrationOrchestrator` is initialized or `startup()` completes THEN the system SHALL resolve the correct TTS method reference once and store it as an instance attribute, so that `_stage_tts()` calls the cached reference directly without repeating `getattr` chains.

**Private Attribute Access**

2.9 WHEN `main.py _on_wake_word` needs to capture command audio THEN the system SHALL call a public method `wake_manager.capture_command_audio()` exposed by `WakeWordManager`, which internally accesses `_audio_capture`, keeping the implementation detail encapsulated.

**Missing Timeout**

2.10 WHEN `LLMRuntime.complete()` calls a provider adapter THEN the system SHALL wrap the call with `asyncio.wait_for(..., timeout=30.0)` (or a configurable timeout from `RuntimeConfig`) so that a hung provider raises `asyncio.TimeoutError` after the deadline and does not block the pipeline indefinitely.

**Missing Audit Logging**

2.11 WHEN `IntegrationOrchestrator.run_pipeline()` completes stage 8 (or exits early due to an error) THEN the system SHALL call the audit logger (`security/audit/logger.py`) to record the pipeline execution, including timestamp, personality, stages completed, intent, policy decision, and any error, so that every pipeline run appears in the audit trail.

**Dead Code and Artifacts**

2.12 WHEN the repository is inspected THEN the system SHALL NOT contain the dead files and directories listed in 1.12; they SHALL be deleted and, where appropriate, their patterns SHALL be added to `.gitignore` to prevent re-accumulation.

2.13 WHEN the module structure is inspected THEN the system SHALL contain a single canonical module for each duplicated concern: `llm/llm_runtime.py` (canonical), `deployment/onboarding.py` (canonical), and `messaging_controller.py` (canonical); the duplicate files SHALL be removed and all import references SHALL be updated to point to the canonical paths.

2.14 WHEN the `reasoning/` module directory is inspected THEN the system SHALL NOT contain test artifacts; `.coverage`, `.benchmarks/`, and `.hypothesis/` SHALL reside at the project root (or be excluded via `.gitignore`) and SHALL NOT appear inside the `reasoning/` package directory.

**Broad Exception Swallowing**

2.15 WHEN a `_load_*` function in `main.py` encounters an exception loading a subsystem marked `critical=True` THEN the system SHALL re-raise the exception after logging, causing startup to fail fast with a clear error rather than silently continuing in a degraded state.

---

### Unchanged Behavior (Regression Prevention)

3.1 WHEN `AgentStorage` methods (`store_agent`, `update_agent`, `get_agent`, `store_performance_record`, `store_evolution_event`, `create_agent_atomic`) are called with valid inputs THEN the system SHALL CONTINUE TO persist and retrieve agent data correctly with the same observable semantics as before the fix.

3.2 WHEN `IntegrationOrchestrator.run_pipeline()` is called with a valid `WakeWordEvent` THEN the system SHALL CONTINUE TO execute all 8 pipeline stages in order and return a `PipelineResult` with the same fields populated as before the fix.

3.3 WHEN `LLMRuntime.complete()` is called and the provider responds within the timeout window THEN the system SHALL CONTINUE TO return a `CompletionResponse` with the same content, usage, and latency fields as before the fix.

3.4 WHEN `main.py run()` is executed on Linux or macOS THEN the system SHALL CONTINUE TO register `SIGINT` and `SIGTERM` handlers via `loop.add_signal_handler()` and shut down gracefully on those signals.

3.5 WHEN `main.py run()` is executed on Windows THEN the system SHALL CONTINUE TO fall back to `signal.signal()` for `SIGINT` and `SIGTERM` and shut down gracefully on those signals.

3.6 WHEN non-critical subsystems (`vision`, `platform`, `agents`, `memory`, `reasoning`, `security`, `policy`, `avatar`, `deployment`) fail to load THEN the system SHALL CONTINUE TO log a warning, return a stub, and start in degraded mode without raising.

3.7 WHEN `WakeWordManager.start_listening()` and `stop_listening()` are called THEN the system SHALL CONTINUE TO operate correctly regardless of whether command audio capture is accessed via the new public method or the existing internal mechanism.

3.8 WHEN `AgentStorage.get_active_agents()` is called and the cache is warm THEN the system SHALL CONTINUE TO return the cached list without hitting the database, preserving the existing O(1) cache-hit path.

3.9 WHEN the canonical LLM, deployment, and messaging modules are imported by their existing consumers THEN the system SHALL CONTINUE TO expose the same public API surface after the duplicate modules are removed and imports are updated.

3.10 WHEN `docker-compose.yml` is used in a local development environment where `POSTGRES_PASSWORD` is set in a `.env` file THEN the system SHALL CONTINUE TO start the `postgres` service and connect successfully with the same database name and user as before.
