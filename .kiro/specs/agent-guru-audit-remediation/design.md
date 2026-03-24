# Agent Guru Audit Remediation Bugfix Design

## Overview

A full system audit identified 15 distinct issues across the Agent Guru codebase spanning security
vulnerabilities, resource leaks, deprecated API usage, performance anti-patterns, a missing audit
pipeline integration, and accumulated dead code. This design formalizes the bug condition for each
issue, defines the expected correct behavior, hypothesizes root causes, and plans the targeted
minimal fixes required to bring the codebase to production quality without regressing any existing
functionality.

The fix strategy is additive and surgical: each change is scoped to the smallest possible diff that
eliminates the defect while preserving all observable behavior for non-buggy inputs.

---

## Glossary

- **Bug_Condition (C)**: The condition that identifies a defective input or code path — the set of
  states where the system behaves incorrectly.
- **Property (P)**: The desired correct behavior that must hold for all inputs satisfying C.
- **Preservation**: All existing behaviors for inputs NOT satisfying C that must remain unchanged
  after the fix.
- **`_get_conn()`**: Method in `Agent_Guru/agents/agent_storage.py` that opens a raw SQLite
  connection; callers are responsible for closing it.
- **`run_pipeline()`**: The 8-stage voice pipeline in `Agent_Guru/integration/orchestrator.py`
  that processes a `WakeWordEvent` end-to-end.
- **`complete()`**: The LLM completion method in `Agent_Guru/llm/llm_runtime.py` that delegates
  to a provider adapter via `error_handler.execute_with_retry()`.
- **`_stage_stt()`**: Stage 1 of the pipeline in `orchestrator.py`; calls `inspect.signature()`
  on every invocation to determine transcription function parameters.
- **`_stage_tts()`**: Stage 8 of the pipeline in `orchestrator.py`; resolves the TTS method via
  `getattr` chains on every invocation.
- **`AuditLogger`**: Class in `Agent_Guru/security/audit/logger.py` with `log_event()` method
  and `EventType` enum; currently never called from `run_pipeline()`.
- **`isBugCondition(input)`**: Pseudocode predicate — returns `true` when the input triggers one
  of the 15 defects catalogued in this document.
- **`F`**: The original (unfixed) function or code path.
- **`F'`**: The fixed function or code path.

---

## Bug Details

### Bug Condition

The 15 defects share a common structure: each is triggered by a specific code path or input that
causes the system to behave incorrectly. They are grouped into six categories.

**Formal Specification:**

```
FUNCTION isBugCondition(input)
  INPUT: input — a code path execution, file state, or runtime call
  OUTPUT: boolean

  RETURN (
    -- Security
    isCommittedSecret(input)                          -- 1.1, 1.2
    OR isRawConnectionLeak(input)                     -- 1.3
    -- Deprecated APIs
    OR usesGetEventLoop(input)                        -- 1.4
    OR hasBroadSignalExcept(input)                    -- 1.5
    -- Performance
    OR isNPlusOneQuery(input)                         -- 1.6
    OR callsSignaturePerInvocation(input)             -- 1.7
    OR resolvesAttrPerInvocation(input)               -- 1.8
    -- Encapsulation
    OR accessesPrivateAudioCapture(input)             -- 1.9
    -- Missing behaviors
    OR lacksLLMTimeout(input)                         -- 1.10
    OR lacksAuditLog(input)                           -- 1.11
    -- Dead code / duplicates
    OR deadFileExists(input)                          -- 1.12
    OR duplicateModuleExists(input)                   -- 1.13
    OR testArtifactInModule(input)                    -- 1.14
    -- Silent degradation
    OR criticalLoadSilentlyDegrades(input)            -- 1.15
  )
END FUNCTION
```

### Examples

**1.1 — Committed secret:**
- Buggy: `.env` contains `GEMINI_API_KEY=AIza...` tracked in git
- Fixed: `.env` contains `GEMINI_API_KEY=your-gemini-api-key-here`; `.env` in `.gitignore`

**1.2 — Hardcoded DB password:**
- Buggy: `docker-compose.yml` line `POSTGRES_PASSWORD: dev_password`
- Fixed: `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}` with no inline fallback

