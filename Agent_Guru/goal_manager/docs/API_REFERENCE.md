# Goal Manager API Reference

## Overview

This document provides complete API reference documentation for all public classes and methods in the Goal Manager system. The Goal Manager enables persistent, self-managing goal execution across multiple sessions with automatic decomposition, progress tracking, and dependency management.

**Version**: 1.0.0  
**Author**: Agent Guru Team  
**Date**: 2024-01-15

## Table of Contents

1. [Core Classes](#core-classes)
   - [GoalManager](#goalmanager)
   - [Goal](#goal)
   - [GoalStatus](#goalstatus)
   - [Priority](#priority)
2. [Storage Layer](#storage-layer)
   - [GoalStorage](#goalstorage)
3. [Decomposition](#decomposition)
   - [GoalDecomposer](#goaldecomposer)
4. [Progress Tracking](#progress-tracking)
   - [ProgressTracker](#progresstracker)
5. [Priority Management](#priority-management)
   - [PriorityManager](#prioritymanager)
6. [Dependency Management](#dependency-management)
   - [DependencyResolver](#dependencyresolver)
7. [Execution](#execution)
   - [GoalExecutor](#goalexecutor)
8. [Session Management](#session-management)
   - [SessionManager](#sessionmanager)
9. [Exceptions](#exceptions)
10. [Utilities](#utilities)

---

## Core Classes

### GoalManager

**Module**: `Agent_Guru.goal_manager.goal_manager`

Main interface for goal lifecycle management. Coordinates all components and provides unified API for creating, querying, updating, and managing goals.

#### Constructor

```python
def __init__(
    self,
    storage_path: str,
    git_repo_path: str,
    llm_runtime: Any,
    agent_orchestration: Any,
    memory_system: Any,
    self_improvement_engine: Any
)
```

Initialize Goal Manager with all dependencies.


**Parameters**:
- `storage_path` (str): Path to SQLite database file (e.g., "goals.db")
- `git_repo_path` (str): Path to Git repository for audit trail (e.g., ".")
- `llm_runtime` (Any): LLM Runtime instance with `generate()` method
- `agent_orchestration` (Any): Agent Orchestration instance with `create_task()` method
- `memory_system` (Any): Memory System instance with `query_similar()` method
- `self_improvement_engine` (Any): Self-Improvement Engine with `record_task_execution()` method

**Raises**:
- `StorageError`: If database initialization fails
- `ValueError`: If paths are invalid

**Example**:
```python
from Agent_Guru.goal_manager import GoalManager, Priority

manager = GoalManager(
    storage_path="goals.db",
    git_repo_path=".",
    llm_runtime=llm_runtime,
    agent_orchestration=orchestrator,
    memory_system=memory,
    self_improvement_engine=engine
)
```

#### Methods

##### create_goal

```python
async def create_goal(
    self,
    description: str,
    priority: Priority = Priority.MEDIUM,
    dependencies: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Goal
```

Create a new goal with unique ID and trigger async decomposition.

**Parameters**:
- `description` (str): High-level goal description (min 1 character)
- `priority` (Priority, optional): Goal priority (default: MEDIUM)
- `dependencies` (List[str], optional): List of dependency goal IDs
- `metadata` (Dict[str, Any], optional): Additional metadata

**Returns**:
- `Goal`: Created goal with unique ID and initial state

**Raises**:
- `ValidationError`: If dependencies contain cycles
- `StorageError`: If persistence fails
- `ValueError`: If description is empty

**Example**:
```python
goal = await manager.create_goal(
    description="Implement user authentication",
    priority=Priority.HIGH,
    dependencies=["goal-id-1"],
    metadata={"team": "backend"}
)
print(f"Created goal {goal.id}")
```


##### get_goal

```python
async def get_goal(self, goal_id: str) -> Optional[Goal]
```

Get goal by ID with complete hierarchy.

**Parameters**:
- `goal_id` (str): Goal identifier

**Returns**:
- `Optional[Goal]`: Goal object if found, None otherwise

**Example**:
```python
goal = await manager.get_goal("goal-id-123")
if goal:
    print(f"Goal: {goal.description}")
```

##### query_goals

```python
async def query_goals(
    self,
    status: Optional[GoalStatus] = None,
    priority: Optional[Priority] = None
) -> List[Goal]
```

Query goals with optional filters.

**Parameters**:
- `status` (GoalStatus, optional): Filter by status
- `priority` (Priority, optional): Filter by priority

**Returns**:
- `List[Goal]`: List of goals matching filters

**Example**:
```python
pending = await manager.query_goals(status=GoalStatus.PENDING)
high_priority = await manager.query_goals(priority=Priority.HIGH)
```

##### update_priority

```python
async def update_priority(self, goal_id: str, priority: Priority) -> None
```

Update goal priority with immediate persistence.

**Parameters**:
- `goal_id` (str): Goal identifier
- `priority` (Priority): New priority level

**Raises**:
- `ValueError`: If goal not found
- `StorageError`: If persistence fails

**Example**:
```python
await manager.update_priority("goal-id-123", Priority.CRITICAL)
```

##### cancel_goal

```python
async def cancel_goal(self, goal_id: str) -> None
```

Cancel goal and all sub-goals recursively. Stops execution if in progress.

**Parameters**:
- `goal_id` (str): Goal identifier

**Raises**:
- `ValueError`: If goal not found
- `StorageError`: If persistence fails

**Example**:
```python
await manager.cancel_goal("goal-id-123")
```


##### modify_goal

```python
async def modify_goal(
    self,
    goal_id: str,
    description: Optional[str] = None,
    notes: Optional[str] = None
) -> Goal
```

Modify goal description or add notes. Description can only be modified for PENDING goals.

**Parameters**:
- `goal_id` (str): Goal identifier
- `description` (str, optional): New description (only for PENDING goals)
- `notes` (str, optional): Notes to add to metadata (allowed for any status)

**Returns**:
- `Goal`: Modified goal

**Raises**:
- `ValueError`: If goal not found
- `ValidationError`: If trying to modify COMPLETE goal description
- `StorageError`: If persistence fails

**Example**:
```python
# Modify PENDING goal description
goal = await manager.modify_goal("goal-123", description="New description")

# Add notes to COMPLETE goal
goal = await manager.modify_goal("goal-456", notes="Additional context")
```

##### re_decompose_goal

```python
async def re_decompose_goal(self, goal_id: str) -> None
```

Re-decompose goal after description change. Clears existing sub-goals and triggers new decomposition. Only allowed for PENDING goals.

**Parameters**:
- `goal_id` (str): Goal identifier

**Raises**:
- `ValueError`: If goal not found
- `ValidationError`: If goal is not PENDING
- `StorageError`: If persistence fails
- `DecompositionError`: If decomposition fails

**Example**:
```python
# Modify goal description
await manager.modify_goal("goal-123", description="New description")

# Re-decompose with new description
await manager.re_decompose_goal("goal-123")
```

##### get_summary

```python
async def get_summary(self) -> Dict[str, Any]
```

Get summary of all goals including counts and overall progress.

**Returns**:
- `Dict[str, Any]`: Dictionary with keys:
  - `total_goals` (int): Total number of goals
  - `completed` (int): Number of completed goals
  - `in_progress` (int): Number of in-progress goals
  - `failed` (int): Number of failed goals
  - `overall_progress` (float): Overall progress (0.0 to 1.0)

**Example**:
```python
summary = await manager.get_summary()
print(f"Progress: {summary['overall_progress']:.1%}")
print(f"Completed: {summary['completed']}/{summary['total_goals']}")
```


##### start

```python
async def start(self) -> None
```

Start Goal Manager by loading goals from storage and resuming interrupted goals.

**Raises**:
- `StorageError`: If loading fails

**Example**:
```python
await manager.start()
print("Goal Manager started")
```

##### shutdown

```python
async def shutdown(self) -> None
```

Shutdown Goal Manager and persist all state. With immediate persistence strategy, this is a no-op but kept for API consistency.

**Example**:
```python
await manager.shutdown()
print("Goal Manager shutdown complete")
```

---

### Goal

**Module**: `Agent_Guru.goal_manager.models`

Data model representing a goal with hierarchical structure. Uses Pydantic for validation.

#### Attributes

- `id` (str): Unique identifier (UUID)
- `description` (str): High-level goal description
- `status` (GoalStatus): Current execution status
- `priority` (Priority): Priority level
- `progress` (float): Completion progress (0.0 to 1.0)
- `created_at` (datetime): Creation timestamp
- `started_at` (Optional[datetime]): Start timestamp
- `completed_at` (Optional[datetime]): Completion timestamp
- `parent_id` (Optional[str]): Parent goal ID (None for root goals)
- `sub_goal_ids` (List[str]): List of sub-goal IDs
- `dependency_ids` (List[str]): List of dependency goal IDs
- `metadata` (Dict[str, Any]): Additional metadata
- `error_message` (Optional[str]): Error message if failed

#### Validation

- `progress` must be between 0.0 and 1.0
- `started_at` must be after `created_at`
- `completed_at` must be after `started_at`

**Example**:
```python
from Agent_Guru.goal_manager.models import Goal, GoalStatus, Priority

goal = Goal(
    description="Implement feature X",
    status=GoalStatus.PENDING,
    priority=Priority.HIGH
)
print(f"Goal ID: {goal.id}")
```

---

### GoalStatus

**Module**: `Agent_Guru.goal_manager.models`

Enum representing goal execution status.

#### Values

- `PENDING`: Goal created, awaiting decomposition
- `DECOMPOSING`: Goal being decomposed by LLM
- `READY`: Goal ready for execution (dependencies satisfied)
- `IN_PROGRESS`: Goal currently executing
- `COMPLETE`: Goal completed successfully
- `FAILED`: Goal failed with error
- `CANCELLED`: Goal cancelled by user
- `BLOCKED`: Goal blocked by failed dependency

**Example**:
```python
from Agent_Guru.goal_manager.models import GoalStatus

if goal.status == GoalStatus.COMPLETE:
    print("Goal completed!")
```


---

### Priority

**Module**: `Agent_Guru.goal_manager.models`

Enum representing goal priority levels.

#### Values

- `CRITICAL`: Highest priority (0)
- `HIGH`: High priority (1)
- `MEDIUM`: Medium priority (2)
- `LOW`: Lowest priority (3)

**Example**:
```python
from Agent_Guru.goal_manager.models import Priority

goal = await manager.create_goal(
    description="Fix critical bug",
    priority=Priority.CRITICAL
)
```

---

## Storage Layer

### GoalStorage

**Module**: `Agent_Guru.goal_manager.goal_storage`

Persistent storage for goals using SQLite with ACID transactions and immediate persistence.

**Time Complexity**:
- `store_goal`: O(1) - single INSERT with index update
- `update_goal`: O(1) - single UPDATE with index update
- `get_goal`: O(1) - indexed lookup by primary key
- `query_goals`: O(log n) - indexed scan with filters

#### Constructor

```python
def __init__(self, db_path: str)
```

Initialize storage with database path. Creates database file and schema if they don't exist.

**Parameters**:
- `db_path` (str): Path to SQLite database file

**Raises**:
- `StorageError`: If database initialization fails

**Example**:
```python
storage = GoalStorage("goals.db")
```

#### Methods

##### store_goal

```python
async def store_goal(self, goal: Goal) -> None
```

Store goal with immediate persistence using ACID transaction.

**Parameters**:
- `goal` (Goal): Goal to store

**Raises**:
- `StorageError`: If persistence fails or goal already exists

**Example**:
```python
goal = Goal(description="Test goal")
await storage.store_goal(goal)
```

##### update_goal

```python
async def update_goal(self, goal: Goal) -> None
```

Update goal with immediate persistence using ACID transaction.

**Parameters**:
- `goal` (Goal): Goal with updated fields

**Raises**:
- `StorageError`: If persistence fails or goal not found

**Example**:
```python
goal.status = GoalStatus.COMPLETE
await storage.update_goal(goal)
```


##### get_goal

```python
async def get_goal(self, goal_id: str) -> Optional[Goal]
```

Retrieve goal by ID using primary key index for O(1) lookup.

**Parameters**:
- `goal_id` (str): Goal identifier

**Returns**:
- `Optional[Goal]`: Goal if found, None otherwise

**Raises**:
- `StorageError`: If retrieval fails

**Example**:
```python
goal = await storage.get_goal("goal-id-123")
if goal:
    print(f"Found: {goal.description}")
```

##### query_goals

```python
async def query_goals(
    self,
    status: Optional[GoalStatus] = None,
    priority: Optional[Priority] = None
) -> List[Goal]
```

Query goals with optional filters using indexed scan.

**Parameters**:
- `status` (GoalStatus, optional): Filter by status
- `priority` (Priority, optional): Filter by priority

**Returns**:
- `List[Goal]`: List of goals matching filters

**Raises**:
- `StorageError`: If query fails

**Example**:
```python
pending = await storage.query_goals(status=GoalStatus.PENDING)
high_priority = await storage.query_goals(priority=Priority.HIGH)
```

##### export_to_json

```python
async def export_to_json(self, output_path: str) -> None
```

Export all goals to JSON file for backup.

**Parameters**:
- `output_path` (str): Path to output JSON file

**Raises**:
- `StorageError`: If export fails

**Example**:
```python
await storage.export_to_json("goals_backup.json")
```

##### import_from_json

```python
async def import_from_json(self, input_path: str) -> int
```

Import goals from JSON file.

**Parameters**:
- `input_path` (str): Path to input JSON file

**Returns**:
- `int`: Number of goals imported (skips duplicates)

**Raises**:
- `StorageError`: If import fails

**Example**:
```python
count = await storage.import_from_json("goals_backup.json")
print(f"Imported {count} goals")
```

---

## Decomposition

### GoalDecomposer

**Module**: `Agent_Guru.goal_manager.goal_decomposer`

Decomposes high-level goals into actionable sub-goals using LLM Runtime.

**Time Complexity**: O(1) per decomposition (LLM call dominates)  
**Space Complexity**: O(n) where n is number of sub-goals generated


#### Constructor

```python
def __init__(self, llm_runtime: Any, memory_system: Any)
```

Initialize with LLM Runtime and Memory System.

**Parameters**:
- `llm_runtime` (Any): LLM Runtime instance with `generate()` method
- `memory_system` (Any): Memory System instance with `query_similar()` method

**Example**:
```python
decomposer = GoalDecomposer(llm_runtime, memory_system)
```

#### Methods

##### decompose

```python
async def decompose(self, goal: Goal) -> List[Goal]
```

Decompose goal into 3-7 actionable sub-goals using LLM.

**Process**:
1. Query Memory System for relevant context
2. Build structured decomposition prompt
3. Call LLM with retry logic (exponential backoff)
4. Parse JSON response into Goal objects
5. Validate sub-goals meet quality criteria

**Parameters**:
- `goal` (Goal): Goal to decompose

**Returns**:
- `List[Goal]`: List of sub-goals (typically 3-7)

**Raises**:
- `DecompositionError`: If LLM fails after retries or returns invalid response

**Example**:
```python
parent_goal = Goal(description="Build user authentication")
sub_goals = await decomposer.decompose(parent_goal)
print(f"Generated {len(sub_goals)} sub-goals")
```

---

## Progress Tracking

### ProgressTracker

**Module**: `Agent_Guru.goal_manager.progress_tracker`

Tracks goal progress and propagates status changes up the hierarchy.

**Time Complexity**:
- `mark_complete`: O(h) where h is hierarchy depth
- `mark_failed`: O(h) where h is hierarchy depth
- `mark_in_progress`: O(1)

#### Constructor

```python
def __init__(self, storage: GoalStorage)
```

Initialize with storage.

**Parameters**:
- `storage` (GoalStorage): GoalStorage instance for persistence

**Example**:
```python
tracker = ProgressTracker(storage)
```

#### Methods

##### mark_complete

```python
async def mark_complete(self, goal_id: str) -> None
```

Mark goal as complete and recursively update parent progress.

**Parameters**:
- `goal_id` (str): Goal to mark as complete

**Example**:
```python
await tracker.mark_complete(sub_goal_id)
# Parent progress automatically updated
```


##### mark_failed

```python
async def mark_failed(self, goal_id: str, error_message: str) -> None
```

Mark goal as failed with error message and update parent progress.

**Parameters**:
- `goal_id` (str): Goal to mark as failed
- `error_message` (str): Error description

**Example**:
```python
await tracker.mark_failed(goal_id, "Task execution failed")
```

##### mark_in_progress

```python
async def mark_in_progress(self, goal_id: str) -> None
```

Mark goal as in progress and record start timestamp.

**Parameters**:
- `goal_id` (str): Goal to mark as in progress

**Example**:
```python
await tracker.mark_in_progress(goal_id)
```

---

## Priority Management

### PriorityManager

**Module**: `Agent_Guru.goal_manager.priority_manager`

Manages goal priorities and intelligent selection for execution.

**Time Complexity**:
- `update_priority`: O(1)
- `select_next_goal`: O(n log n) where n is number of ready goals

#### Constructor

```python
def __init__(self, storage: GoalStorage)
```

Initialize with storage.

**Parameters**:
- `storage` (GoalStorage): GoalStorage instance for persistence

**Example**:
```python
manager = PriorityManager(storage)
```

#### Methods

##### update_priority

```python
async def update_priority(self, goal_id: str, priority: Priority) -> None
```

Update goal priority with immediate persistence.

**Parameters**:
- `goal_id` (str): Goal identifier
- `priority` (Priority): New priority level

**Raises**:
- `ValueError`: If goal not found
- `StorageError`: If persistence fails

**Example**:
```python
await manager.update_priority(goal_id, Priority.HIGH)
```

##### select_next_goal

```python
async def select_next_goal(self) -> Optional[Goal]
```

Select next goal for execution based on priority and age.

**Selection Criteria** (in order):
1. Status must be READY
2. Highest priority first (CRITICAL > HIGH > MEDIUM > LOW)
3. Oldest goal (earliest created_at) for tie-breaking

**Returns**:
- `Optional[Goal]`: Next goal to execute, or None if no ready goals

**Raises**:
- `StorageError`: If query fails

**Example**:
```python
next_goal = await manager.select_next_goal()
if next_goal:
    print(f"Executing: {next_goal.description}")
```


---

## Dependency Management

### DependencyResolver

**Module**: `Agent_Guru.goal_manager.dependency_resolver`

Manages goal dependencies with cycle detection using depth-first search.

**Time Complexity**:
- `validate_dependencies`: O(V + E) where V is goals, E is dependencies
- `is_ready`: O(D) where D is number of dependencies
- `mark_blocked`: O(V + E)

#### Constructor

```python
def __init__(self, storage: GoalStorage)
```

Initialize with storage.

**Parameters**:
- `storage` (GoalStorage): GoalStorage instance for querying goals

**Example**:
```python
resolver = DependencyResolver(storage)
```

#### Methods

##### validate_dependencies

```python
async def validate_dependencies(self, goal: Goal) -> None
```

Validate goal dependencies don't form cycles using depth-first search.

**Parameters**:
- `goal` (Goal): Goal to validate

**Raises**:
- `ValidationError`: If circular dependencies detected

**Example**:
```python
goal_a = Goal(description="Goal A")
goal_b = Goal(description="Goal B", dependency_ids=[goal_a.id])
await resolver.validate_dependencies(goal_b)  # OK

goal_a.dependency_ids = [goal_b.id]
await resolver.validate_dependencies(goal_a)  # Raises ValidationError
```

##### is_ready

```python
async def is_ready(self, goal: Goal) -> bool
```

Check if goal is ready for execution (all dependencies complete).

**Parameters**:
- `goal` (Goal): Goal to check

**Returns**:
- `bool`: True if ready for execution, False otherwise

**Example**:
```python
if await resolver.is_ready(goal):
    await executor.execute_goal(goal.id)
```

##### mark_blocked

```python
async def mark_blocked(self, goal_id: str) -> None
```

Mark goal as blocked and recursively propagate to all dependent goals.

**Parameters**:
- `goal_id` (str): Goal to mark as blocked

**Example**:
```python
await resolver.mark_blocked(failed_goal_id)
# All dependent goals also marked as blocked
```

---

## Execution

### GoalExecutor

**Module**: `Agent_Guru.goal_manager.goal_executor`

Coordinates goal execution with Agent Orchestration, GitHub commits, and metrics reporting.

**Time Complexity**: O(n) per goal where n is number of sub-goals  
**Space Complexity**: O(k) where k is number of active executions


#### Constructor

```python
def __init__(
    self,
    agent_orchestration: Any,
    storage: GoalStorage,
    git_repo_path: str,
    self_improvement_engine: Any
)
```

Initialize Goal Executor with dependencies.

**Parameters**:
- `agent_orchestration` (Any): Agent Orchestration system for task execution
- `storage` (GoalStorage): Goal storage for persistence
- `git_repo_path` (str): Path to Git repository for commits
- `self_improvement_engine` (Any): Self-Improvement Engine for metrics reporting

**Raises**:
- `ExecutionError`: If git_repo_path is invalid or not a Git repository

**Example**:
```python
executor = GoalExecutor(
    agent_orchestration=orchestrator,
    storage=storage,
    git_repo_path=".",
    self_improvement_engine=engine
)
```

#### Methods

##### execute_goal

```python
async def execute_goal(self, goal_id: str) -> None
```

Execute goal by processing sub-goals sequentially.

**Process**:
1. Mark goal as IN_PROGRESS with timestamp
2. Iterate through sub_goal_ids sequentially
3. Handle recursive execution for sub-goals with children
4. Handle leaf sub-goal execution via Agent Orchestration
5. Check for failures and propagate to parent
6. Mark goal as COMPLETE when all sub-goals done

**Parameters**:
- `goal_id` (str): Goal to execute

**Raises**:
- `ExecutionError`: If goal not found or execution fails critically

**Example**:
```python
await executor.execute_goal("goal-uuid-123")
```

##### stop_execution

```python
async def stop_execution(self, goal_id: str) -> None
```

Stop execution of a goal by canceling its task in Agent Orchestration.

**Parameters**:
- `goal_id` (str): Goal to stop execution for

**Example**:
```python
await executor.stop_execution("goal-uuid-123")
```

##### resume_goal

```python
async def resume_goal(self, goal_id: str) -> None
```

Resume execution of an interrupted goal from the last completed sub-goal.

**Parameters**:
- `goal_id` (str): Goal to resume execution for

**Raises**:
- `ExecutionError`: If goal not found

**Example**:
```python
# Goal was interrupted after completing 2 of 5 sub-goals
await executor.resume_goal("goal-uuid-123")
# Execution resumes from sub-goal 3
```

---

## Session Management

### SessionManager

**Module**: `Agent_Guru.goal_manager.session_manager`

Manages goal persistence and restoration across system restarts.

**Time Complexity**:
- `load_goals`: O(n) where n is number of goals
- `persist_all`: O(1) - no-op with immediate persistence


#### Constructor

```python
def __init__(self, storage: GoalStorage)
```

Initialize session manager with storage dependency.

**Parameters**:
- `storage` (GoalStorage): GoalStorage instance for persistence operations

**Example**:
```python
session_manager = SessionManager(storage)
```

#### Methods

##### load_goals

```python
async def load_goals(self) -> None
```

Load all goals from storage on startup and validate integrity.

**Process**:
1. Query all goals from storage
2. Validate integrity of each goal
3. Attempt recovery for corrupted goals
4. Log warnings if corruption detected

**Raises**:
- `StorageError`: If storage operations fail catastrophically

**Example**:
```python
await session_manager.load_goals()
```

##### persist_all

```python
async def persist_all(self) -> None
```

Persist all goal state before shutdown. This is a no-op with immediate persistence strategy but kept for API consistency.

**Example**:
```python
await session_manager.persist_all()
```

---

## Exceptions

**Module**: `Agent_Guru.goal_manager.exceptions`

### GoalManagerError

Base exception for all Goal Manager errors.

**Attributes**:
- `message` (str): Human-readable error message
- `context` (dict): Optional dictionary containing error context

**Example**:
```python
try:
    await goal_manager.create_goal("Test goal")
except GoalManagerError as e:
    logger.error(f"Goal Manager error: {e}")
```

### StorageError

Raised when storage operations fail (database errors, I/O errors, data corruption).

**Common Causes**:
- Database connection failures
- Disk full or I/O errors
- SQLite locking conflicts
- Data corruption or invalid schema

**Example**:
```python
try:
    await storage.store_goal(goal)
except StorageError as e:
    logger.error(f"Failed to store goal: {e}")
```

### DecompositionError

Raised when goal decomposition fails (LLM errors, invalid responses).

**Common Causes**:
- LLM Runtime unavailable or timeout
- LLM returns invalid JSON response
- Sub-goals fail validation

**Example**:
```python
try:
    sub_goals = await decomposer.decompose(goal)
except DecompositionError as e:
    logger.error(f"Failed to decompose goal: {e}")
```


### ValidationError

Raised when validation fails (circular dependencies, invalid data, schema violations).

**Common Causes**:
- Circular dependencies detected
- Invalid goal data (missing required fields, invalid types)
- Schema validation failures
- Constraint violations

**Example**:
```python
try:
    dependency_resolver.validate_dependencies(goal)
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
```

### ExecutionError

Raised when goal execution fails (Agent Orchestration errors, task failures).

**Common Causes**:
- Agent Orchestration unavailable or timeout
- Task creation or execution failure
- Sub-goal execution failure

**Example**:
```python
try:
    await executor.execute_goal(goal_id)
except ExecutionError as e:
    logger.error(f"Failed to execute goal: {e}")
```

---

## Utilities

**Module**: `Agent_Guru.goal_manager.utils`

### retry_with_backoff

```python
async def retry_with_backoff(
    operation: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 1.0
) -> Any
```

Retry an async operation with exponential backoff for handling transient failures.

**Retry Schedule** (with default base_delay=1.0):
- Attempt 1: Immediate
- Attempt 2: After 1.0s delay (base_delay * 2^0)
- Attempt 3: After 2.0s delay (base_delay * 2^1)
- Attempt 4: After 4.0s delay (base_delay * 2^2)

**Parameters**:
- `operation` (Callable): Async callable to retry (should take no arguments)
- `max_retries` (int, optional): Maximum number of retry attempts (default: 3)
- `base_delay` (float, optional): Base delay in seconds for exponential backoff (default: 1.0)

**Returns**:
- `Any`: Result of the operation if successful

**Raises**:
- `Exception`: The last exception raised by the operation after all retries are exhausted

**Example**:
```python
from Agent_Guru.goal_manager.utils import retry_with_backoff

# Retry LLM call with default settings (3 retries, 1s base delay)
response = await retry_with_backoff(
    operation=lambda: llm_runtime.generate(prompt)
)

# Retry with custom settings (5 retries, 2s base delay)
result = await retry_with_backoff(
    operation=lambda: agent_orchestration.create_task(task),
    max_retries=5,
    base_delay=2.0
)
```

---

## Complete Usage Example

Here's a complete example demonstrating the full Goal Manager API:

```python
import asyncio
from Agent_Guru.goal_manager import GoalManager, Priority, GoalStatus

async def main():
    # Initialize Goal Manager
    manager = GoalManager(
        storage_path="goals.db",
        git_repo_path=".",
        llm_runtime=llm_runtime,
        agent_orchestration=orchestrator,
        memory_system=memory,
        self_improvement_engine=engine
    )
    
    # Start the manager
    await manager.start()
    
    # Create a high-priority goal
    goal = await manager.create_goal(
        description="Implement user authentication system",
        priority=Priority.HIGH,
        metadata={"team": "backend", "sprint": "2024-Q1"}
    )
    print(f"Created goal: {goal.id}")
    
    # Query pending goals
    pending = await manager.query_goals(status=GoalStatus.PENDING)
    print(f"Pending goals: {len(pending)}")
    
    # Update priority
    await manager.update_priority(goal.id, Priority.CRITICAL)
    
    # Get summary
    summary = await manager.get_summary()
    print(f"Progress: {summary['overall_progress']:.1%}")
    print(f"Completed: {summary['completed']}/{summary['total_goals']}")
    
    # Modify goal
    await manager.modify_goal(
        goal.id,
        notes="Added security requirements"
    )
    
    # Get specific goal
    retrieved = await manager.get_goal(goal.id)
    if retrieved:
        print(f"Status: {retrieved.status}")
        print(f"Progress: {retrieved.progress:.1%}")
    
    # Shutdown
    await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Performance Characteristics

### Time Complexity Summary

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| create_goal | O(1) | Single database insert |
| get_goal | O(1) | Indexed lookup by primary key |
| query_goals | O(log n + k) | Indexed scan, k results |
| update_priority | O(1) | Single database update |
| cancel_goal | O(n) | Recursive cancellation of sub-goals |
| decompose | O(1) | LLM call dominates |
| mark_complete | O(h) | Recursive parent updates, h = hierarchy depth |
| execute_goal | O(n) | Sequential sub-goal execution |
| validate_dependencies | O(V + E) | DFS traversal, V = goals, E = dependencies |

### Space Complexity Summary

| Component | Complexity | Notes |
|-----------|-----------|-------|
| GoalStorage | O(n) | n = number of goals |
| GoalExecutor | O(k) | k = active executions |
| DependencyResolver | O(V) | V = goals (DFS visited set) |
| ProgressTracker | O(h) | h = hierarchy depth (recursion stack) |

---

## Thread Safety

The Goal Manager uses SQLite for persistence, which provides thread-safe operations through connection-per-operation pattern. However, the Goal Manager itself is designed for single-threaded async operation. For concurrent access from multiple threads, use appropriate locking mechanisms.

---

## Best Practices

1. **Always await async operations**: All Goal Manager methods are async and must be awaited
2. **Handle exceptions**: Wrap operations in try-except blocks to handle errors gracefully
3. **Use context managers**: Consider using context managers for startup/shutdown
4. **Monitor progress**: Use `get_summary()` to track overall progress
5. **Validate dependencies**: Always validate dependencies before creating goals with dependencies
6. **Use appropriate priorities**: Set priorities based on business importance
7. **Add metadata**: Use metadata field for additional context and tracking
8. **Check status**: Always check goal status before performing operations
9. **Handle failures**: Implement retry logic for transient failures
10. **Log operations**: Use structured logging for debugging and monitoring

---

**End of API Reference**

For more information, see:
- [Architecture Documentation](ARCHITECTURE.md)
- [API Usage Examples](API_USAGE.md)
- [Integration Guide](INTEGRATIONS.md)
