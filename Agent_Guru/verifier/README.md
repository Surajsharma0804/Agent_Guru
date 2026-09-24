# Verifier System

Multi-layered verification for Agent_Guru that detects hallucinations, validates outputs,
prevents infinite loops, and provides self-correction feedback. Integrates with LLM Runtime,
Agent Orchestration, and Memory System.

## Architecture

```
VerifierSystem
├── HallucinationDetector          - 4-technique hallucination detection
├── OutputValidator                - JSON/XML/Markdown schema validation
├── ToolOutputChecker              - Tool result safety verification
├── LoopDetector                   - State-hash-based loop detection
├── ConfidenceScorer               - Weighted confidence aggregation
├── VerificationStrategySelector   - Task-type-aware strategy selection
├── SelfCorrectionFeedbackGenerator - Actionable failure feedback
├── VerificationResultStorage      - SQLite audit trail
├── AccuracyTracker                - FP/FN rate monitoring
└── TestingModeManager             - Injection & detection rate testing
```

## Integration Points

| Component | Integration Class | Purpose |
|-----------|------------------|---------|
| LLM Runtime | `LLMRuntimeIntegration` | Intercept responses before forwarding |
| Agent Orchestration | `AgentOrchestrationIntegration` | Validate task outputs, retry/escalate |
| Memory System | `MemorySystemIntegration` | Block hallucinated storage, attach confidence |
| Self-Improvement | `SelfImprovementIntegration` | Report failures, extract patterns |

## Quick Start

```python
from Agent_Guru.verifier import VerifierSystem, VerificationConfig

verifier = VerifierSystem(config=VerificationConfig(
    min_confidence_threshold=0.7,
    loop_detection_threshold=3,
    max_latency_ms=200.0,
))

# Verify LLM response
result = await verifier.verify_llm_response(
    response="The capital of France is Paris.",
    context={"topic": "geography"},
    session_id="session_001",
)
if result.failed:
    print(result.feedback.suggestions)

# Verify task output
result = await verifier.verify_task_output(
    task_id="task_001",
    output={"status": "done", "items": [1, 2, 3]},
    expected_schema={"type": "object", "required": ["status"]},
)

# Verify before memory storage
result = await verifier.verify_before_storage(
    content="User prefers dark mode.",
    metadata={"source": "conversation"},
)
if result.failed:
    print("Blocked hallucinated content from storage")
```

## Integration Usage

```python
from Agent_Guru.verifier.integrations import (
    LLMRuntimeIntegration,
    AgentOrchestrationIntegration,
    MemorySystemIntegration,
    SelfImprovementIntegration,
)

# LLM Runtime - intercept and verify responses
llm_integration = LLMRuntimeIntegration(verifier)
should_forward, result = await llm_integration.intercept_response(
    response, context=context, session_id=session_id
)

# Agent Orchestration - validate task outputs with retry
agent_integration = AgentOrchestrationIntegration(verifier, max_retries=3)
is_valid, result, should_escalate = await agent_integration.validate_task_output(
    task_id, output, expected_schema=schema
)

# Memory System - prevent hallucinated storage
memory_integration = MemorySystemIntegration(verifier, reverification_age_days=30)
should_store, result = await memory_integration.verify_before_storage(
    content, content_id="mem_001"
)
meta = memory_integration.get_confidence_metadata("mem_001")
needs_refresh = memory_integration.needs_reverification("mem_001")

# Self-Improvement - get failure reports
si_integration = SelfImprovementIntegration(verifier)
report = si_integration.get_failure_report()
history = si_integration.get_historical_data(limit=100)
```

## Configuration

```python
from Agent_Guru.verifier.models import VerificationConfig

config = VerificationConfig(
    # Confidence thresholds
    min_confidence_threshold=0.7,        # Below this → UNCERTAIN
    hallucination_confidence_threshold=0.6,

    # Strategy enablement
    enable_hallucination_detection=True,
    enable_output_validation=True,
    enable_tool_output_checking=True,
    enable_loop_detection=True,
    enable_confidence_scoring=True,

    # Performance
    max_latency_ms=200.0,               # Timeout for verification (ms)

    # Loop detection
    loop_detection_threshold=3,          # Repetitions before loop detected

    # Accuracy targets
    max_false_positive_rate=0.05,        # <5% FP rate
    max_false_negative_rate=0.02,        # <2% FN rate

    # Caching
    enable_caching=True,
    cache_ttl_seconds=60.0,
)

# Runtime updates
verifier.update_config(min_confidence_threshold=0.8)
```

## Testing Mode

```python
from Agent_Guru.verifier.testing_mode import TestingModeManager

manager = TestingModeManager()
manager.enable()

# Inject hallucination for detection testing
injected = manager.inject_hallucination("The answer is 42.")
result = await verifier.verify_llm_response(injected)
manager.record_detection("hallucination", detected=result.hallucination.detected)

# Inject malformed output for validation testing
malformed = manager.inject_malformed_output("json")
result = await verifier.verify_llm_response(malformed, expected_format="json")

# Get detection rates
print(manager.get_detection_rate("hallucination"))   # e.g. 0.95
print(manager.get_diagnostics())

manager.disable()
```

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Latency (p95) | <200ms | Parallel strategy execution |
| False Positive Rate | <5% | Configurable threshold |
| False Negative Rate | <2% | Configurable threshold |
| Cache hit | O(1) | LRU cache, 256 entries |
| Concurrent requests | Unlimited | asyncio.gather |

## Error Handling & Graceful Degradation

- Individual strategy failures are caught and logged - verification continues with remaining strategies
- Storage failures are non-fatal - result is returned even if audit trail write fails
- Timeout (configurable via `max_latency_ms`) returns a degraded result rather than raising
- None/invalid inputs are normalized to empty strings before processing

## Monitoring

```python
# Get accuracy metrics
metrics = verifier.get_accuracy_metrics()
# {
#   "total": 1000,
#   "false_positive_rate": 0.02,
#   "false_negative_rate": 0.01,
#   "accuracy": 0.97,
#   "p95_latency_ms": 45.2,
# }

# Get failure reports for Self-Improvement Engine
reports = verifier.get_failure_reports()
```

## Module Reference

| Module | Class | Purpose |
|--------|-------|---------|
| `models.py` | `VerificationResult`, `VerificationConfig`, ... | All Pydantic v2 data models |
| `verifier_system.py` | `VerifierSystem` | Core async API |
| `hallucination_detector.py` | `HallucinationDetector` | 4-technique detection |
| `output_validator.py` | `OutputValidator` | Schema/format validation |
| `tool_output_checker.py` | `ToolOutputChecker` | Tool result safety |
| `loop_detector.py` | `LoopDetector` | State-hash loop detection |
| `confidence_scorer.py` | `ConfidenceScorer` | Weighted score aggregation |
| `strategy_selector.py` | `VerificationStrategySelector` | Task-type strategy selection |
| `feedback_generator.py` | `SelfCorrectionFeedbackGenerator` | Actionable feedback |
| `result_storage.py` | `VerificationResultStorage` | SQLite audit trail |
| `accuracy_tracker.py` | `AccuracyTracker` | FP/FN monitoring |
| `testing_mode.py` | `TestingModeManager` | Injection & detection testing |
| `integrations.py` | `LLMRuntimeIntegration`, ... | Integration hooks |