**1.3 — Connection leak:**
- Buggy: `conn = self._get_conn()` called without `closing()` wrapper leaks the fd
- Fixed: `_get_conn()` is a `@contextmanager` — `with self._get_conn() as conn:` enforced at source

**1.6 — N+1 query:**
- Buggy: `query_agents(status=ACTIVE)` returns 500 rows → 500 individual `get_performance_records()` calls
- Fixed: Single `WHERE agent_id IN (...)` query returns all records; mapped in memory

**1.10 — Missing LLM timeout:**
- Buggy: `adapter.complete(request)` hangs indefinitely on network stall
- Fixed: `asyncio.wait_for(adapter.complete(request), timeout=30.0)` raises `TimeoutError` after deadline

**1.11 — Missing audit log:**
- Buggy: `run_pipeline()` completes 8 stages; nothing written to `AuditLogger`
- Fixed: `_audit_logger.log_event(EventType.POLICY_ALLOWED, ...)` called after stage 8 (and in except block)

**1.15 — Silent critical degradation:**
- Buggy: `_load_speech()` catches exception, logs error, returns stub — startup continues silently
- Fixed: After logging, re-raises when `critical=True` — startup fails fast with clear error

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**

- `AgentStorage` CRUD methods (`store_agent`, `update_agent`, `get_agent`, `store_performance_record`,
  `store_evolution_event`, `create_agent_atomic`) continue to persist and retrieve data correctly.
- `IntegrationOrchestrator.run_pipeline()` continues to execute all 8 stages in order and return a
  `PipelineResult` with the same fields populated.
- `LLMRuntime.complete()` continues to return a `CompletionResponse` with the same content, usage,
  and latency fields when the provider responds within the timeout window.
- `main.py run()` continues to register `SIGINT`/`SIGTERM` handlers on Linux/macOS via
  `loop.add_signal_handler()` and fall back to `signal.signal()` on Windows.
- Non-critical subsystems (`vision`, `platform`, `agents`, `memory`, `reasoning`, `security`,
  `policy`, `avatar`, `deployment`) continue to log a warning and return a stub on load failure.
- `get_active_agents()` continues to return the cached list on cache-hit without hitting the DB.
- Canonical LLM, deployment, and messaging modules continue to expose the same public API surface
  after duplicate files are removed.
- `docker-compose.yml` continues to start the `postgres` service when `POSTGRES_PASSWORD` is
  supplied via `.env`.

**Scope:**
All inputs that do NOT satisfy `isBugCondition` must be completely unaffected. This includes:
- All valid agent storage operations with correct connection management
- All pipeline runs that complete within the LLM timeout window
- All non-critical subsystem load failures
- All signal handler registrations on supported platforms

---

## Hypothesized Root Cause

1. **Security (1.1, 1.2)**: Secrets were committed during initial scaffolding before `.gitignore`
   and environment variable patterns were established. The `docker-compose.yml` was written with a
   hardcoded fallback for developer convenience without considering version-control exposure.

2. **Resource Leak (1.3)**: `_get_conn()` was designed with the expectation that callers would
   always use `closing()`, but this is a convention rather than an enforced contract. A
   `@contextmanager` design would enforce correct usage at the call site.

3. **Deprecated APIs (1.4, 1.5)**: `asyncio.get_event_loop()` was the correct API before Python
   3.10; the code was not updated when the deprecation was introduced. The signal handler `except`
   clause was written broadly to catch all errors rather than only the expected
   `NotImplementedError` on Windows.

4. **N+1 Query (1.6)**: `query_agents()` was implemented with a straightforward loop calling the
   existing `get_performance_records()` per agent. No bulk-fetch method existed, so the path of
   least resistance was per-row fetching.

5. **Per-call Reflection (1.7, 1.8)**: `_stage_stt()` and `_stage_tts()` were written to be
   maximally flexible by probing the speech engine's API on every call. The caching step was
   deferred and never implemented.

6. **Private Access (1.9)**: `main.py` accesses `wake_manager._audio_capture` directly because no
   public method was provided by `WakeWordManager` for command audio capture.

