# Full Integration Resource Utilization Bugfix Design

## Overview

Agent Guru fails to run with all subsystems integrated and active simultaneously. The system
initializes each subsystem independently with no unified wiring, no shared GPU resource
coordination, and no concurrent startup — leaving the end-to-end pipeline broken and hardware
resources idle.

The fix introduces two new components in `Agent_Guru/integration/`:

1. `IntegrationOrchestrator` — wires all subsystems into a single unified pipeline, manages
   concurrent async startup, and drives the end-to-end voice command flow.
2. `GPUResourcePool` — coordinates GPU memory allocation across PyTorch, ONNX Runtime, and
   faster-whisper so all three coexist without contention, with CPU fallback when no GPU is
   available.

The fix is additive: no existing subsystem code is modified. All existing subsystem unit and
property-based tests continue to pass unchanged.

---

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug — the system is started but no
  `IntegrationOrchestrator` exists to wire subsystems together, coordinate GPU resources, or
  drive the end-to-end pipeline.
- **Property (P)**: The desired behavior when the system is started — all subsystems are wired,
  GPU resources are coordinated, subsystems start concurrently, and voice commands traverse the
  complete pipeline.
- **Preservation**: All existing per-subsystem behavior (personality routing, biometric auth,
  policy enforcement, sleep mode, onboarding) that must remain unchanged by the fix.
- **IntegrationOrchestrator**: New class in `Agent_Guru/integration/orchestrator.py` that owns
  the unified startup sequence and end-to-end pipeline execution.
- **GPUResourcePool**: New class in `Agent_Guru/integration/gpu_pool.py` that partitions GPU
  VRAM across PyTorch, ONNX Runtime, and faster-whisper and provides CPU fallback.
- **Pipeline**: The ordered sequence of stages a voice command traverses: wake word → STT →
  memory context → LLM reasoning → intent → policy check → action → TTS.
- **Concurrent startup**: Using `asyncio.gather()` to initialize all subsystems in parallel
  rather than sequentially, so startup time is bounded by the slowest subsystem, not their sum.

---

## Bug Details

### Bug Condition

The bug manifests when the Agent Guru application is started. No `IntegrationOrchestrator`
exists to wire subsystems together, so each subsystem initializes in isolation. There is no
shared GPU resource pool, no concurrent startup, and no end-to-end pipeline connecting wake
word detection through to TTS response.

**Formal Specification:**
```
FUNCTION isBugCondition(system_state)
  INPUT: system_state — the state of the Agent Guru process after startup
  OUTPUT: boolean

  RETURN (system_state.integration_orchestrator IS None
          OR NOT system_state.integration_orchestrator.is_wired)
         AND (system_state.gpu_resource_pool IS None
              OR NOT system_state.gpu_resource_pool.is_coordinating)
         AND NOT system_state.pipeline_active
END FUNCTION
```

### Examples

- **Startup with GPU**: System starts, each subsystem initializes independently. GPU is
  available but only the first subsystem to load claims VRAM; others fall back to CPU or
  crash with OOM. Expected: GPUResourcePool partitions VRAM across all three frameworks.
- **Voice command issued**: Wake word detected, but no pipeline routes the event to STT, LLM,
  or TTS. Expected: IntegrationOrchestrator drives the full 8-stage pipeline.
- **Concurrent face + voice event**: Face recognition and STT run sequentially because no
  parallel dispatch exists. Expected: Both pipelines run as concurrent asyncio tasks.
- **No GPU available**: System should fall back to CPU for all subsystems without crashing.
  Expected: GPUResourcePool detects no CUDA device and configures CPU-only mode.

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Wake word "Hey Guru" MUST continue to activate the Guru personality and route to the male
  voice TTS pipeline (Requirement 3.3).
- Wake word "Hey Maya" MUST continue to activate the Maya personality and route to the female
  voice TTS pipeline (Requirement 3.4).
- Biometric multi-factor authentication (face + voice) MUST continue to be enforced before
  privileged commands execute (Requirement 3.5).
- Policy engine denial MUST continue to block execution and return a voice response without
  bypassing the policy check (Requirement 3.6).
- Sleep mode MUST continue to consume <5% battery/hour on mobile and <15% CPU on desktop,
  with only wake word detection active (Requirement 3.7).
- Missing API key MUST continue to trigger the onboarding flow rather than silently failing
  (Requirement 3.8).
- All existing per-subsystem unit and property-based tests MUST continue to pass without
  modification (Requirement 3.2).

