# Implementation Plan: Agent Guru World-Class Audit

## Overview

This plan implements the complete Agent Guru World-Class Audit system across all 9 phases, transforming the codebase to production-ready, world-class quality. The audit system is a Python 3.11+ orchestrated pipeline that executes phases in DAG order, with each phase writing structured findings to `AUDIT_REPORT_MASTER.md`.

**Phase Execution Order (DAG):**
- Phase 0: Infrastructure Setup (foundation)
- Phase 1: Repository Intelligence Scan (baseline)
- Phase 2: Competitive Analysis (after Phase 1)
- Phase 3: Bug and Failure Detection (after Phase 1)
- Phase 4: Performance Optimization (after Phase 3)
- Phase 5: Architectural Cleanup (after Phase 3)
- Phase 6: Integration Validation (after Phases 4 & 5)
- Phase 7: World-Class Code Quality (after Phase 6)
- Phase 8: Deployment and Production Readiness (after Phase 7)
- Phase 9: Final Master Audit Report (after Phases 2 & 8)

**Enforcement Standards:**
- Every phase that modifies `Agent_Guru/` includes enforcement gate sub-tasks
- Enforcement gate: `pytest -x` + `ruff format --check` + `ruff check --select ALL` + `mypy --strict`
- Performance tasks include before/after benchmark sub-tasks
- Integration validation includes property-based test sub-tasks for all 22 correctness properties

**2025 Technology Stack:**
- **Ruff** (replaces Black/flake8/isort): `ruff format` + `ruff check`
- **asyncio.TaskGroup** (Python 3.11+): Structured concurrency with proper exception propagation
- **Kokoro-ONNX** (replaces abandoned Coqui TTS): v1.0, MIT, ~300MB, ONNX-based
- **faster-whisper**: 8-bit quantization (`compute_type="int8_float16"`)
- **Silero VAD v5**: <1ms per 30ms chunk, ONNX support
- **structlog 24.x**: JSON production logging with `JSONRenderer` and `TimeStamper(fmt="iso")`
- **pvporcupine**: Latest PyPI version with `.ppn` model files

## Tasks

- [x] 1. Phase 0 — Audit Infrastructure Setup
  - [x] 1.1 Create `audit/` package skeleton with `__init__.py`, `runner.py`, `report.py`, `models.py`, `enforcement.py`, and `phases/__init__.py`
    - Implement all dataclasses from `audit/models.py`: `Severity`, `FindingCategory`, `Finding`, `ModuleInventory`, `DependencyEdge`, `PerformanceMetric`, `RemediationItem`, `IntegrationCheckResult`, `AuditReport`
    - All fields must have complete type annotations; use `from __future__ import annotations`
    - _Requirements: 1.1, 3.13, 9.1_

  - [x] 1.2 Implement `audit/enforcement.py` — the enforcement gate
    - Implement `run_enforcement_gate(phase_name: str) -> bool` running `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict` in sequence; stop and return `False` on first failure
    - Implement `run_auto_fix_gate(phase_name: str) -> bool` running `ruff format Agent_Guru/` and `ruff check Agent_Guru/ --fix` before re-running the full gate
    - Implement `_log_gate_failure(phase_name, cmd, result)` that appends the failure to `AUDIT_REPORT_MASTER.md`
    - _Requirements: 10.7, 10.8_

  - [x] 1.3 Implement `audit/report.py` — the `MasterReportWriter` class
    - Implement `atomic_write(path: Path, content: str) -> None` using temp-file + rename for crash-safe writes
    - Implement `write(report: AuditReport) -> None` that produces a valid Markdown document with exactly 9 top-level sections in the order specified in Requirement 9.1
    - Implement `add_phase_error(phase_name: str, exc: Exception) -> None` and `add_temporary_regression(scope: str, plan: str) -> None`
    - _Requirements: 9.1, 9.6, 10.9_

  - [x] 1.4 Implement `audit/runner.py` — the `AuditRunner` orchestrator
    - Implement `async run_phase(phase_fn, phase_name: str) -> bool` with try/except that logs failures and skips dependent phases per the DAG
    - Wire all 9 phase functions in DAG order: Phase 1 first; Phases 2 and 3 after Phase 1; Phase 4 and 5 after Phase 3; Phase 6 after Phases 4 and 5; Phase 7 after Phase 6; Phase 8 after Phase 7; Phase 9 after Phases 2 and 8
    - _Requirements: 9.1, 9.2_

  - [x] 1.5 Create `audit/tests/conftest.py` with Hypothesis CI profile
    - Register `settings.register_profile("ci", max_examples=100, derandomize=True, suppress_health_check=[HealthCheck.too_slow])`
    - Call `settings.load_profile("ci")`
    - _Requirements: Design — Testing Strategy_

  - [x] 1.6 Write unit tests for `audit/models.py` in `audit/tests/test_models.py`
    - Test that every dataclass can be instantiated with valid arguments
    - Test that `Severity` and `FindingCategory` enums have the expected members
    - _Requirements: 9.1_

  - [x] 1.7 Write unit tests for `audit/report.py` in `audit/tests/test_report.py`
    - Test `atomic_write` produces the correct file content
    - Test `write` produces a document with exactly 9 top-level `##` headings
    - _Requirements: 9.1, 9.6_