7. **Missing Timeout (1.10)**: `execute_with_retry()` handles retries and circuit breaking but
   does not impose a wall-clock timeout on the underlying provider call. The timeout was not
   threaded through from `RuntimeConfig`.

8. **Missing Audit Log (1.11)**: `AuditLogger` was implemented in `security/audit/logger.py` but
   the integration point in `run_pipeline()` was never wired up.

9. **Dead Code / Duplicates (1.12, 1.13, 1.14)**: Accumulated during development — scratch
   scripts, intermediate audit artifacts, and parallel implementations that were never cleaned up.

10. **Silent Degradation (1.15)**: `_load_*` functions were designed to be fault-tolerant for
    optional subsystems. The `critical=True` flag was added to `_stub()` for logging but the
    re-raise path was never implemented.

---

## Correctness Properties

Property 1: Bug Condition — SQLite Connection Always Closed

_For any_ call to `AgentStorage._get_conn()`, the fixed implementation SHALL ensure the returned
connection is always closed after use, regardless of whether an exception occurs, by enforcing
closure at the source via a `@contextmanager` design rather than relying on caller convention.

**Validates: Requirements 2.3**

---

Property 2: Preservation — Agent Storage Semantics Unchanged

_For any_ call to `AgentStorage` methods (`store_agent`, `update_agent`, `get_agent`,
`store_performance_record`, `store_evolution_event`, `create_agent_atomic`) with valid inputs,
the fixed implementation SHALL produce the same observable data persistence and retrieval
semantics as the original implementation.

**Validates: Requirements 3.1**

---

Property 3: Bug Condition — N+1 Query Eliminated

_For any_ call to `AgentStorage.query_agents()` or `AgentStorage.get_active_agents()` that
returns N agent rows, the fixed implementation SHALL issue exactly 1 SQL query for performance
records (a single `WHERE agent_id IN (...)`) rather than N individual queries, regardless of N.

**Validates: Requirements 2.6**

---

Property 4: Bug Condition — STT Signature Cached

_For any_ sequence of N calls to `IntegrationOrchestrator._stage_stt()` where N ≥ 1, the fixed
implementation SHALL call `inspect.signature()` at most once (during `__init__` or `startup()`),
not once per invocation.

**Validates: Requirements 2.7**

---

Property 5: Bug Condition — LLM Timeout Enforced

_For any_ call to `LLMRuntime.complete()` where the provider adapter does not respond within the
configured timeout (default 30.0 seconds), the fixed implementation SHALL raise
`asyncio.TimeoutError` and SHALL NOT block the pipeline indefinitely.

**Validates: Requirements 2.10**

---

Property 6: Preservation — LLM Response Unchanged Within Timeout

_For any_ call to `LLMRuntime.complete()` where the provider adapter responds within the timeout
window, the fixed implementation SHALL return a `CompletionResponse` with the same `content`,
`usage`, and `latency_ms` fields as the original implementation.

**Validates: Requirements 3.3**

---

Property 7: Bug Condition — Audit Log Written for Every Pipeline Run

_For any_ `WakeWordEvent` passed to `IntegrationOrchestrator.run_pipeline()`, the fixed
implementation SHALL call `AuditLogger.log_event()` exactly once — either after stage 8 completes
successfully or in the exception handler — so that every pipeline execution appears in the audit
trail.

**Validates: Requirements 2.11**

---

Property 8: Preservation — Pipeline Result Unchanged

_For any_ `WakeWordEvent` passed to `IntegrationOrchestrator.run_pipeline()`, the fixed
implementation SHALL return a `PipelineResult` with the same `stages_completed`, `transcript`,
`llm_response`, `intent`, `policy_allowed`, `action_result`, `tts_response`, and `personality`
fields as the original implementation (audit logging is additive and does not alter the result).

**Validates: Requirements 3.2**

---

Property 9: Bug Condition — Critical Subsystem Load Failure Propagates

_For any_ exception raised inside `_load_speech()` or `_load_llm()` (the two `critical=True`
subsystems), the fixed implementation SHALL re-raise the exception after logging, causing
`run()` to exit with a clear error rather than continuing in a silently degraded state.

**Validates: Requirements 2.15**

---

Property 10: Preservation — Non-Critical Subsystem Degradation Unchanged

