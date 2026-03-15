# Agent Orchestration System

Multi-agent coordination system for Agent Guru. Enables emergent behavior through dynamic agent creation, specialization, merging, splitting, and evolution based on performance patterns.

## Architecture

```
OrchestrationSystem          ← Main API entry point
├── TaskDecomposer           ← Breaks complex tasks into sub-tasks
├── TaskAssigner             ← Assigns tasks to optimal agents
├── DelegationManager        ← Agent-to-agent delegation with cycle prevention
├── LoopDetector             ← Detects action/delegation loops
├── AgentLifecycleManager    ← Create/retire agents
├── AgentMerger              ← Merge agents with overlapping specializations
├── AgentSplitter            ← Split agents with divergent specializations
├── DuplicateDetector        ← Prevent duplicate agent creation
├── SpecializationTracker    ← Track per-agent task-type scores
├── PerformanceTracker       ← Sliding-window performance metrics
├── PopulationManager        ← Maintain optimal population size
├── ConvergenceAnalyzer      ← Detect specialization convergence
├── AdversarialHandler       ← Quarantine/terminate bad actors
├── AssignmentOptimizer      ← Verify assignment quality vs baseline
├── GitHubSyncEngine         ← Sync evolution events to GitHub
├── CircuitBreaker           ← Prevent cascading failures
├── AgentStorage             ← SQLite persistence layer
└── Integrations             ← Goal Manager, Model Router, Verifier, Memory, Self-Improvement
```

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from Agent_Guru.agents.agent_storage import AgentStorage
from Agent_Guru.agents.agent_lifecycle import AgentLifecycleManager
from Agent_Guru.agents.task_decomposer import TaskDecomposer, Task
from Agent_Guru.agents.task_assigner import TaskAssigner
from Agent_Guru.agents.performance_tracker import PerformanceTracker
from Agent_Guru.agents.orchestration_system import OrchestrationSystem

# Initialize storage
storage = AgentStorage("data/agents.db")

# Wire components
lifecycle = AgentLifecycleManager(storage)
decomposer = TaskDecomposer()
assigner = TaskAssigner(storage, None, lifecycle)
tracker = PerformanceTracker(storage)

# Create orchestration system
system = OrchestrationSystem(storage, decomposer, assigner, tracker)

# Execute a task
task = Task(
    id="task-1",
    description="Implement and test the payment module",
    task_type="implementation",
    requirements={"module": "payment"},
    success_criteria=["tests pass", "coverage > 80%"],
    priority=1,
    dependencies=[],
)
result = await system.receive_task(task)
print(f"Success: {result.success}")
```

## Configuration

See `config_template.yaml` for all configuration options.

Key parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `similarity_threshold` | 0.85 | Cosine similarity above which agents are merged |
| `divergence_threshold` | 0.5 | Divergence above which agents are split |
| `max_delegation_depth` | 3 | Maximum delegation chain length |
| `max_agents` | 50 | Population cap before aggressive merging |
| `min_agents` | 5 | Population floor before conservative retirement |
| `window_size` | 100 | Sliding window for performance metrics |
| `circuit_breaker.failure_threshold` | 5 | Failures before opening circuit |
| `circuit_breaker.recovery_timeout_seconds` | 30.0 | Time before attempting recovery |

## API Reference

### OrchestrationSystem

```python
result = await system.receive_task(task)  # Main entry point
```

### AgentLifecycleManager

```python
agent = await lifecycle.create_agent(task_requirements, initial_capabilities)
await lifecycle.retire_agent(agent_id, reason)
agents = await lifecycle.get_active_agents()
```

### TaskAssigner

```python
agent_id = await assigner.assign_task(task)
await assigner.task_completed(agent_id)
workload = assigner.get_workload(agent_id)
```

### AgentMerger

```python
candidates = await merger.detect_merge_candidates()  # [(id1, id2, similarity)]
merged = await merger.merge_agents(agent_id_1, agent_id_2)
```

### CircuitBreaker

```python
cb = CircuitBreaker("model_router", CircuitBreakerConfig(failure_threshold=5))
result = await cb.call(my_async_func, arg1, arg2)  # Raises CircuitOpenError if open
```

## Testing

```bash
# Run all agent tests
pytest Agent_Guru/agents/tests/ -v

# Run property-based tests only
pytest Agent_Guru/agents/tests/ -m property -v

# Run benchmarks
pytest Agent_Guru/agents/tests/test_benchmarks.py -v --benchmark-only
```

## Performance Targets

| Operation | Target |
|-----------|--------|
| Agent creation | < 10ms |
| Task assignment (1000 agents) | < 50ms |
| Merge detection (100 agents) | < 100ms |
| Delegation cycle check | < 10ms |
| DB read (single agent) | < 5ms |