- [x] 2. Phase 1 — Repository Intelligence Scan
  - [x] 2.1 Implement `audit/phases/phase1_repo_scan.py` — `RepositoryScanner` class
    - Implement `scan_all_modules() -> list[ModuleInventory]` using `ast.parse()` on every `.py` file under `Agent_Guru/` (excluding `__pycache__`)
    - Implement `_ModuleVisitor(ast.NodeVisitor)` that counts public classes, public functions, and import statements
    - Implement `build_dependency_dag(inventories) -> tuple[nx.DiGraph, list[list[str]]]` using `networkx` for cycle detection via `nx.simple_cycles()`
    - _Requirements: 1.1, 1.2_

  - [x] 2.2 Implement `VoicePipelineTracer` in `phase1_repo_scan.py`
    - Trace the call graph from `speech/audio/capture.py` through `speech/audio/wake_word.py`, `speech/stt/whisper_stt.py`, `reasoning/engine.py`, `llm/llm_runtime.py`, `speech/tts/tts_engine.py` to audio playback
    - Record function name, input type, and output type at each boundary using AST analysis
    - _Requirements: 1.3_

  - [x] 2.3 Implement `StartupAnalyzer` in `phase1_repo_scan.py`
    - Parse `main.py` and trace every `asyncio.create_task()`, `threading.Thread()`, and `subprocess.Popen()` call
    - Record coroutine/function name and whether a corresponding cancellation/join is present
    - _Requirements: 1.4_

  - [x] 2.4 Implement external service boundary enumeration and configuration entry point mapping
    - Enumerate every external service boundary (OpenAI, Anthropic, Google Gemini, Ollama, sounddevice, pywin32, pyobjc, dbus-python) with protocol, library, and error-handling strategy
    - Document every configuration entry point (`.env`, `pyproject.toml`, `pytest.ini`, `mypy.ini`, per-module `config.py`) and which subsystem consumes each key
    - Count and list every `__pycache__` directory and `.pyc` file
    - _Requirements: 1.5, 1.6, 1.8_

  - [x] 2.5 Write Phase 1 output to `AUDIT_REPORT_MASTER.md` under "Repository Intelligence" section
    - Include: module inventory table, dependency DAG as Mermaid diagram (top 20 nodes), cycle list, voice pipeline trace table, startup lifecycle table, external service boundary table, configuration entry point table, `__pycache__`/`.pyc` count
    - _Requirements: 1.7_

  - [x] 2.6 Write property test for `RepositoryScanner` in `audit/tests/test_phase1.py`
    - **Property 1: Module Inventory Completeness** — for any set of Python file paths, `scan_all_modules()` returns exactly one `ModuleInventory` per file with no duplicates
    - **Validates: Requirements 1.1, 1.7**

  - [x] 2.7 Write property test for dependency DAG in `audit/tests/test_phase1.py`
    - **Property 2: Dependency DAG Correctness** — for any module A with `import B`, the DAG contains edge A->B; if no import exists, no edge is present
    - **Property 3: Cycle Detection Completeness** — for any graph with known cycles, every cycle is reported with no false positives
    - **Validates: Requirements 1.2, 3.5**

- [x] 3. Phase 2 — Competitive Analysis
  - [x] 3.1 Create `audit/data/competitive_baselines.json` with published metrics for all 7 competitors
    - Include for each competitor: `wake_word_p95_ms`, `stt_wer_percent`, `e2e_p95_ms`, `idle_cpu_percent`, `idle_ram_mb`, `offline_capable`, `multi_platform`, `open_api`
    - Competitors: Alexa, Siri, Google Assistant, ChatGPT Desktop, Claude Desktop, Open Interpreter, OpenVoiceOS
    - _Requirements: 2.1_

  - [x] 3.2 Implement `audit/phases/phase2_competitive.py` — `CompetitiveAnalyzer` class
    - Implement `CompetitorBaseline` dataclass and `compute_gap_analysis(agent_guru_metrics, baselines, quality_targets) -> tuple[list[RemediationItem], list[dict]]`
    - Apply the prioritization formula: `competitive_impact_score = (gap_magnitude / target_value) * platforms_affected`
    - Identify every metric where Agent Guru does not meet its own stated target from `quality.md`
    - Identify capabilities present in competitors but absent/incomplete in Agent Guru
    - Identify Agent Guru competitive advantages (dual personality, biometric auth, self-improvement, local LLM)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6_

  - [x] 3.3 Write competitive matrix and gap analysis to `AUDIT_REPORT_MASTER.md` under "Competitive Analysis" section
    - Use atomic write; if write fails emit error to stderr, exit non-zero, write no partial content
    - Include prioritized remediation list ordered by `competitive_impact_score` descending
    - Each remediation item must specify: gap, affected module, required change, expected metric improvement as absolute delta with unit and percentile
    - _Requirements: 2.5, 2.6_

  - [x] 3.4 Write property tests for competitive analysis in `audit/tests/test_phase1.py`
    - **Property 4: Competitive Gap Detection Correctness** — for any (measured, target) pair where measured > target, gap analysis classifies as gap; where measured <= target, no gap
    - **Property 5: Remediation List Ordering** — for any list of `RemediationItem` objects, the output is sorted descending by `competitive_impact_score` with no inversions
    - **Validates: Requirements 2.2, 2.3, 2.6, 9.3**