_For any_ exception raised inside a non-critical `_load_*` function (`_load_vision`,
`_load_platform`, `_load_agents`, `_load_memory`, `_load_reasoning`, `_load_security`,
`_load_policy`, `_load_avatar`, `_load_deployment`), the fixed implementation SHALL continue to
log a warning, return a stub, and allow startup to proceed — identical to the original behavior.

**Validates: Requirements 3.6**

---

## Fix Implementation

### Changes Required

Assuming the root cause analysis above is correct:

---

**File**: `Agent_Guru/agents/agent_storage.py`

**Change 1 — `_get_conn()` as `@contextmanager`**

Convert `_get_conn()` from a plain method returning a raw connection to a `@contextmanager` that
yields the connection and guarantees closure. Update all call sites from
`with closing(self._get_conn()) as conn:` to `with self._get_conn() as conn:`.

```python
from contextlib import contextmanager

@contextmanager
def _get_conn(self):
    conn = sqlite3.connect(self.db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
    finally:
        conn.close()
```

**Change 2 — `get_performance_records_bulk(agent_ids)`**

Add a new method that fetches all performance records for a list of agent IDs in a single query
and returns a `dict[str, list[PerformanceRecord]]`. Update `query_agents()` to call this method
once after fetching agent rows, then map records to agents in memory.

```python
async def get_performance_records_bulk(
    self, agent_ids: list[str]
) -> dict[str, list[PerformanceRecord]]:
    if not agent_ids:
        return {}
    placeholders = ",".join("?" * len(agent_ids))
    query = f"""
        SELECT agent_id, task_id, task_type, success,
               completion_time_ms, resource_usage, timestamp
        FROM performance_records
        WHERE agent_id IN ({placeholders})
        ORDER BY timestamp DESC
    """
    with self._get_conn() as conn:
        rows = conn.execute(query, agent_ids).fetchall()
    result: dict[str, list[PerformanceRecord]] = {aid: [] for aid in agent_ids}
    for row in rows:
        result[row[0]].append(PerformanceRecord(...))
    return result
```

---

**File**: `Agent_Guru/integration/orchestrator.py`

**Change 3 — Cache STT signature in `__init__` / `startup()`**

Add `self._stt_fn: Optional[Callable] = None` and `self._stt_params: Optional[list[str]] = None`
to `__init__`. In `startup()`, after subsystem init, resolve the transcription function and call
`inspect.signature()` once, storing the parameter list. `_stage_stt()` reads from the cache.

**Change 4 — Cache TTS method in `startup()`**

Add `self._tts_fn: Optional[Callable] = None` to `__init__`. In `startup()`, probe the speech
engine once for `synthesize_to_array`, `synthesize_response`, or `synthesize` and store the
resolved callable. `_stage_tts()` calls `self._tts_fn` directly.

**Change 5 — Wire `AuditLogger` into `run_pipeline()`**

Add `self._audit_logger: AuditLogger = AuditLogger()` to `__init__`. After stage 8 in
`run_pipeline()`, call:

```python
self._audit_logger.log_event(
    event_type=EventType.POLICY_ALLOWED if result.policy_allowed else EventType.POLICY_VIOLATION,
    actor_id="guru_pipeline",
    target_id=result.intent,
    outcome="success" if not result.error else "failure",
    details={
        "stages_completed": result.stages_completed,
        "personality": result.personality.value,
        "transcript": result.transcript,
        "error": result.error,
    },
)
```

Also call `log_event` in the `except` block with `outcome="failure"`.

---

**File**: `Agent_Guru/llm/llm_runtime.py`

**Change 6 — Wrap adapter call with `asyncio.wait_for`**

In `complete()`, replace:

```python
response = await self.error_handler.execute_with_retry(
    lambda: adapter.complete(request),
    provider=provider.value,
)
```

with:

```python
timeout = getattr(self.config, "timeout", None) or 30.0
response = await self.error_handler.execute_with_retry(
    lambda: asyncio.wait_for(adapter.complete(request), timeout=timeout),
    provider=provider.value,
)
```

---

**File**: `main.py`

