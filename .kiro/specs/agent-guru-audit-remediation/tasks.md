# Implementation Plan

- [x] 1. Write bug condition exploration tests (BEFORE implementing any fix)
  - **Property 1: Bug Condition** - Multi-Defect Exploration Suite
  - **CRITICAL**: These tests MUST FAIL on unfixed code — failure confirms each bug exists
  - **DO NOT attempt to fix the code when tests fail**
  - **GOAL**: Surface counterexamples that demonstrate each bug exists before touching production code
  - **Scoped PBT Approach**: Scope each property to the concrete failing case(s) for reproducibility
  - Create `tests/test_audit_remediation_exploration.py`
  - **1a — Connection Leak (Bug 1.3)**:
    - Call `AgentStorage._get_conn()` 1000 times without `closing()` wrapper
    - Assert SQLite reports open file descriptors — demonstrates the leak
    - Run on UNFIXED code — **EXPECTED OUTCOME**: Test FAILS (proves leak exists)
  - **1b — N+1 Query (Bug 1.6)**:
    - Mock DB cursor; call `query_agents()` with 10 agents
    - Assert `cursor.execute` is called 11 times (1 agent query + 10 per-record queries)
    - Run on UNFIXED code — **EXPECTED OUTCOME**: Test FAILS (proves N+1 exists)
  - **1c — STT Signature Per-Call (Bug 1.7)**:
    - Mock `inspect.signature`; call `_stage_stt()` 5 times
    - Assert `inspect.signature` was called exactly 5 times
    - Run on UNFIXED code — **EXPECTED OUTCOME**: Test FAILS (proves per-call reflection)
  - **1d — LLM Hang (Bug 1.10)**:
    - Mock `adapter.complete` to sleep indefinitely (`asyncio.sleep(9999)`)
    - Call `LLMRuntime.complete()` with a 2-second wall-clock limit
    - Assert it never returns within 2 seconds
    - Run on UNFIXED code — **EXPECTED OUTCOME**: Test FAILS (proves indefinite hang)
  - **1e — Missing Audit Log (Bug 1.11)**:
    - Patch `AuditLogger.log_event`; call `run_pipeline()` with a valid `WakeWordEvent`
    - Assert `log_event` was never called
    - Run on UNFIXED code — **EXPECTED OUTCOME**: Test FAILS (proves audit gap)
  - **1f — Silent Critical Degradation (Bug 1.15)**:
    - Patch `SpeechEngine.__init__` to raise `RuntimeError`
    - Call `_load_speech()` and assert it returns a stub without raising
    - Run on UNFIXED code — **EXPECTED OUTCOME**: Test FAILS (proves silent swallow)
  - Document all counterexamples found to understand root causes
  - Mark task complete when all exploration tests are written, run, and failures documented
  - _Requirements: 1.3, 1.6, 1.7, 1.10, 1.11, 1.15_

