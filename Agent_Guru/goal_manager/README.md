# Goal Manager

Persistent autonomous goal management system for Agent_Guru.

## Overview

The Goal Manager enables persistent, self-managing goal execution across multiple sessions with:
- **Persistent Storage**: Goals survive system restarts
- **LLM-Powered Decomposition**: Automatic breakdown of high-level goals
- **Progress Tracking**: Real-time progress calculation and status propagation
- **Priority Management**: Intelligent goal prioritization
- **Dependency Resolution**: Cycle detection and execution ordering
- **Session Recovery**: Automatic resumption of interrupted goals
- **GitHub Integration**: Complete audit trail via commits
- **Error Resilience**: Retry logic and graceful degradation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Goal Manager                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Goal Manager API                          │ │
│  │  - Create, query, update, cancel goals                │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Goal Storage (SQLite + JSON)                 │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Goal Decomposer (LLM-powered)                │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Progress Tracker                             │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Priority Manager                             │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Goal Executor                                │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Dependency Resolver                          │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Session Manager                              │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Installation

Dependencies are already included in the main `requirements.txt`:
- SQLite3 (built-in with Python)
- GitPython (>=3.1.40)
- Pydantic (>=2.0.0)
- asyncio (built-in with Python)
- Hypothesis (>=6.92.0) for property-based testing

## Quick Start

```python
from Agent_Guru.goal_manager import GoalManager, Priority, GoalStatus

# Initialize Goal Manager
manager = GoalManager(
    storage_path="goals.db",
    git_repo_path=".",
    llm_runtime=llm,
    agent_orchestration=orchestrator,
    memory_system=memory,
    self_improvement_engine=engine
)

# Start the system
await manager.start()

# Create a goal
goal = await manager.create_goal(
    description="Implement user authentication system",
    priority=Priority.HIGH
)

# Query goals
pending_goals = await manager.query_goals(status=GoalStatus.PENDING)
high_priority = await manager.query_goals(priority=Priority.HIGH)

# Update priority
await manager.update_priority(goal.id, Priority.CRITICAL)

# Get summary
summary = await manager.get_summary()
print(f"Total goals: {summary['total_goals']}")
print(f"Progress: {summary['overall_progress']:.1%}")

# Cancel a goal
await manager.cancel_goal(goal.id)

# Shutdown (persists all state)
await manager.shutdown()
```

## Goal Lifecycle

```
[*] --> Pending: Create Goal
Pending --> Decomposing: Start Decomposition
Decomposing --> Pending: Decomposition Complete
Pending --> Ready: Dependencies Satisfied
Ready --> InProgress: Start Execution
InProgress --> InProgress: Execute Sub-Goals
InProgress --> Complete: All Sub-Goals Complete
InProgress --> Failed: Sub-Goal Failed
InProgress --> Cancelled: User Cancels
```

## Data Model

### Goal Structure

```python
{
    "id": "uuid-string",
    "description": "High-level goal description",
    "status": "pending|decomposing|ready|in_progress|complete|failed|cancelled|blocked",
    "priority": "critical|high|medium|low",
    "progress": 0.75,  # 0.0 to 1.0
    "created_at": "2024-01-15T10:30:00Z",
    "started_at": "2024-01-15T10:35:00Z",
    "completed_at": null,
    "parent_id": "parent-uuid-string",  # null for root goals
    "sub_goal_ids": ["sub-goal-1-uuid", "sub-goal-2-uuid"],
    "dependency_ids": ["dep-goal-1-uuid", "dep-goal-2-uuid"],
    "metadata": {
        "rationale": "Why this goal exists",
        "estimated_complexity": "low|medium|high",
        "generated_by": "user|llm_decomposer"
    },
    "error_message": null
}
```

## Testing

The Goal Manager uses comprehensive testing with both unit tests and property-based tests:

```bash
# Run all tests
pytest Agent_Guru/goal_manager/tests/

# Run unit tests only
pytest Agent_Guru/goal_manager/tests/ -m unit

# Run property-based tests only
pytest Agent_Guru/goal_manager/tests/ -m property

# Run with coverage
pytest Agent_Guru/goal_manager/tests/ --cov=Agent_Guru.goal_manager --cov-report=html
```

### Property-Based Testing

The Goal Manager validates 25 correctness properties using Hypothesis:

1. **Goal Creation Initialization**: Correct initial state
2. **Immediate Persistence**: Changes persisted before return
3. **Session Persistence Round-Trip**: State preserved across restarts
4. **Unique Identifier Invariant**: All IDs unique
5. **Hierarchical Tree Structure**: Valid tree structure
6. **Parent-Child Reference Consistency**: Bidirectional references
7. **Progress Calculation Correctness**: Average of sub-goals
8. **Completion Propagation**: Parent completes when all children complete
9. **Timestamp Chronological Order**: Timestamps in order
10. **Priority Selection Correctness**: Highest priority first
11. **Priority Validity**: Valid priority values
12. **Sequential Sub-Goal Execution**: One at a time
13. **Task Creation for Execution**: One task per leaf goal
14. **GitHub Commit on Completion**: Commit created
15. **Dependency Blocking**: Dependencies must be satisfied
16. **Circular Dependency Detection**: Cycles rejected
17. **Dependency Satisfaction**: Ready when dependencies complete
18. **Cancellation Propagation**: Cancels entire subtree
19. **Query Filtering Correctness**: Filters work correctly
20. **Hierarchical Retrieval Completeness**: Returns full hierarchy
21. **Serialization Round-Trip**: JSON serialization preserves data
22. **Schema Validation**: Invalid data rejected
23. **Retry with Exponential Backoff**: Retries with backoff
24. **Error Logging Completeness**: All errors logged
25. **Corruption Recovery**: Graceful handling of corruption

## Integration

The Goal Manager integrates with:

- **LLM Runtime**: Goal decomposition
- **Agent Orchestration**: Task execution
- **Memory System**: Context storage
- **Self-Improvement Engine**: Metrics reporting
- **GitHub**: Audit trail via commits

## Error Handling

The Goal Manager provides robust error handling:

```python
from Agent_Guru.goal_manager.exceptions import (
    GoalManagerError,
    StorageError,
    DecompositionError,
    ValidationError,
    ExecutionError,
)

try:
    goal = await manager.create_goal(
        description="Test goal",
        dependencies=["invalid-id"]
    )
except ValidationError as e:
    print(f"Validation failed: {e}")
except StorageError as e:
    print(f"Storage failed: {e}")
```

## Performance

- **Storage**: O(1) goal retrieval, O(log n) queries with indexes
- **Decomposition**: O(1) per goal (async, non-blocking)
- **Progress Tracking**: O(depth) for hierarchical updates
- **Dependency Resolution**: O(V + E) cycle detection with DFS
- **Execution**: O(n) sequential sub-goal execution

## Configuration

The Goal Manager can be configured via environment variables:

```bash
# Storage configuration
GOAL_MANAGER_DB_PATH=goals.db

# Git configuration
GOAL_MANAGER_GIT_REPO=.

# Retry configuration
GOAL_MANAGER_MAX_RETRIES=3
GOAL_MANAGER_BASE_DELAY=1.0

# LLM configuration
GOAL_MANAGER_LLM_MAX_TOKENS=2000
GOAL_MANAGER_LLM_TEMPERATURE=0.7
```

## Development

### Project Structure

```
Agent_Guru/goal_manager/
├── __init__.py              # Package initialization
├── models.py                # Data models (Goal, GoalStatus, Priority)
├── exceptions.py            # Exception hierarchy
├── goal_storage.py          # SQLite storage layer
├── goal_decomposer.py       # LLM-powered decomposition
├── progress_tracker.py      # Progress calculation
├── priority_manager.py      # Priority management
├── goal_executor.py         # Task execution
├── dependency_resolver.py   # Dependency management
├── session_manager.py       # Session persistence
├── goal_manager.py          # Main API
├── README.md                # This file
└── tests/                   # Test suite
    ├── __init__.py
    ├── conftest.py          # Pytest fixtures
    ├── test_models.py
    ├── test_storage.py
    ├── test_decomposer.py
    ├── test_progress_tracker.py
    ├── test_priority_manager.py
    ├── test_dependency_resolver.py
    ├── test_executor.py
    ├── test_session_manager.py
    ├── test_goal_manager.py
    ├── test_integration.py
    └── test_properties.py
```

### Code Quality

```bash
# Format code
black Agent_Guru/goal_manager/

# Lint code
ruff check Agent_Guru/goal_manager/ --fix

# Type check
mypy Agent_Guru/goal_manager/

# Run all quality checks
pre-commit run --all-files
```

## License

Part of Agent_Guru project.

## Support

For issues and questions, see the main Agent_Guru documentation.