- [ ] 4. Phase 3 — Bug and Failure Detection (run all tools)
  - [x] 4.1 Implement `audit/phases/phase3_bug_detection.py` — `BugDetector` class with all 12 detection methods
    - Implement `_run_py_compile()`: run `python -m py_compile` on every `.py` file; report file path, error message, line number
    - Implement `_run_ruff_all()`: run `ruff check Agent_Guru/ --select ALL`; parse output into `Finding` objects
    - Implement `_run_mypy_strict()`: run `mypy Agent_Guru/ --strict`; parse output into `Finding` objects
    - Implement `_run_bandit()`: run `bandit -r Agent_Guru/ -ll`; report every HIGH and MEDIUM severity issue with CWE reference
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 4.2 Implement circular import detection, broken import detection, and platform guard checking
    - Implement `_detect_circular_imports()`: use the dependency DAG from Phase 1 to find cycles; report each as ordered list of module paths
    - Implement `_detect_broken_imports()`: for every `import` or `from ... import` statement, verify the referenced module/class/function exists at the referenced path via AST analysis
    - Implement `_check_platform_guards()`: verify every `pywin32`, `pyobjc`, `dbus-python` import is guarded by `sys.platform` check or `try/except ImportError`
    - _Requirements: 3.5, 3.6, 3.12_

  - [x] 4.3 Implement `AsyncAntipatternVisitor` and race condition detector
    - Implement `AsyncAntipatternVisitor(ast.NodeVisitor)` detecting: blocking I/O inside `async def` (time.sleep, requests.*, urllib.request.urlopen, subprocess.run/call/check_output, sync open() outside run_in_executor), missing `await` on coroutines, `asyncio.gather` with `return_exceptions=False` and no per-task handler
    - Implement `_detect_race_conditions()`: build set of module-level and class-level mutable variables; for each, find all coroutines/threads that access it; report if >1 accessor and no synchronization primitive (asyncio.Lock, asyncio.Semaphore, threading.Lock, threading.RLock, threading.Semaphore)
    - _Requirements: 3.7, 3.8_

  - [x] 4.4 Implement resource leak detector and duplicate implementation detector
    - Implement `_detect_resource_leaks()`: track every `open()`, `sqlite3.connect()`, `aiohttp.ClientSession()`, `sounddevice.InputStream()`, `torch.cuda.memory_allocated()` call; verify each is inside a `with` statement or has `.close()` in all code paths including `except`/`finally`
    - Implement `_run_ruff_unused()`: run `ruff --select F401,F841`; report unused imports and unused variables
    - Implement `_detect_duplicates()`: extract public function/class names and type signatures from all modules; report any pair sharing >= 2 public symbols with identical names and type signatures, with both file paths, overlapping API surface, and consolidation strategy
    - _Requirements: 3.9, 3.10, 3.11_

  - [x] 4.5 Fix all findings detected in tasks 4.1-4.4 in the original source files
    - Fix every compile error, type error, lint violation, security issue, broken import, async anti-pattern, race condition, resource leak, unused import, and platform guard violation directly in the affected `Agent_Guru/` source file
    - Do NOT create shadow files (`*_v2.py`, `*_fixed.py`, `*_optimized.py`)
    - Update every caller when a public API changes
    - _Requirements: 3.1-3.12, 10.1, 10.2, 10.6_

  - [ ]* 4.6 Run enforcement gate after all Phase 3 fixes
    - Run `pytest Agent_Guru/ -x --tb=short -q` — must pass with zero failures
    - Run `ruff format --check Agent_Guru/` — must report zero formatting violations
    - Run `ruff check Agent_Guru/ --select ALL` — must report zero violations
    - Run `mypy Agent_Guru/ --strict` — must report zero type errors
    - _Requirements: 10.7, 10.8_

  - [~] 4.7 Write Phase 3 findings to `AUDIT_REPORT_MASTER.md` under "Bug and Failure Report" section
    - Severity-sorted table of all findings with file path, line number, rule code, description, and fixed status
    - _Requirements: 3.13_

  - [x] 4.8 Write property tests for bug detection in `audit/tests/test_phase3_properties.py`
    - **Property 6: Async Anti-pattern Detection Completeness** — any `async def` with a blocking call produces >= 1 finding; any `async def` without blocking calls produces 0 findings
    - **Property 7: Broken Import Detection Correctness** — any import of a non-existent symbol produces a finding; any import of an existing symbol produces no finding
    - **Property 8: Duplicate Implementation Detection** — any module pair sharing >= 2 public symbols with identical signatures produces a finding; pairs sharing < 2 do not
    - **Validates: Requirements 3.6, 3.7, 3.11**