**Scope:**
All inputs that do NOT involve the integration layer (i.e., direct calls to individual
subsystem APIs) are completely unaffected by this fix. This includes:
- Direct calls to `SpeechEngine`, `VisionEngine`, `LLMRuntime`, etc.
- Existing subsystem configuration and initialization paths.
- Platform-specific controller behavior.

---

## Hypothesized Root Cause

Based on the bug description, the most likely issues are:

1. **Missing Integration Layer**: No `Agent_Guru/integration/` module exists. Each subsystem
   has its own coordinator (`engine.py`, `runtime.py`, `controller.py`) but nothing wires them
   together into a unified pipeline. This is the primary cause.

2. **No GPU Resource Coordination**: PyTorch, ONNX Runtime, and faster-whisper each manage
   their own GPU memory independently. Without a shared pool, they compete for VRAM, causing
   OOM errors or silent CPU fallback on individual subsystems.

3. **Sequential Subsystem Startup**: Without `asyncio.gather()`, subsystems start one after
   another. Startup time equals the sum of all initialization times rather than the maximum,
   and the system is not ready to respond until the last subsystem finishes.

4. **No Pipeline Dispatch**: No component listens for wake word events and dispatches them
   through the full STT → memory → LLM → intent → policy → action → TTS chain. Each subsystem
   waits for direct API calls that never come in the integrated context.

5. **No Parallel Vision/Speech Dispatch**: When a face recognition event and a voice command
   arrive simultaneously, there is no concurrent dispatch mechanism, so they serialize.

---

## Correctness Properties

Property 1: Bug Condition — End-to-End Pipeline Execution

_For any_ wake word detection event where `isBugCondition` holds (no orchestrator wired),
the fixed `IntegrationOrchestrator` SHALL route the event through all 8 pipeline stages
(wake word → STT → memory context retrieval → LLM reasoning → intent recognition → policy
check → action execution → TTS response) and return a completed `PipelineResult` with all
stage outputs populated.

**Validates: Requirements 2.1, 2.2**

Property 2: Bug Condition — Concurrent GPU Resource Allocation

_For any_ active processing state where GPU hardware is available and `isBugCondition` holds,
the fixed `GPUResourcePool` SHALL allocate GPU memory to speech (faster-whisper), vision
(ONNX Runtime / InsightFace), and LLM (PyTorch) subsystems simultaneously, achieving >80%
GPU utilization during active processing without OOM errors or silent CPU fallback on any
individual subsystem.

**Validates: Requirements 2.3, 2.4**

Property 3: Bug Condition — Concurrent Async Startup

_For any_ call to `IntegrationOrchestrator.startup()`, all subsystems (speech, vision, LLM,
platform, agents, memory, reasoning, deployment, security, policy, avatar) SHALL be
initialized concurrently via `asyncio.gather()`, such that total startup time is bounded by
the slowest single subsystem initialization time, not the sum of all initialization times.

**Validates: Requirements 2.5**

Property 4: Bug Condition — Parallel Vision and Speech Processing

_For any_ concurrent face recognition event and voice command event, the fixed orchestrator
SHALL dispatch both the vision pipeline and the speech pipeline as independent asyncio tasks
that run in parallel, completing both within their individual latency targets (<50ms face
recognition, <1s STT) rather than their sum.

**Validates: Requirements 2.6**

Property 5: Bug Condition — LLM Context Enrichment

_For any_ LLM inference call made through the pipeline, the fixed orchestrator SHALL supply
a context object containing both `memory_context` (retrieved from the memory system) and
`reasoning_output` (from the reasoning engine) as non-None values in the same inference call.

**Validates: Requirements 2.7**

Property 6: Preservation — CPU Fallback

_For any_ startup where no CUDA device is available (`torch.cuda.is_available()` returns
False), the fixed `GPUResourcePool` SHALL configure all subsystems for CPU-only processing
and the `IntegrationOrchestrator` SHALL complete startup and pipeline execution without
raising any exception related to GPU unavailability.

**Validates: Requirements 3.1**

Property 7: Preservation — Personality and Policy Routing

_For any_ input that is NOT the integration bug condition (i.e., direct subsystem calls,
personality routing, policy checks, biometric auth), the fixed code SHALL produce exactly
the same behavior as the original code, preserving wake word personality routing, policy
enforcement, biometric MFA, sleep mode power consumption, and onboarding flow.

**Validates: Requirements 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**

---

## Fix Implementation

### Changes Required

No existing files are modified. All changes are additive, contained in the new
`Agent_Guru/integration/` module.