- [x] 2. Write preservation property tests (BEFORE implementing any fix)
  - **Property 2: Preservation** - Unchanged Behavior Baseline
  - **IMPORTANT**: Follow observation-first methodology — run UNFIXED code first, observe outputs, then encode as tests
  - Create `tests/test_audit_remediation_preservation.py`
  - **2a — Agent Storage Round-Trip (Preservation Req 3.1)**:
    - Observe: `store_agent` + `get_agent` round-trips correctly on unfixed code
    - Write property: for all valid agents (random id, status, capabilities), stored data equals retrieved data
    - Verify test PASSES on UNFIXED code (confirms baseline)
  - **2b — Pipeline Result Fields Unchanged (Preservation Req 3.2)**:
    - Observe: `run_pipeline()` returns `PipelineResult` with all 8 fields populated on unfixed code
    - Write property: for any `WakeWordEvent`, `stages_completed`, `transcript`, `personality` fields are present and typed correctly
    - Verify test PASSES on UNFIXED code (confirms baseline)
  - **2c — LLM Response Unchanged Within Timeout (Preservation Req 3.3)**:
    - Observe: `complete()` returns `CompletionResponse` with `content`, `usage`, `latency_ms` on unfixed code with fast mock adapter
    - Write property: for any `CompletionRequest` with sub-1s mock adapter, response content is non-None and usage fields are populated
    - Verify test PASSES on UNFIXED code (confirms baseline)
  - **2d — Non-Critical Loader Stub Behavior (Preservation Req 3.6)**:
    - Observe: `_load_vision()`, `_load_agents()`, etc. return stubs (not raise) on unfixed code when import fails
    - Write property: for any exception raised in non-critical `_load_*` functions, result is a stub object with `initialize` attribute
    - Verify test PASSES on UNFIXED code (confirms baseline)
  - **2e — Active Agent Cache Hit (Preservation Req 3.8)**:
    - Observe: `get_active_agents()` returns cached list without DB hit on second call
    - Write property: after first call populates cache, second call issues zero SQL queries
    - Verify test PASSES on UNFIXED code (confirms baseline)
  - Mark task complete when all preservation tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.6, 3.8_

- [x] 3. Fix agent_storage.py — connection leak and N+1 query

  - [x] 3.1 Convert `_get_conn()` to `@contextmanager`
    - Add `from contextlib import contextmanager` import
    - Replace plain `_get_conn(self) -> sqlite3.Connection` with `@contextmanager` version that yields the connection and closes it in `finally`
    - Update all call sites in `agent_storage.py` from `with closing(self._get_conn()) as conn:` to `with self._get_conn() as conn:`
    - Affected methods: `store_agent`, `get_agent`, `update_agent`, `query_agents`, `store_performance_record`, `get_performance_records`, `store_evolution_event`, `create_agent_atomic`
    - _Bug_Condition: isRawConnectionLeak(input) — any call to `_get_conn()` outside `closing()` leaks fd_
    - _Expected_Behavior: connection always closed after `with self._get_conn() as conn:` block, even on exception_
    - _Preservation: all CRUD semantics (store/get/update/query) unchanged — same data in, same data out_
    - _Requirements: 2.3, 3.1_

  - [x] 3.2 Add `get_performance_records_bulk()` method
    - Add new async method `get_performance_records_bulk(self, agent_ids: list[str]) -> dict[str, list[PerformanceRecord]]`
    - Use single `WHERE agent_id IN (...)` query with `",".join("?" * len(agent_ids))` placeholders
    - Return `dict[str, list[PerformanceRecord]]` keyed by agent_id; empty list for agents with no records
    - Guard: return `{}` immediately when `agent_ids` is empty
    - _Bug_Condition: isNPlusOneQuery(input) — `query_agents()` calls `get_performance_records()` once per agent row_
    - _Expected_Behavior: exactly 1 SQL query for performance records regardless of N agents_
    - _Requirements: 2.6_

  - [x] 3.3 Fix N+1 in `query_agents()`
    - After fetching agent rows, collect all agent IDs into a list
    - Call `await self.get_performance_records_bulk(agent_ids)` once
    - Map bulk result to each `Agent` object in memory instead of per-row `get_performance_records()` calls
    - Remove the per-row `await self.get_performance_records(row[0])` call inside the loop
    - _Bug_Condition: isNPlusOneQuery(input) — N agents → N+1 queries_
    - _Expected_Behavior: N agents → exactly 2 queries total (1 agents + 1 bulk performance)_
    - _Preservation: `query_agents()` returns same agents with same performance history as before_
    - _Requirements: 2.6, 3.1_

  - [x] 3.4 Verify bug condition exploration tests 1a and 1b now pass
    - **Property 1: Expected Behavior** — Connection Closed + Single Bulk Query
    - **IMPORTANT**: Re-run the SAME tests from task 1 (1a and 1b) — do NOT write new tests
    - Run connection leak test (1a): assert no open connections after 1000 `_get_conn()` calls
    - Run N+1 query test (1b): assert `cursor.execute` called exactly 2 times for 10 agents
    - **EXPECTED OUTCOME**: Both tests PASS (confirms bugs 1.3 and 1.6 are fixed)
    - _Requirements: 2.3, 2.6_

  - [x] 3.5 Verify preservation tests 2a and 2e still pass
    - **Property 2: Preservation** — Agent Storage Semantics + Cache Hit
    - Re-run preservation tests 2a (round-trip) and 2e (cache hit) from task 2
    - **EXPECTED OUTCOME**: Both tests PASS (confirms no regressions in storage layer)
    - _Requirements: 3.1, 3.8_