- [ ] 5. Phase 4 — Performance Optimization
  - [~] 5.1 Benchmark Voice_Pipeline end-to-end P95 latency before any optimization
    - Measure and record baseline P95 latency for: wake word detection, STT, end-to-end response, idle CPU, idle RAM, startup time, intent classification
    - Record all baselines in `AUDIT_REPORT_MASTER.md` under "Performance Optimization" section
    - _Requirements: 4.1_

  - [~] 5.2 Replace Vosk-based wake word detector with pvporcupine in `speech/audio/wake_word.py`
    - Implement `WakeWordDetector` class using `pvporcupine.create()` with `FRAME_LENGTH=512`, `SAMPLE_RATE=16000`
    - Implement `process_frame(pcm_frame: np.ndarray) -> int` returning keyword index or -1
    - Implement `delete() -> None` releasing pvporcupine resources
    - Wire `on_detection: Callable[[str], None]` callback for "hey guru" and "hey maya" keywords using `.ppn` model files
    - Use latest pvporcupine PyPI version; store access key in environment variable `PORCUPINE_ACCESS_KEY`
    - _Requirements: 4.2_

  - [ ]* 5.3 Benchmark pvporcupine wake word P95 latency and idle CPU after replacement
    - Measure P95 latency across 1,000 samples; must be < 200ms
    - Measure idle CPU usage; must be < 10%
    - Record before/after delta in `AUDIT_REPORT_MASTER.md`
    - _Requirements: 4.2, 4.11_

  - [ ]* 5.4 Run enforcement gate after pvporcupine integration
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - _Requirements: 4.12, 10.7, 10.8_

  - [~] 5.5 Implement `LockFreeRingBuffer` in `speech/audio/capture.py`
    - Implement `LockFreeRingBuffer` with `CAPACITY=163840` (next power of 2 above 160,000 = 10s @ 16kHz), `SAMPLE_RATE=16000`
    - Implement `write(samples: np.ndarray) -> None` with wrap-around logic for SPSC use
    - Implement `read_frame(frame_size: int) -> np.ndarray | None` returning None if insufficient data
    - Implement `available_samples` property
    - Replace blocking `sd.rec()` in `MicrophoneCapture` with sounddevice callback that calls `ring_buffer.write()`
    - _Requirements: 4.3_

  - [x] 5.6 Write property tests for `LockFreeRingBuffer` in `audit/tests/test_phase4_properties.py`
    - **Property 9: Ring Buffer Capacity Invariant** — for any sequence of writes, `available_samples` never exceeds `CAPACITY - 1`
    - **Property 10: Ring Buffer Read/Write Round Trip** — for any samples written that do not exceed capacity, reading back returns the exact samples in order
    - **Validates: Requirements 4.3**

  - [ ]* 5.7 Run enforcement gate after ring buffer implementation
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - _Requirements: 4.12, 10.7, 10.8_

  - [~] 5.8 Implement `GPUMemoryPool` in `integration/gpu_pool.py`
    - Implement `GPUMemoryPool` with `max_vram_bytes` defaulting to 80% of total VRAM
    - Implement `allocate(shape, dtype) -> Optional[torch.Tensor]` returning None if VRAM exhausted
    - Implement `release(tensor: torch.Tensor) -> None` zeroing and returning tensor to pool
    - Implement `utilization_percent` property
    - Wire GPU pool into STT, TTS, vision, and avatar subsystems so they share VRAM without reallocation
    - _Requirements: 4.5_

  - [x] 5.9 Write property test for `GPUMemoryPool` in `audit/tests/test_phase4_properties.py`
    - **Property 21: GPU Pool VRAM Invariant** — for any sequence of `allocate()` and `release()` operations, `allocated_bytes` never exceeds `max_vram_bytes`; any `allocate()` that would exceed the limit returns `None`
    - **Validates: Requirements 4.5**

  - [ ]* 5.10 Run enforcement gate after GPU pool implementation
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - _Requirements: 4.12, 10.7, 10.8_

  - [~] 5.11 Implement `LRUResponseCache` in `reasoning/response/response_cache.py`
    - Implement `LRUResponseCache` with `max_size=1024`, `ttl_seconds=300.0` using `OrderedDict`
    - Implement `get(query: str) -> Optional[str]` with TTL expiry check and LRU promotion
    - Implement `put(query: str, response: str) -> None` with LRU eviction when at capacity
    - Implement `invalidate(query: str) -> bool` and `size` property
    - Key queries by `hashlib.sha256(query.strip().lower().encode()).hexdigest()`
    - Wire cache into `reasoning/engine.py` so repeated identical queries return within 1ms
    - _Requirements: 4.7_

  - [x] 5.12 Write property tests for `LRUResponseCache` in `audit/tests/test_phase4_properties.py`
    - **Property 11: LRU Cache Size Invariant** — for any sequence of `put()` operations, `size` never exceeds `max_size`
    - **Property 12: LRU Cache Eviction Order** — at capacity, the entry evicted is the one whose last access was earliest
    - **Property 13: LRU Cache TTL Expiry** — any entry older than `ttl_seconds` returns `None` on `get()`
    - **Property 14: LRU Cache Round Trip** — `put(q, r)` then `get(q)` within TTL returns `r`
    - **Validates: Requirements 4.7**

  - [ ]* 5.13 Run enforcement gate after LRU cache implementation
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - _Requirements: 4.12, 10.7, 10.8_

  - [~] 5.14 Implement `LazyModel` in `core/lazy_model.py` and wire lazy loading for all ML models
    - Implement `LazyModel(Generic[T])` with `factory: Callable[[], T]` and optional `prewarm_fn: Callable[[T], None]`
    - Implement `async get() -> T` using `asyncio.Lock` to prevent double-initialization
    - Wrap faster-whisper `WhisperModel` with `compute_type="int8_float16"` (target: <1s STT P95) in `LazyModel` with pre-warm dummy inference
    - Wrap Kokoro-ONNX TTS engine (replaces Coqui TTS — Coqui is abandoned; use `kokoro-onnx` package, MIT license, ~300MB) with pre-warm (target: <500ms TTS P95)
    - Wrap InsightFace (target: <50ms face recognition P95) and ONNX emotion models (target: <50ms) in `LazyModel` with pre-warm dummy inference
    - _Requirements: 4.4_

  - [~] 5.15 Implement asyncio.TaskGroup-based LLM token streaming in `llm/llm_runtime.py`
    - Replace any `asyncio.gather` calls with `asyncio.TaskGroup` (Python 3.11+ structured concurrency) for proper exception propagation
    - Implement streaming so the first token reaches `speech/tts/tts_engine.py` within 500ms of the LLM call being issued
    - Wire TTS playback: Kokoro-ONNX `synthesize()` WAV bytes must be played back through `sounddevice` without error
    - _Requirements: 4.6_

  - [~] 5.16 Profile and optimize startup time in `main.py`
    - Defer initialization of vision, avatar, deployment, and self-improvement subsystems until first use
    - Target: startup from `main.py` invocation to "Listening for wake words" log line in < 10 seconds on NVIDIA GPU with CUDA 11.8+ and Ollama running
    - Target: idle RAM < 500MB after deferral
    - _Requirements: 4.8, 4.9_

  - [~] 5.17 Implement and optimize trie lookup in `reasoning/intent/fast_router.py`
    - Implement or optimize the trie data structure for intent classification
    - Target: P95 intent classification latency < 50ms for the 200 most common commands
    - _Requirements: 4.10_

  - [x] 5.18 Write property test for trie intent classification in `audit/tests/test_phase4_properties.py`
    - **Property 22: Trie Intent Classification Correctness** — any command exactly matching a registered pattern returns the correct intent type; any non-matching command returns `None` or routes to neural fallback
    - **Validates: Requirements 4.10**

  - [ ]* 5.19 Benchmark all optimized metrics and record before/after table
    - Re-benchmark: wake word P95, STT P95, end-to-end P95, idle CPU, idle RAM, startup time, intent classification P95, GPU utilization
    - All optimized metrics must be at least 10% below each target defined in `quality.md`
    - Append "Before/After Performance Table" to `AUDIT_REPORT_MASTER.md`
    - _Requirements: 4.11_

  - [ ]* 5.20 Run final enforcement gate after all Phase 4 optimizations
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - _Requirements: 4.12, 10.7, 10.8_