**New File**: `Agent_Guru/integration/__init__.py`
- Exports `IntegrationOrchestrator` and `GPUResourcePool`.

**New File**: `Agent_Guru/integration/gpu_pool.py`

**Class**: `GPUResourcePool`

**Specific Changes**:
1. **GPU Detection**: On construction, call `torch.cuda.is_available()` and
   `torch.cuda.get_device_properties(0)` to determine total VRAM. Set `device = "cuda"` or
   `device = "cpu"` accordingly.
2. **Memory Partitioning**: Divide available VRAM into three named allocations:
   - `whisper_budget`: 30% of VRAM for faster-whisper (STT)
   - `onnx_budget`: 30% of VRAM for ONNX Runtime (vision/InsightFace)
   - `torch_budget`: 40% of VRAM for PyTorch (LLM inference)
3. **Allocation API**: Expose `allocate(subsystem: str) -> DeviceConfig` returning the
   device string and memory limit for each subsystem.
4. **CPU Fallback**: When `device == "cpu"`, `allocate()` returns CPU device config for all
   subsystems without error.
5. **Utilization Monitoring**: Expose `get_utilization() -> float` using
   `torch.cuda.memory_allocated() / torch.cuda.get_device_properties(0).total_memory`.

**New File**: `Agent_Guru/integration/orchestrator.py`

**Class**: `IntegrationOrchestrator`

**Specific Changes**:
1. **Subsystem Wiring**: Constructor accepts all subsystem coordinator instances
   (`SpeechEngine`, `VisionEngine`, `LLMRuntime`, `PlatformController`, `AgentOrchestrator`,
   memory system, reasoning engine, `SecurityModule`, `PolicyEngine`, avatar system,
   deployment system) and stores references. Sets `is_wired = True`.
2. **Concurrent Startup**: `async def startup()` calls `asyncio.gather()` with all subsystem
   `initialize()` coroutines. Does NOT use sequential `await` calls.
3. **GPU Resource Distribution**: During startup, calls `GPUResourcePool.allocate()` for each
   GPU-using subsystem and passes the resulting `DeviceConfig` to that subsystem's initializer.
4. **Pipeline Execution**: `async def run_pipeline(wake_event: WakeWordEvent) -> PipelineResult`
   executes the 8-stage pipeline in order:
   - Stage 1: STT via `SpeechEngine.transcribe(wake_event.audio)`
   - Stage 2: Memory context via `memory.retrieve(transcript)`
   - Stage 3: Reasoning via `reasoning.analyze(transcript, memory_context)`
   - Stage 4: LLM inference via `LLMRuntime.infer(transcript, memory_context, reasoning_output)`
   - Stage 5: Intent recognition from LLM response
   - Stage 6: Policy check via `PolicyEngine.evaluate(intent)`
   - Stage 7: Action execution via `AgentOrchestrator.execute(intent)` (only if policy allows)
   - Stage 8: TTS via `SpeechEngine.synthesize(response, personality)`
5. **Parallel Vision/Speech Dispatch**: `async def handle_concurrent_event(vision_event, audio_event)`
   uses `asyncio.gather(vision_pipeline(vision_event), run_pipeline(audio_event))`.
6. **Wake Word Routing**: Preserves personality routing — "Hey Guru" sets
   `personality = Personality.GURU`, "Hey Maya" sets `personality = Personality.MAYA`.

**New File**: `Agent_Guru/integration/tests/test_orchestrator.py`
- Unit, property-based, and integration tests (see Testing Strategy).

**New File**: `Agent_Guru/integration/tests/test_gpu_pool.py`
- Unit and property-based tests for `GPUResourcePool`.

---

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that
demonstrate the bug on unfixed code (no `IntegrationOrchestrator` exists), then verify the
fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix.
Confirm or refute the root cause analysis.

**Test Plan**: Write tests that attempt to run the end-to-end pipeline without an
`IntegrationOrchestrator`. Assert that pipeline stages are not connected, GPU resources are
not coordinated, and subsystems start sequentially. Run these tests on the UNFIXED codebase
to observe failures.

**Test Cases**:
1. **No Pipeline Test**: Attempt to route a wake word event through all 8 stages without an
   orchestrator — assert that no unified dispatch mechanism exists (will fail on unfixed code).
2. **GPU Contention Test**: Initialize PyTorch, ONNX Runtime, and faster-whisper independently
   with no memory budget — assert that total allocated VRAM exceeds available VRAM or that
   one subsystem silently falls back to CPU (will fail on unfixed code).