**Change 7 — Replace `asyncio.get_event_loop()` with `asyncio.get_running_loop()`**

In `_on_wake_word`, replace:
```python
chunk = await asyncio.get_event_loop().run_in_executor(...)
```
with:
```python
chunk = await asyncio.get_running_loop().run_in_executor(...)
```

In the signal handler block, replace:
```python
loop = asyncio.get_event_loop()
```
with:
```python
loop = asyncio.get_running_loop()
```

**Change 8 — Narrow signal handler except clause**

The outer `except` around `loop.add_signal_handler()` is already `except NotImplementedError` —
verify this is the only catch and remove any broader `except Exception` wrapping.

**Change 9 — Add `WakeWordManager.capture_command_audio()` public method**

In `Agent_Guru/speech/wake_word_manager.py`, add:

```python
async def capture_command_audio(self, chunks: int = 2) -> bytes:
    """Capture command audio after wake word detection."""
    import numpy as np
    captured = []
    for _ in range(chunks):
        chunk = await asyncio.get_running_loop().run_in_executor(
            None, self._audio_capture.capture
        )
        captured.append(chunk)
    return np.concatenate(captured).astype(np.float32).tobytes()
```

In `main.py _on_wake_word`, replace the direct `wake_manager._audio_capture` access with:
```python
audio_bytes = await wake_manager.capture_command_audio()
```

**Change 10 — Re-raise in critical `_load_*` functions**

In `_load_speech()` and `_load_llm()`, after `return _stub(name, critical=True)`, add `raise`:

```python
def _load_speech():
    try:
        from Agent_Guru.speech.engine import SpeechEngine
        return SpeechEngine()
    except Exception as e:
        logger.error("SpeechEngine failed to load: %s", e)
        _stub("speech_engine", critical=True)
        raise
```

---

**File**: `docker-compose.yml`

**Change 11 — Parameterize database password**

Replace:
```yaml
POSTGRES_PASSWORD: dev_password
```
with:
```yaml
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
```

Update `DATABASE_URL` default to use `${POSTGRES_PASSWORD}` as well. Document in `.env.example`.

---

**Dead file deletion (1.12)**

Delete: `yolov8n.pt`, `bandit_results.json`, `fix_b108_nosec.py`, `fix_tmp_paths.py`,
`check_mic.py`, `pipeline_test.py`, `examples/application_control_demo.py`,
`FULL_REPOSITORY_AUDIT_REPORT.txt`, `htmlcov/`, `.benchmarks/`, `.mypy_cache/`, `.ruff_cache/`,
`test_logs/`. Add patterns to `.gitignore`.

**Duplicate consolidation (1.13)**

Delete `Agent_Guru/llm/runtime.py`, `Agent_Guru/deployment/onboarding_wizard.py`,
`Agent_Guru/platform/controllers/messaging.py`. Update any imports referencing these files to
point to the canonical modules.

**Test artifact removal (1.14)**

Delete `Agent_Guru/reasoning/.coverage`, `Agent_Guru/reasoning/.benchmarks/`,
`Agent_Guru/reasoning/.hypothesis/`. Ensure `.gitignore` covers these patterns at the project root.

---

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate
each defect on unfixed code to confirm root cause analysis; then verify the fix works correctly
and preserves all existing behavior.

---

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each bug BEFORE implementing the fix. Confirm
or refute the root cause analysis. If refuted, re-hypothesize.

**Test Plan**: Write tests that exercise each defective code path and assert the incorrect behavior
is observable. Run on UNFIXED code to observe failures.

**Test Cases**:

1. **Connection Leak Test**: Call `_get_conn()` 1000 times without `closing()` and assert that
   SQLite reports open connections — will demonstrate the leak on unfixed code.
2. **N+1 Query Test**: Mock the DB cursor, call `query_agents()` with 10 agents, assert
   `cursor.execute` is called 11 times (1 for agents + 10 for records) — will fail on unfixed code.
3. **STT Signature Test**: Mock `inspect.signature`, call `_stage_stt()` 5 times, assert
   `inspect.signature` was called 5 times — will demonstrate per-call overhead on unfixed code.
4. **LLM Timeout Test**: Mock `adapter.complete` to sleep indefinitely, call `complete()`, assert
   it never returns — will demonstrate the hang on unfixed code.