- [~] 6. Checkpoint — Phases 3 and 4 complete
  - Ensure all tests pass and all enforcement gates are green before proceeding to Phase 5. Ask the user if questions arise.

- [ ] 7. Phase 5 — Architectural Cleanup
  - [~] 7.1 Consolidate `llm/llm_runtime.py` and `llm/runtime.py` into canonical `llm/runtime.py`
    - Run `ast.parse()` on both files; compute union of public APIs; identify symbols unique to each
    - Write consolidated file to `llm/runtime.py` preserving all non-duplicate functionality
    - Update every caller across `Agent_Guru/` to import from `llm/runtime.py`
    - Delete `llm/llm_runtime.py`
    - _Requirements: 5.1_

  - [ ]* 7.2 Run enforcement gate after `llm/llm_runtime.py` consolidation
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - _Requirements: 5.11, 10.7, 10.8_

  - [~] 7.3 Consolidate `vision/engine.py` and `vision/vision_engine.py` into canonical `vision/engine.py`
    - Compute union of public APIs; write consolidated file to `vision/engine.py` preserving all non-duplicate public API surface
    - Update every caller across `Agent_Guru/` to import from `vision/engine.py`
    - Delete `vision/vision_engine.py`
    - _Requirements: 5.2_

  - [ ]* 7.4 Run enforcement gate after `vision/vision_engine.py` consolidation
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - _Requirements: 5.11, 10.7, 10.8_

  - [~] 7.5 Consolidate `agents/orchestrator.py` and `agents/orchestration_system.py` into canonical `agents/orchestrator.py`
    - Compute union of public APIs; write consolidated file to `agents/orchestrator.py`
    - Update every caller across `Agent_Guru/` to import from `agents/orchestrator.py`
    - Delete `agents/orchestration_system.py`
    - _Requirements: 5.3_

  - [ ]* 7.6 Run enforcement gate after `agents/orchestration_system.py` consolidation
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - _Requirements: 5.11, 10.7, 10.8_

  - [~] 7.7 Consolidate `agents/decomposer.py` and `agents/task_decomposer.py` into canonical `agents/task_decomposer.py`
    - Compute union of public APIs; write consolidated file to `agents/task_decomposer.py`
    - Update every caller across `Agent_Guru/` to import from `agents/task_decomposer.py`
    - Delete `agents/decomposer.py`
    - _Requirements: 5.4_

  - [ ]* 7.8 Run enforcement gate after `agents/decomposer.py` consolidation
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - _Requirements: 5.11, 10.7, 10.8_

  - [~] 7.9 Run `vulture Agent_Guru/ --min-confidence 80` and remove confirmed dead code
    - For each dead function/class: verify zero callers via AST import analysis, confirm no test imports the symbol, confirm not in `__all__` of any `__init__.py`
    - Remove only after all three safety checks pass
    - Run `pytest Agent_Guru/ -x --tb=short` after removing each individual item; stop if any test fails
    - _Requirements: 5.5, 5.11_

  - [~] 7.10 Remove all unused imports identified in Phase 3 from every file
    - Apply `ruff check Agent_Guru/ --select F401 --fix` to auto-remove unused imports
    - Verify `ruff check Agent_Guru/ --select F401,F811` reports zero violations after removal
    - _Requirements: 5.6, 5.10_

  - [~] 7.11 Evaluate and conditionally remove `memory/github_sync.py` and `llm/github_sync.py`
    - Confirm zero callers via `grep -r` across `Agent_Guru/`
    - Confirm zero integration test files import them via `grep -r` across `Agent_Guru/*/tests/`
    - If both conditions met: remove files and document removal rationale in `AUDIT_REPORT_MASTER.md`
    - If either condition fails: preserve files and document the live reference
    - _Requirements: 5.7_

  - [~] 7.12 Evaluate and conditionally remove files under `speech/examples/`
    - For each file: confirm no function or class is imported by any file outside `speech/examples/` and no function or class is called by any test file via static import analysis
    - Remove only files that pass both checks; document each removal
    - _Requirements: 5.8_

  - [~] 7.13 Identify and preserve future-critical infrastructure modules
    - Identify `reasoning/rust_ext/`, `deployment/installer_builder.py`, `self_improvement/` as future-critical
    - Document in `AUDIT_REPORT_MASTER.md` the specific future capability each enables and estimated activation timeline
    - _Requirements: 5.9_

  - [ ]* 7.14 Run final enforcement gate after all Phase 5 cleanup
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - Confirm `ruff check Agent_Guru/ --select F401,F811` reports zero violations
    - _Requirements: 5.10, 5.11, 10.7, 10.8_

- [~] 8. Checkpoint — Phases 4 and 5 complete
  - Ensure all tests pass and all enforcement gates are green before proceeding to Phase 6. Ask the user if questions arise.