- [x] 4. Fix orchestrator.py — STT caching, TTS caching, audit logging

  - [x] 4.1 Cache STT signature at startup
    - Add `self._stt_fn: Optional[Callable] = None` and `self._stt_params: Optional[list[str]] = None` to `__init__`
    - In `startup()`, after `asyncio.gather(*coros)`, resolve the transcription function using the same probe logic currently in `_stage_stt()` and call `inspect.signature()` once, storing parameter list in `self._stt_params`
    - Refactor `_stage_stt()` to read `self._stt_fn` and `self._stt_params` from cache instead of calling `inspect.signature()` on every invocation
    - _Bug_Condition: callsSignaturePerInvocation(input) — `inspect.signature(fn)` called on every `_stage_stt()` call_
    - _Expected_Behavior: `inspect.signature()` called at most once across all `_stage_stt()` invocations_
    - _Preservation: STT transcription output unchanged; same transcript returned for same audio_
    - _Requirements: 2.7, 3.2_

  - [x] 4.2 Cache TTS method at startup
    - Add `self._tts_fn: Optional[Callable] = None` to `__init__`
    - In `startup()`, probe the speech engine once for `synthesize_to_array`, `synthesize_response`, or `synthesize` and store the resolved callable in `self._tts_fn`
    - Refactor `_stage_tts()` to call `self._tts_fn` directly instead of repeating `getattr` chains
    - _Bug_Condition: resolvesAttrPerInvocation(input) — TTS method resolved via `getattr` chain on every call_
    - _Expected_Behavior: TTS method resolved once at startup; `_stage_tts()` calls cached reference_
    - _Preservation: TTS output unchanged; same synthesis result for same text and personality_
    - _Requirements: 2.8, 3.2_

  - [x] 4.3 Wire `AuditLogger` into `run_pipeline()`
    - Add `from Agent_Guru.security.audit.logger import AuditLogger, EventType` import
    - Add `self._audit_logger: AuditLogger = AuditLogger()` to `__init__`
    - After stage 8 completes in `run_pipeline()`, call `self._audit_logger.log_event(event_type=EventType.POLICY_ALLOWED if result.policy_allowed else EventType.POLICY_VIOLATION, actor_id="guru_pipeline", target_id=result.intent, outcome="success", details={...})`
    - In the `except` block, call `self._audit_logger.log_event(...)` with `outcome="failure"` and `error=str(exc)` in details
    - Details dict must include: `stages_completed`, `personality`, `transcript`, `error`
    - _Bug_Condition: lacksAuditLog(input) — `run_pipeline()` completes without calling `AuditLogger.log_event()`_
    - _Expected_Behavior: `log_event()` called exactly once per `run_pipeline()` invocation (success or error path)_
    - _Preservation: `PipelineResult` fields unchanged; audit logging is additive and does not alter the returned result_
    - _Requirements: 2.11, 3.2_

  - [x] 4.4 Verify bug condition exploration tests 1c and 1e now pass
    - **Property 1: Expected Behavior** — STT Signature Cached + Audit Log Written
    - Re-run exploration tests 1c (signature called once) and 1e (log_event called once) from task 1
    - **EXPECTED OUTCOME**: Both tests PASS (confirms bugs 1.7 and 1.11 are fixed)
    - _Requirements: 2.7, 2.11_

  - [x] 4.5 Verify preservation test 2b still passes
    - **Property 2: Preservation** — Pipeline Result Fields Unchanged
    - Re-run preservation test 2b from task 2
    - **EXPECTED OUTCOME**: Test PASSES (confirms no regressions in pipeline result shape)
    - _Requirements: 3.2_