5. **Audit Log Test**: Call `run_pipeline()` with a valid event, assert `AuditLogger.log_event`
   was never called — will demonstrate the audit gap on unfixed code.
6. **Critical Load Test**: Patch `SpeechEngine.__init__` to raise, call `_load_speech()`, assert
   it returns a stub without raising — will demonstrate silent degradation on unfixed code.

**Expected Counterexamples**:
- `_get_conn()` returns connections that are never closed when called without `closing()`
- `query_agents()` issues N+1 DB calls for N agents
- `inspect.signature()` called once per `_stage_stt()` invocation
- `complete()` blocks indefinitely when adapter hangs
- `run_pipeline()` completes without any audit log entry
- `_load_speech()` swallows exceptions and returns a stub

---

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces
the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := fixedFunction(input)
  ASSERT expectedBehavior(result)
END FOR
```

---

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function
produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT originalFunction(input) = fixedFunction(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for valid agent storage operations, pipeline
runs within timeout, and non-critical load failures; then write property-based tests capturing
that behavior.

**Test Cases**:
1. **Agent Storage Preservation**: Generate random valid agents, store and retrieve them, assert
   data round-trips correctly after `_get_conn()` is converted to a context manager.
2. **Pipeline Result Preservation**: Generate random `WakeWordEvent` inputs, run the pipeline,
   assert `PipelineResult` fields are identical before and after audit logging is added.
3. **LLM Response Preservation**: Generate random `CompletionRequest` inputs with fast mock
   adapters, assert `CompletionResponse` content is unchanged after timeout wrapper is added.
4. **Non-Critical Degradation Preservation**: Generate random exceptions in non-critical loaders,
   assert they still return stubs and do not raise after the critical re-raise fix.

---

### Unit Tests

- Test `_get_conn()` as context manager: verify connection is closed on normal exit and on exception
- Test `get_performance_records_bulk()`: verify single query issued for N agent IDs
- Test `query_agents()` with bulk fetch: verify N agents returned with correct performance history
- Test `_stage_stt()` caching: verify `inspect.signature` called once across multiple invocations
- Test `complete()` timeout: verify `asyncio.TimeoutError` raised when adapter exceeds deadline
- Test `run_pipeline()` audit: verify `log_event` called once per pipeline run (success and error)
- Test `_load_speech()` re-raise: verify exception propagates when `SpeechEngine` fails to load
- Test `_load_vision()` stub: verify stub returned (no raise) when `GuruVisionEngine` fails
- Test `capture_command_audio()`: verify public method returns concatenated audio bytes
- Test `docker-compose.yml`: verify no literal `dev_password` string present

### Property-Based Tests

- Generate random lists of agent IDs (1–500): verify `get_performance_records_bulk` always issues
  exactly 1 SQL query regardless of list length (Property 3)
- Generate random N ≥ 1 `_stage_stt()` invocations: verify `inspect.signature` called ≤ 1 time
  total (Property 4)
- Generate random `CompletionRequest` inputs with sub-timeout adapters: verify response content
  unchanged after timeout wrapper added (Property 6)
- Generate random `WakeWordEvent` inputs: verify `log_event` called exactly once per
  `run_pipeline()` call (Property 7)
- Generate random `WakeWordEvent` inputs: verify `PipelineResult` fields identical before and
  after audit logging added (Property 8)
- Generate random exceptions in non-critical loaders: verify stub returned, no raise (Property 10)

### Integration Tests

- Full pipeline run with real subsystem stubs: verify audit log entry written with correct fields
- Agent storage round-trip: store 100 agents with performance records, query all, verify data
  integrity and single bulk query
- LLM timeout integration: mock slow adapter at 35s, verify pipeline returns error within 31s
- Signal handler registration: verify `SIGINT`/`SIGTERM` handlers registered on Linux/macOS
- Dead file absence: verify all 13 dead files/directories do not exist after cleanup
- Duplicate module absence: verify `llm/runtime.py`, `deployment/onboarding_wizard.py`,
  `platform/controllers/messaging.py` do not exist; verify canonical imports resolve correctly