- [ ] 9. Phase 6 — Integration Validation (implement missing components + run 12 checks)
  - [~] 9.1 Implement `memory/conversation_memory.py` — `ConversationMemory` with 50-turn LRU eviction
    - Implement `ConversationMemory(max_turns: int = 50)` using `collections.deque(maxlen=max_turns)`
    - Implement `async add_turn(user: str, assistant: str) -> None` and `async get_all_turns() -> list[ConversationTurn]`
    - Implement `turn_count` property
    - _Requirements: 6.7_

  - [~] 9.2 Implement `integration/orchestrator.py` — `IntegrationOrchestrator` wiring all 11 subsystems
    - Wire speech, vision, llm, platform, agents, memory, reasoning, security, policy, avatar, deployment subsystems
    - Implement `async startup() -> None` that initializes all subsystems without exception on a clean environment
    - Implement `async run_pipeline(event: WakeWordEvent) -> PipelineResult`
    - _Requirements: 6.1, 6.2_

  - [ ]* 9.3 Run enforcement gate after integration orchestrator implementation
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - _Requirements: 10.7, 10.8_

  - [~] 9.4 Implement all 12 integration validation checks in `audit/phases/phase6_integration.py`t/phases/phase6_integration.py` — `IntegrationTestHarness` with all 12 checks
    - **Check 1**: `orch.startup()` completes without exception on a clean environment
    - **Check 2**: Wake word event from `WakeWordManager` triggers `_on_wake_word` callback, captures audio via `_capture_command_with_vad`, passes `WakeWordEvent` to `run_pipeline()`
    - **Check 3**: `WhisperTranscriber.transcribe()` produces `TranscriptionResult` with non-empty `text`, `language`, `confidence` for audio with RMS > 0.005
    - **Check 4**: `reasoning/engine.py` produces `Intent` with non-null `type` and `confidence` > 0.5 for every `TranscriptionResult` with non-empty text
    - **Check 5**: `llm/runtime.py` produces non-empty string response for every LLM-routed `Intent` within 2s P95
    - **Check 6**: `speech/tts/tts_engine.py` produces non-empty WAV bytes for every non-empty LLM response and plays back through `sounddevice` without error
    - **Check 7**: `ConversationMemory` stores every completed turn and LRU eviction discards oldest turn at 50-turn limit
    - **Check 8**: Policy DENY result prevents action execution — action callable not invoked, pipeline returns DENY status
    - **Check 9**: `security/security_system.py` logs every action to audit trail; each entry includes SHA-256 hash of previous entry
    - **Check 10**: `avatar/avatar_system.py` updates `current_emotion` in response to voice emotion signals from `speech/emotion/emotion_detector.py` and face emotion signals from `vision/emotion/recognizer.py`
    - **Check 11**: Every Prometheus metric in `reasoning/config/metrics.py` is incremented at least once during a complete pipeline run
    - **Check 12**: Simulated LLM provider failure causes `llm/model_router/fallback_manager.py` to route to next provider within 500ms with no exception propagated and no error TTS to user
    - _Requirements: 6.1-6.12_

  - [~] 9.5 Run all 12 integration checks and record each result as PASS or FAIL
    - All 12 checks must be explicitly confirmed as PASS before writing the Integration Validation Report
    - Fix any failing check in the relevant `Agent_Guru/` source file before proceeding
    - _Requirements: 6.13_

  - [x] 9.6 Write property tests for integration validation in `audit/tests/test_phase6_properties.py`
    - **Property 15: Conversation Memory LRU Eviction** — for any sequence of `add_turn()` calls with `max_turns=N`, `turn_count` never exceeds N; after N+1 turns, oldest turn is evicted and remaining turns are in insertion order
    - **Property 16: Audit Trail Hash Chain Integrity** — for any sequence of `log_action()` calls, each entry at index i (i>0) has `prev_hash` equal to SHA-256 of entry at index i-1; first entry has genesis hash
    - **Property 17: Policy DENY Enforcement** — for any action where `PolicyEngine` returns DENY, the action callable is not invoked and pipeline result has DENY status, regardless of action type, user identity, or resource
    - **Property 18: STT Output Validity for Valid Audio** — for any audio array with RMS > 0.005, `transcribe()` returns `TranscriptionResult` with non-empty `text`, non-empty `language`, and `confidence` in (0.0, 1.0]
    - **Validates: Requirements 6.3, 6.7, 6.8, 6.9**

  - [ ]* 9.7 Run enforcement gate after all Phase 6 fixes
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - _Requirements: 10.7, 10.8_

  - [~] 9.8 Write Integration Validation Report to `AUDIT_REPORT_MASTER.md`
    - Append "Integration Validation Report" section with pass/fail table for all 12 checks
    - Only write after all 12 checks are confirmed PASS
    - _Requirements: 6.13_

- [ ] 10. Phase 7 — Code Quality (zero violations across all tools)
  - [~] 10.1 Run `ruff format --check Agent_Guru/` and fix all formatting violations
    - Apply `ruff format Agent_Guru/` to auto-format all files
    - Confirm `ruff format --check Agent_Guru/` reports zero violations
    - _Requirements: 7.1_

  - [~] 10.2 Run `ruff check Agent_Guru/` with all rules enabled and fix all violations
    - Apply `ruff check Agent_Guru/ --fix` for auto-fixable violations
    - Manually fix any remaining violations
    - Confirm `ruff check Agent_Guru/` reports zero violations
    - _Requirements: 7.2_

  - [~] 10.3 Run `mypy Agent_Guru/ --strict` and fix all type errors
    - Add missing type annotations, fix incorrect annotations, add type stubs where needed
    - Confirm `mypy Agent_Guru/ --strict` reports zero errors
    - _Requirements: 7.3_

  - [~] 10.4 Run `bandit -r Agent_Guru/ -ll` and fix all HIGH and MEDIUM security issues
    - Fix every HIGH and MEDIUM severity security issue in the original source file
    - Confirm `bandit -r Agent_Guru/ -ll` reports zero HIGH or MEDIUM issues
    - _Requirements: 7.4_

  - [~] 10.5 Add Google-style docstrings to every public function and class missing them
    - Every public function must have: one-line summary, `Args:` section (if parameters exist), `Returns:` section (if non-None return type)
    - Every module must have a module-level docstring stating purpose, subsystem, and primary public API
    - _Requirements: 7.5, 7.6_

  - [~] 10.6 Fix cyclomatic complexity violations (`ruff --select C901`) and function length violations (`ruff --select PLR0915`)
    - Refactor any function with cyclomatic complexity > 10 by extracting sub-functions
    - Refactor any function exceeding 50 statements by extracting helper functions
    - Refactor any class exceeding 300 non-blank, non-comment lines by splitting responsibilities
    - _Requirements: 7.7, 7.8, 7.9_

  - [~] 10.7 Enforce platform abstraction and layer architecture
    - Verify every platform-specific code path (Windows, macOS, Linux, Android, iOS) is isolated behind an `abc.ABC` subclass or `typing.Protocol`
    - Verify no platform-specific library (`pywin32`, `pyobjc`, `dbus-python`) is imported at module level without a `sys.platform` guard or `try/except ImportError`
    - Verify no module in `llm/`, `memory/`, `reasoning/` imports from `platform/` or `deployment/` directly
    - _Requirements: 7.10, 7.11_

  - [~] 10.8 Fix all async blocking violations and hardcoded secret violations
    - Replace every blocking call (`time.sleep`, `requests.*`, `urllib.request.urlopen`, `subprocess.run/call/check_output`, sync `open()` outside `run_in_executor`) inside `async def` functions with async equivalents
    - Move every API key, password, and private key to environment variables or OS keychain; remove all string literals containing secrets
    - _Requirements: 7.12, 7.13_

  - [x] 10.9 Write property tests for code quality checks in `audit/tests/test_phase7_properties.py`
    - **Property 19: Layer Violation Detection** — any import in `llm/`, `memory/`, or `reasoning/` referencing `platform/` or `deployment/` produces a finding; imports that do not cross this boundary produce no finding
    - **Validates: Requirements 7.11**

  - [ ]* 10.10 Run final enforcement gate after all Phase 7 fixes
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - All four tools must report zero violations
    - _Requirements: 7.1-7.4, 7.14, 10.7, 10.8_

  - [~] 10.11 Write Code Quality Report to `AUDIT_REPORT_MASTER.md`
    - Append "Code Quality Report" section with output of each tool and summary of all violations found and fixed
    - Only write after all four tools pass with zero violations
    - _Requirements: 7.14_

- [ ] 11. Phase 8 — Deployment and Production Readiness (10 checks)
  - [~] 11.1 Implement `audit/phases/phase8_deployment.py` — `DeploymentReadinessChecker` with all 10 checks
    - **Check 1**: Verify `main.py` starts cleanly on Windows 10/11 with Python 3.11, CUDA 11.8+, and Ollama running, reaching "Listening for wake words" within 10 seconds
    - **Check 2**: Verify `main.py` auto-restart loop flushes in-flight conversation memory and security audit log to disk before restarting on simulated subsystem crash
    - **Check 3**: Verify every log message uses `structlog` with JSON format including `timestamp`, `level`, `module`, `message` fields; confirm no raw `print()` calls in production code paths
    - **Check 4**: Verify Prometheus metrics endpoint exposes: `guru_pipeline_latency_seconds`, `guru_wake_word_detections_total`, `guru_stt_errors_total`, `guru_llm_requests_total`, `guru_llm_latency_seconds`, `guru_tts_latency_seconds`
    - **Check 5**: Verify Sentry captures every unhandled pipeline exception with full stack trace and user context when `SENTRY_DSN` is set; verify local exception logging when `SENTRY_DSN` is not set
    - **Check 6**: Verify `deployment/installer_builder.py` produces valid Windows MSI, macOS DMG, and Linux `.deb` package
    - **Check 7**: Verify Ollama adapter loads model from `OLLAMA_MODEL` env var (fallback to `llama3.2`), retries up to 3 times with exponential backoff if Ollama not running
    - **Check 8**: Verify voice stack (microphone capture, VAD, wake word, STT, TTS) initializes without error on standard audio device; missing audio device causes graceful degradation with clear error log, not crash
    - **Check 9**: Verify `deployment/rollback_manager.py` rolls back to previous version within 60 seconds, preserving all user data in `memory/` and `security/`
    - **Check 10**: Verify `k8s/` Kubernetes manifests are syntactically valid YAML with resource requests and limits set for every container
    - _Requirements: 8.1-8.10_

  - [~] 11.2 Fix all failing deployment checks in the relevant `Agent_Guru/` source files
    - Implement auto-restart loop in `main.py` if missing
    - Replace all `print()` calls in production code paths with `structlog` structured logging
    - Implement Prometheus metrics registration in `reasoning/config/metrics.py` if any metric is missing
    - Implement Sentry initialization with `SENTRY_DSN` guard in `main.py`
    - Implement Ollama adapter retry logic with exponential backoff in `llm/providers/ollama_adapter.py`
    - Implement graceful audio device degradation in voice stack initialization
    - _Requirements: 8.1-8.9_

  - [ ]* 11.3 Run enforcement gate after all Phase 8 fixes
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - _Requirements: 10.7, 10.8_

  - [~] 11.4 Write Deployment and Production Readiness Report to `AUDIT_REPORT_MASTER.md`
    - Append "Deployment and Production Readiness Report" section with pass/fail table for all 10 checks
    - Only write after all 10 checks pass
    - _Requirements: 8.11_

- [~] 12. Checkpoint — Phases 6, 7, and 8 complete
  - Ensure all tests pass and all enforcement gates are green before proceeding to Phase 9. Ask the user if questions arise.

- [ ] 13. Phase 9 — Final Master Audit Report
  - [~] 13.1 Implement `audit/phases/phase9_report.py` — `MasterReportFinalizer`
    - Consolidate all phase findings into `AUDIT_REPORT_MASTER.md` with exactly 9 top-level sections in order: Repository Intelligence, Competitive Analysis, Bug and Failure Report, Performance Optimization, Architectural Cleanup, Integration Validation, Code Quality, Deployment Readiness, Executive Summary
    - _Requirements: 9.1_

  - [~] 13.2 Write Executive Summary section
    - Include: total files scanned, total bugs found, total bugs fixed, total dead code removed (line count), total performance improvements (before/after table), total test coverage percentage, overall production readiness verdict (READY / NOT READY)
    - Include prioritized remediation backlog with: ID, phase, severity (CRITICAL/HIGH/MEDIUM/LOW), affected module, description, estimated effort (hours)
    - _Requirements: 9.2, 9.3_

  - [~] 13.3 Write Zero Tolerance Checklist and Competitive Readiness Matrix
    - Zero Tolerance Checklist: checkbox for each of: 0 compile errors, 0 mypy errors, 0 ruff violations, 0 bandit HIGH/MEDIUM issues, 0 broken imports, 0 circular imports, 0 unused imports, 0 duplicate implementations, 0 race conditions, 0 resource leaks, 0 blocking calls in async functions, 0 hardcoded secrets
    - Competitive Readiness Matrix: Agent Guru status (MET / NOT MET / EXCEEDS) for each of the 12 performance and accuracy targets in `quality.md`
    - _Requirements: 9.4, 9.5_

  - [~] 13.4 Write Test Coverage Summary and Next Steps sections
    - Run `pytest --cov=Agent_Guru --cov-report=term-missing` and include per-module coverage percentages; highlight modules below 80%
    - Write "Next Steps" section listing top 10 highest-priority actions for full production readiness, ordered by competitive impact
    - _Requirements: 9.7, 9.8_

  - [~] 13.5 Validate `AUDIT_REPORT_MASTER.md` for Markdown correctness
    - Verify no broken links, no unclosed code blocks, no malformed tables
    - Verify the document renders correctly
    - _Requirements: 9.6_

  - [x] 13.6 Write property tests for report generation in `audit/tests/test_phase9_properties.py`
    - **Property 20: Report Section Completeness** — for any `AuditReport` object passed to `MasterReportWriter.write()`, the resulting `AUDIT_REPORT_MASTER.md` contains exactly 9 top-level sections with the exact headings in the specified order
    - **Validates: Requirements 9.1, 9.2**

  - [ ]* 13.7 Run final enforcement gate
    - Run `pytest Agent_Guru/ -x --tb=short -q`, `ruff format --check Agent_Guru/`, `ruff check Agent_Guru/ --select ALL`, `mypy Agent_Guru/ --strict`
    - All four tools must report zero violations
    - _Requirements: 10.7, 10.8_

- [~] 14. Final Checkpoint — All phases complete
  - Ensure all tests pass, all enforcement gates are green, and `AUDIT_REPORT_MASTER.md` is complete and valid. Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP, but all 22 correctness properties should be validated before declaring production readiness
- Every task that modifies `Agent_Guru/` source code has an enforcement-gate sub-task (pytest + black + ruff + mypy) — the gate must pass before proceeding to the next task
- Performance optimization tasks (5.3, 5.19) include before/after benchmark sub-tasks — no optimization may be applied that degrades any metric
- Duplicate consolidation tasks (7.1, 7.3, 7.5, 7.7) include caller-update sub-tasks — all callers must be updated in the same batch as the consolidation
- Integration validation tasks (9.4-9.8) include property-based test sub-tasks for Properties 15-18
- The phase DAG must be respected: Phase 0 first; Phase 1 second; Phases 2 and 3 after Phase 1; Phases 4 and 5 after Phase 3; Phase 6 after Phases 4 and 5; Phase 7 after Phase 6; Phase 8 after Phase 7; Phase 9 after Phases 2 and 8
- No shadow files (`*_v2.py`, `*_fixed.py`, `*_optimized.py`) may be created at any point
- No placeholder, TODO comment, mock logic, or stub implementation may be left as a permanent fix
- All 22 correctness properties are covered: Properties 1-3 in task 2.6-2.7; Properties 4-5 in task 3.4; Properties 6-8 in task 4.8; Properties 9-10 in task 5.6; Property 11-14 in task 5.12; Property 15-18 in task 9.6; Property 19 in task 10.9; Property 20 in task 13.6; Property 21 in task 5.9; Property 22 in task 5.18

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "1.4", "1.5"] },
    { "id": 1, "tasks": ["1.6", "1.7", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4"] },
    { "id": 3, "tasks": ["2.5", "2.6", "2.7", "3.1"] },
    { "id": 4, "tasks": ["3.2", "4.1"] },
    { "id": 5, "tasks": ["3.3", "3.4", "4.2", "4.3"] },
    { "id": 6, "tasks": ["4.4"] },
    { "id": 7, "tasks": ["4.5"] },
    { "id": 8, "tasks": ["4.6", "4.7", "4.8", "5.1"] },
    { "id": 9, "tasks": ["5.2"] },
    { "id": 10, "tasks": ["5.3", "5.4", "5.5"] },
    { "id": 11, "tasks": ["5.6", "5.7", "5.8"] },
    { "id": 12, "tasks": ["5.9", "5.10", "5.11"] },
    { "id": 13, "tasks": ["5.12", "5.13", "5.14"] },
    { "id": 14, "tasks": ["5.15", "5.16", "5.17"] },
    { "id": 15, "tasks": ["5.18", "5.19", "5.20", "7.1"] },
    { "id": 16, "tasks": ["7.2", "7.3"] },
    { "id": 17, "tasks": ["7.4", "7.5"] },
    { "id": 18, "tasks": ["7.6", "7.7"] },
    { "id": 19, "tasks": ["7.8", "7.9"] },
    { "id": 20, "tasks": ["7.10", "7.11", "7.12"] },
    { "id": 21, "tasks": ["7.13", "7.14", "9.1"] },
    { "id": 22, "tasks": ["9.2"] },
    { "id": 23, "tasks": ["9.3", "9.4"] },
    { "id": 24, "tasks": ["9.5"] },
    { "id": 25, "tasks": ["9.6", "9.7", "9.8", "10.1"] },
    { "id": 26, "tasks": ["10.2", "10.3", "10.4"] },
    { "id": 27, "tasks": ["10.5", "10.6", "10.7"] },
    { "id": 28, "tasks": ["10.8"] },
    { "id": 29, "tasks": ["10.9", "10.10", "10.11", "11.1"] },
    { "id": 30, "tasks": ["11.2"] },
    { "id": 31, "tasks": ["11.3", "11.4", "13.1"] },
    { "id": 32, "tasks": ["13.2", "13.3"] },
    { "id": 33, "tasks": ["13.4", "13.5"] },
    { "id": 34, "tasks": ["13.6", "13.7"] }
  ]
}
```