- [x] 5. Fix llm_runtime.py — add timeout to adapter call

  - [x] 5.1 Wrap `adapter.complete()` with `asyncio.wait_for`
    - Add `import asyncio` if not already present at top of `llm_runtime.py`
    - In `complete()`, replace the `execute_with_retry` lambda `lambda: adapter.complete(request)` with `lambda: asyncio.wait_for(adapter.complete(request), timeout=timeout)`
    - Resolve timeout: `timeout = getattr(self.config, "timeout", None) or 30.0`
    - Place timeout resolution before the `execute_with_retry` call
    - _Bug_Condition: lacksLLMTimeout(input) — `adapter.complete(request)` hangs indefinitely on network stall_
    - _Expected_Behavior: `asyncio.TimeoutError` raised after `timeout` seconds; pipeline does not block indefinitely_
    - _Preservation: when adapter responds within timeout, `CompletionResponse` content/usage/latency_ms fields are identical to pre-fix behavior_
    - _Requirements: 2.10, 3.3_

  - [x] 5.2 Verify bug condition exploration test 1d now passes
    - **Property 1: Expected Behavior** — LLM Timeout Enforced
    - Re-run exploration test 1d (mock adapter sleeps indefinitely) from task 1
    - Assert `asyncio.TimeoutError` is raised within ~31 seconds (timeout + scheduling slack)
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug 1.10 is fixed)
    - _Requirements: 2.10_

  - [x] 5.3 Verify preservation test 2c still passes
    - **Property 2: Preservation** — LLM Response Unchanged Within Timeout
    - Re-run preservation test 2c from task 2 (fast mock adapter, sub-timeout response)
    - **EXPECTED OUTCOME**: Test PASSES (confirms no regressions for normal LLM calls)
    - _Requirements: 3.3_