3. **Sequential Startup Test**: Time the startup of all subsystems sequentially — assert that
   startup time equals the sum of individual times, confirming no concurrency (will fail on
   unfixed code).
4. **Missing Context Test**: Make an LLM inference call without memory/reasoning context —
   assert that `memory_context` and `reasoning_output` are absent from the inference call
   (will fail on unfixed code).

**Expected Counterexamples**:
- Wake word events are not routed to any pipeline stage.
- GPU memory is over-subscribed or one subsystem silently uses CPU.
- Startup time is the sum of all subsystem init times.
- LLM inference calls lack memory and reasoning context.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed orchestrator
produces the expected behavior.

**Pseudocode:**
```
FOR ALL wake_event WHERE isBugCondition(system_state_before_fix) DO
  orchestrator = IntegrationOrchestrator(all_subsystems)
  await orchestrator.startup()
  result = await orchestrator.run_pipeline(wake_event)
  ASSERT result.stages_completed == 8
  ASSERT result.tts_response IS NOT None
  ASSERT gpu_pool.get_utilization() > 0.80  (if GPU available)
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold (direct subsystem
calls, personality routing, policy checks), the fixed code produces the same result as the
original code.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(system_state) DO
  ASSERT original_subsystem_behavior(input) == fixed_subsystem_behavior(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain.
- It catches edge cases that manual unit tests might miss.
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs.

**Test Plan**: Observe behavior of existing subsystem APIs on unfixed code, then write
property-based tests capturing that behavior and verify they still pass after the fix.

**Test Cases**:
1. **Personality Routing Preservation**: For any wake word string in {"Hey Guru", "Hey Maya"},
   verify personality assignment is unchanged after fix.
2. **Policy Denial Preservation**: For any policy-denied intent, verify execution is blocked
   and a voice response is returned, unchanged after fix.
3. **CPU Fallback Preservation**: For any startup with no GPU, verify all subsystems
   initialize and process without error, unchanged after fix.
4. **Biometric Auth Preservation**: For any privileged command, verify MFA is enforced,
   unchanged after fix.

### Unit Tests

- Test `GPUResourcePool` construction with GPU available (mock `torch.cuda`).
- Test `GPUResourcePool` construction with no GPU (CPU fallback path).
- Test `GPUResourcePool.allocate()` returns correct memory budgets for each subsystem.
- Test `GPUResourcePool.get_utilization()` returns value in [0.0, 1.0].
- Test `IntegrationOrchestrator` constructor sets `is_wired = True`.
- Test `IntegrationOrchestrator.startup()` calls `asyncio.gather()` (not sequential awaits).
- Test `IntegrationOrchestrator.run_pipeline()` invokes all 8 stages in order.
- Test `IntegrationOrchestrator.handle_concurrent_event()` dispatches vision and speech as
  parallel tasks.
- Test pipeline stage 6 (policy check) blocks execution when policy denies.
- Test wake word routing assigns correct personality for "Hey Guru" and "Hey Maya".

### Property-Based Tests

- **Property 1 (Fix)**: For any `WakeWordEvent` with valid audio, `run_pipeline()` always
  returns a `PipelineResult` with all 8 stages completed and a non-None TTS response.
- **Property 2 (Fix)**: For any set of subsystem mock configurations, `startup()` completes
  in time ≤ max(individual_init_times) + epsilon (concurrency guarantee).
- **Property 3 (Fix)**: For any GPU VRAM size > 0, `GPUResourcePool` allocates budgets that
  sum to ≤ total VRAM (no over-subscription).
- **Property 4 (Fix)**: For any LLM inference call through the pipeline, the context always
  contains both `memory_context` and `reasoning_output` as non-None values.
- **Property 5 (Preservation)**: For any wake word string, personality routing produces the
  same result before and after the fix.
- **Property 6 (Preservation)**: For any startup with `torch.cuda.is_available() == False`,
  `IntegrationOrchestrator.startup()` completes without raising any exception.

### Integration Tests

- Test full pipeline from mock wake word event through all 8 stages with all subsystems
  mocked, verifying stage outputs are passed correctly between stages.
- Test concurrent vision + speech dispatch: assert both complete within their individual
  latency targets when run in parallel.
- Test GPU resource pool integration with mock PyTorch/ONNX/faster-whisper subsystems:
  verify each receives its allocated device config during startup.
- Test sleep mode: verify only wake word detection is active (all other subsystems idle)
  after `orchestrator.sleep()` is called.
- Test onboarding trigger: verify startup with missing API key routes to onboarding flow
  without crashing.