- [x] 6. Fix main.py — deprecated API, signal handler, private access, critical re-raise

  - [x] 6.1 Replace `asyncio.get_event_loop()` with `asyncio.get_running_loop()`
    - In `_on_wake_word`, replace `asyncio.get_event_loop().run_in_executor(...)` with `asyncio.get_running_loop().run_in_executor(...)`
    - In the signal handler setup block, replace `loop = asyncio.get_event_loop()` with `loop = asyncio.get_running_loop()`
    - _Bug_Condition: usesGetEventLoop(input) — `asyncio.get_event_loop()` called inside running coroutine on Python 3.10+_
    - _Expected_Behavior: `asyncio.get_running_loop()` used; no `DeprecationWarning` or `RuntimeError` on Python 3.10+_
    - _Preservation: executor calls and signal handler registration behavior unchanged on Linux/macOS and Windows_
    - _Requirements: 2.4, 3.4, 3.5_

  - [x] 6.2 Narrow signal handler except clause
    - Verify the `try/except` around `loop.add_signal_handler(sig, _handle_signal)` catches only `NotImplementedError`
    - Remove any broader `except Exception` wrapping that would silently swallow unrelated errors
    - The correct pattern is: `try: loop.add_signal_handler(sig, _handle_signal) except NotImplementedError: signal.signal(sig, _handle_signal)`
    - _Bug_Condition: hasBroadSignalExcept(input) — outer except catches more than `NotImplementedError`_
    - _Expected_Behavior: only `NotImplementedError` (Windows incompatibility) is caught silently; all other errors propagate_
    - _Preservation: SIGINT/SIGTERM handlers still registered correctly on Linux/macOS and Windows_
    - _Requirements: 2.5, 3.4, 3.5_

  - [x] 6.3 Add `capture_command_audio()` public method to `WakeWordManager`
    - In `Agent_Guru/speech/wake_word_manager.py`, add public async method `capture_command_audio(self, chunks: int = 2) -> bytes`
    - Method body: loop `chunks` times, call `await asyncio.get_running_loop().run_in_executor(None, self._audio_capture.capture)`, concatenate results, return as `np.float32` bytes
    - Guard: if `self._audio_capture is None`, return `b""`
    - _Bug_Condition: accessesPrivateAudioCapture(input) — `main.py` accesses `wake_manager._audio_capture` directly_
    - _Expected_Behavior: `main.py` calls `wake_manager.capture_command_audio()` — internal `_audio_capture` stays encapsulated_
    - _Preservation: captured audio bytes are identical to the pre-fix direct access path_
    - _Requirements: 2.9, 3.7_

  - [x] 6.4 Update `main.py _on_wake_word` to use `capture_command_audio()`
    - Replace the `if wake_manager._audio_capture is not None:` block and its inner loop with `audio_bytes = await wake_manager.capture_command_audio()`
    - Remove the direct `wake_manager._audio_capture.capture` access
    - Keep the `rms` logging if desired by computing it from the returned bytes after the call
    - _Requirements: 2.9, 3.7_

  - [x] 6.5 Re-raise in critical `_load_speech()` and `_load_llm()`
    - In `_load_speech()`: after `return _stub("speech_engine", critical=True)`, add `raise` on the next line (so the stub call is replaced by `_stub(...)` call followed by `raise`)
    - In `_load_llm()`: same pattern — call `_stub("llm_runtime", critical=True)` then `raise`
    - Non-critical loaders (`_load_vision`, `_load_platform`, `_load_agents`, `_load_memory`, `_load_reasoning`, `_load_security`, `_load_policy`, `_load_avatar`, `_load_deployment`) must NOT be changed
    - _Bug_Condition: criticalLoadSilentlyDegrades(input) — `_load_speech()` / `_load_llm()` swallow exception and return stub_
    - _Expected_Behavior: after logging, exception re-raised — startup fails fast with clear error_
    - _Preservation: non-critical loaders still return stubs without raising; degraded startup still works for optional subsystems_
    - _Requirements: 2.15, 3.6_

  - [x] 6.6 Verify bug condition exploration test 1f now passes
    - **Property 1: Expected Behavior** — Critical Load Failure Propagates
    - Re-run exploration test 1f (patch `SpeechEngine.__init__` to raise) from task 1
    - Assert `_load_speech()` now raises instead of returning a stub
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug 1.15 is fixed)
    - _Requirements: 2.15_

  - [x] 6.7 Verify preservation test 2d still passes
    - **Property 2: Preservation** — Non-Critical Loader Stub Behavior Unchanged
    - Re-run preservation test 2d from task 2 (non-critical loaders still return stubs)
    - **EXPECTED OUTCOME**: Test PASSES (confirms no regressions for optional subsystems)
    - _Requirements: 3.6_

- [x] 7. Fix docker-compose.yml — parameterize database password

  - [x] 7.1 Replace hardcoded `POSTGRES_PASSWORD` with environment variable reference
    - In `docker-compose.yml`, replace `POSTGRES_PASSWORD: dev_password` with `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}`
    - Update `DATABASE_URL` default (if present in compose file) to use `${POSTGRES_PASSWORD}` instead of the literal string
    - Ensure no inline fallback value (e.g. `${POSTGRES_PASSWORD:-dev_password}`) remains
    - _Bug_Condition: isCommittedSecret(input) — `docker-compose.yml` contains `POSTGRES_PASSWORD: dev_password` in version control_
    - _Expected_Behavior: no literal password in compose file; secret supplied via `.env` excluded from VCS_
    - _Requirements: 2.2_

  - [x] 7.2 Document `POSTGRES_PASSWORD` in `.env.example`
    - Add `POSTGRES_PASSWORD=your-postgres-password-here` to `.env.example` if not already present
    - Verify `.env` is listed in `.gitignore`
    - _Requirements: 2.1, 2.2_

- [x] 8. Delete dead files and test artifacts

  - [x] 8.1 Delete dead root-level files
    - Delete: `yolov8n.pt`, `bandit_results.json`, `fix_b108_nosec.py`, `fix_tmp_paths.py`, `check_mic.py`, `pipeline_test.py`, `FULL_REPOSITORY_AUDIT_REPORT.txt`
    - Delete directory: `examples/application_control_demo.py` (or full `examples/` if otherwise empty)
    - _Bug_Condition: deadFileExists(input) — files serve no runtime or test purpose_
    - _Requirements: 2.12_

  - [x] 8.2 Delete generated artifact directories
    - Delete directories: `htmlcov/`, `.benchmarks/`, `.mypy_cache/`, `.ruff_cache/`, `test_logs/`
    - _Requirements: 2.12_

  - [x] 8.3 Add dead-file patterns to `.gitignore`
    - Add entries: `htmlcov/`, `.benchmarks/`, `.mypy_cache/`, `.ruff_cache/`, `test_logs/`, `bandit_results.json`, `*.pt` (model weights), `FULL_REPOSITORY_AUDIT_REPORT.txt`
    - _Requirements: 2.12_

  - [x] 8.4 Remove test artifacts from `reasoning/` module directory
    - Delete: `Agent_Guru/reasoning/.coverage`, `Agent_Guru/reasoning/.benchmarks/`, `Agent_Guru/reasoning/.hypothesis/`
    - Verify `.gitignore` at project root already covers `.coverage`, `.benchmarks/`, `.hypothesis/`
    - _Bug_Condition: testArtifactInModule(input) — test artifacts co-located inside `reasoning/` package directory_
    - _Requirements: 2.14_

- [x] 9. Remove duplicate modules and update imports

  - [x] 9.1 Delete duplicate `llm/runtime.py`
    - Verify `Agent_Guru/llm/runtime.py` is a duplicate of `Agent_Guru/llm/llm_runtime.py`
    - Search for all imports of `Agent_Guru.llm.runtime` or `from Agent_Guru.llm import runtime` across the codebase
    - Update any found imports to reference `Agent_Guru.llm.llm_runtime` (canonical)
    - Delete `Agent_Guru/llm/runtime.py`
    - _Bug_Condition: duplicateModuleExists(input) — `llm/runtime.py` duplicates `llm/llm_runtime.py`_
    - _Requirements: 2.13, 3.9_

  - [x] 9.2 Delete duplicate `deployment/onboarding_wizard.py`
    - Verify `Agent_Guru/deployment/onboarding_wizard.py` is a duplicate of `Agent_Guru/deployment/onboarding.py`
    - Search for all imports referencing `onboarding_wizard` and update to `onboarding`
    - Delete `Agent_Guru/deployment/onboarding_wizard.py`
    - _Requirements: 2.13, 3.9_

  - [x] 9.3 Delete duplicate `platform/controllers/messaging.py`
    - Verify `Agent_Guru/platform/controllers/messaging.py` is a duplicate of the canonical messaging controller
    - Search for all imports referencing the duplicate path and update to canonical
    - Delete `Agent_Guru/platform/controllers/messaging.py`
    - _Requirements: 2.13, 3.9_

- [x] 10. Checkpoint — Ensure all tests pass

  - Run the full exploration test suite: `pytest tests/test_audit_remediation_exploration.py -v`
  - All 6 exploration tests (1a–1f) must PASS (confirming all bugs are fixed)
  - Run the full preservation test suite: `pytest tests/test_audit_remediation_preservation.py -v`
  - All 5 preservation tests (2a–2e) must PASS (confirming no regressions)
  - Run the broader test suite: `pytest Agent_Guru/ -v --tb=short`
  - Verify no pre-existing tests are broken by the changes
  - Ensure all tests pass; ask the user if questions arise.
