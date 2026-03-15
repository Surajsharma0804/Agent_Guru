# Goal Manager API Usage Examples

## Overview

This document provides comprehensive examples of using the Goal Manager API for common use cases. All examples assume you have initialized the Goal Manager with required dependencies.

## Table of Contents

1. [Initialization](#initialization)
2. [Basic Goal Creation and Execution](#basic-goal-creation-and-execution)
3. [Goal with Dependencies](#goal-with-dependencies)
4. [Goal Cancellation](#goal-cancellation)
5. [Querying and Filtering Goals](#querying-and-filtering-goals)
6. [System Startup and Shutdown](#system-startup-and-shutdown)
7. [Error Handling](#error-handling)
8. [Advanced Use Cases](#advanced-use-cases)

## Initialization

```python
from Agent_Guru.goal_manager import GoalManager, Priority
from Agent_Guru.llm import LLMRuntime
from Agent_Guru.agents import AgentOrchestration
from Agent_Guru.memory import MemorySystem
from Agent_Guru.reasoning import SelfImprovementEngine

# Initialize dependencies
llm_runtime = LLMRuntime(provider="openai", model="gpt-4")
agent_orchestration = AgentOrchestration()
memory_system = MemorySystem(storage_path="./memory")
self_improvement_engine = SelfImprovementEngine()

# Initialize Goal Manager
goal_manager = GoalManager(
    storage_path="./goals.db",
    git_repo_path="./",
    llm_runtime=llm_runtime,
    agent_orchestration=agent_orchestration,
    memory_system=memory_system,
    self_improvement_engine=self_improvement_engine
)

# Start Goal Manager (loads existing goals)
await goal_manager.start()
```

## Basic Goal Creation and Execution

### Example 1: Create a Simple Goal

```python
# Create a goal with default priority (MEDIUM)
goal = await goal_manager.create_goal(
    description="Implement user authentication system"
)

print(f"Created goal: {goal.id}")
print(f"Status: {goal.status}")  # PENDING
print(f"Priority: {goal.priority}")  # MEDIUM
print(f"Progress: {goal.progress}")  # 0.0
```

### Example 2: Create a High-Priority Goal

```python
# Create a critical priority goal
goal = await goal_manager.create_goal(
    description="Fix critical security vulnerability in login endpoint",
    priority=Priority.CRITICAL,
    metadata={
        "severity": "critical",
        "affected_component": "authentication",
        "deadline": "2024-01-20"
    }
)

print(f"Created critical goal: {goal.id}")
print(f"Priority: {goal.priority}")  # CRITICAL
```

### Example 3: Monitor Goal Progress

```python
# Create a goal
goal = await goal_manager.create_goal(
    description="Build REST API for user management"
)

# Wait for decomposition to complete
await asyncio.sleep(5)

# Get updated goal with sub-goals
updated_goal = await goal_manager.get_goal(goal.id)

print(f"Goal status: {updated_goal.status}")
print(f"Number of sub-goals: {len(updated_goal.sub_goal_ids)}")
print(f"Progress: {updated_goal.progress * 100:.1f}%")

# Monitor progress periodically
while updated_goal.status not in [GoalStatus.COMPLETE, GoalStatus.FAILED]:
    await asyncio.sleep(10)
    updated_goal = await goal_manager.get_goal(goal.id)
    print(f"Progress: {updated_goal.progress * 100:.1f}%")

print(f"Final status: {updated_goal.status}")
```

### Example 4: Retrieve Goal Hierarchy

```python
# Create a goal and wait for decomposition
goal = await goal_manager.create_goal(
    description="Implement payment processing system"
)

await asyncio.sleep(5)

# Get complete hierarchy
goal_with_hierarchy = await goal_manager.get_goal(goal.id)

print(f"Parent goal: {goal_with_hierarchy.description}")
print(f"Sub-goals:")
for sub_goal_id in goal_with_hierarchy.sub_goal_ids:
    sub_goal = await goal_manager.get_goal(sub_goal_id)
    print(f"  - {sub_goal.description} ({sub_goal.status})")
```

## Goal with Dependencies

### Example 5: Create Goals with Dependencies

```python
# Create first goal (no dependencies)
goal_a = await goal_manager.create_goal(
    description="Design database schema for user management"
)

# Create second goal that depends on first
goal_b = await goal_manager.create_goal(
    description="Implement user CRUD operations",
    dependencies=[goal_a.id]
)

# Create third goal that depends on second
goal_c = await goal_manager.create_goal(
    description="Add user authentication endpoints",
    dependencies=[goal_b.id]
)

print(f"Goal A: {goal_a.id} (no dependencies)")
print(f"Goal B: {goal_b.id} (depends on A)")
print(f"Goal C: {goal_c.id} (depends on B)")

# Goal B will be BLOCKED until Goal A completes
goal_b_status = await goal_manager.get_goal(goal_b.id)
print(f"Goal B status: {goal_b_status.status}")  # BLOCKED or PENDING
```

### Example 6: Handle Circular Dependencies

```python
try:
    # Create goal A
    goal_a = await goal_manager.create_goal(
        description="Implement feature A"
    )
    
    # Create goal B that depends on A
    goal_b = await goal_manager.create_goal(
        description="Implement feature B",
        dependencies=[goal_a.id]
    )
    
    # Try to create circular dependency (A depends on B)
    # This will raise ValidationError
    await goal_manager.create_goal(
        description="Update feature A",
        dependencies=[goal_b.id]
    )
    
except ValidationError as e:
    print(f"Circular dependency detected: {e}")
```

### Example 7: Monitor Dependency Satisfaction

```python
# Create goals with dependencies
goal_a = await goal_manager.create_goal(
    description="Set up development environment"
)

goal_b = await goal_manager.create_goal(
    description="Write unit tests",
    dependencies=[goal_a.id]
)

# Monitor goal B status
while True:
    goal_b_current = await goal_manager.get_goal(goal_b.id)
    
    if goal_b_current.status == GoalStatus.READY:
        print("Goal B is ready for execution (dependencies satisfied)")
        break
    elif goal_b_current.status == GoalStatus.BLOCKED:
        print("Goal B is blocked (waiting for dependencies)")
    
    await asyncio.sleep(5)
```

## Goal Cancellation

### Example 8: Cancel a Single Goal

```python
# Create a goal
goal = await goal_manager.create_goal(
    description="Implement feature X"
)

# Cancel the goal
await goal_manager.cancel_goal(goal.id)

# Verify cancellation
cancelled_goal = await goal_manager.get_goal(goal.id)
print(f"Goal status: {cancelled_goal.status}")  # CANCELLED
```

### Example 9: Cancel Goal with Sub-Goals

```python
# Create a goal and wait for decomposition
goal = await goal_manager.create_goal(
    description="Build complete user management system"
)

await asyncio.sleep(5)

# Get goal with sub-goals
goal_with_subs = await goal_manager.get_goal(goal.id)
print(f"Goal has {len(goal_with_subs.sub_goal_ids)} sub-goals")

# Cancel parent goal (cancels all sub-goals)
await goal_manager.cancel_goal(goal.id)

# Verify all sub-goals are cancelled
for sub_goal_id in goal_with_subs.sub_goal_ids:
    sub_goal = await goal_manager.get_goal(sub_goal_id)
    print(f"Sub-goal {sub_goal_id}: {sub_goal.status}")  # All CANCELLED
```

### Example 10: Cancel In-Progress Goal

```python
# Create and start executing a goal
goal = await goal_manager.create_goal(
    description="Process large dataset"
)

# Wait for execution to start
await asyncio.sleep(10)

# Check if in progress
current_goal = await goal_manager.get_goal(goal.id)
if current_goal.status == GoalStatus.IN_PROGRESS:
    print("Goal is executing, cancelling...")
    
    # Cancel will stop execution
    await goal_manager.cancel_goal(goal.id)
    
    # Verify cancellation
    cancelled_goal = await goal_manager.get_goal(goal.id)
    print(f"Goal status: {cancelled_goal.status}")  # CANCELLED
```

## Querying and Filtering Goals

### Example 11: Query All Goals

```python
# Get all goals
all_goals = await goal_manager.query_goals()

print(f"Total goals: {len(all_goals)}")
for goal in all_goals:
    print(f"  {goal.id}: {goal.description} ({goal.status})")
```

### Example 12: Filter by Status

```python
# Get all in-progress goals
in_progress_goals = await goal_manager.query_goals(
    status=GoalStatus.IN_PROGRESS
)

print(f"In-progress goals: {len(in_progress_goals)}")
for goal in in_progress_goals:
    print(f"  {goal.description}: {goal.progress * 100:.1f}% complete")

# Get all completed goals
completed_goals = await goal_manager.query_goals(
    status=GoalStatus.COMPLETE
)

print(f"Completed goals: {len(completed_goals)}")
```

### Example 13: Filter by Priority

```python
# Get all critical priority goals
critical_goals = await goal_manager.query_goals(
    priority=Priority.CRITICAL
)

print(f"Critical goals: {len(critical_goals)}")
for goal in critical_goals:
    print(f"  {goal.description} ({goal.status})")

# Get all high priority goals
high_priority_goals = await goal_manager.query_goals(
    priority=Priority.HIGH
)

print(f"High priority goals: {len(high_priority_goals)}")
```

### Example 14: Filter by Status and Priority

```python
# Get all pending critical goals
pending_critical = await goal_manager.query_goals(
    status=GoalStatus.PENDING,
    priority=Priority.CRITICAL
)

print(f"Pending critical goals: {len(pending_critical)}")
for goal in pending_critical:
    print(f"  {goal.description}")
```

### Example 15: Get System Summary

```python
# Get summary of all goals
summary = await goal_manager.get_summary()

print("Goal Manager Summary:")
print(f"  Total goals: {summary['total_goals']}")
print(f"  Completed: {summary['completed']}")
print(f"  In progress: {summary['in_progress']}")
print(f"  Failed: {summary['failed']}")
print(f"  Overall progress: {summary['overall_progress'] * 100:.1f}%")
```

## System Startup and Shutdown

### Example 16: Proper Startup

```python
# Initialize Goal Manager
goal_manager = GoalManager(
    storage_path="./goals.db",
    git_repo_path="./",
    llm_runtime=llm_runtime,
    agent_orchestration=agent_orchestration,
    memory_system=memory_system,
    self_improvement_engine=self_improvement_engine
)

# Start Goal Manager
# This loads all existing goals and resumes interrupted ones
await goal_manager.start()

print("Goal Manager started successfully")

# Get summary to see restored goals
summary = await goal_manager.get_summary()
print(f"Loaded {summary['total_goals']} goals from storage")
print(f"Resuming {summary['in_progress']} interrupted goals")
```

### Example 17: Proper Shutdown

```python
# Before shutting down, persist all state
await goal_manager.shutdown()

print("Goal Manager shut down successfully")
print("All goal state persisted to disk")
```

### Example 18: Complete Lifecycle

```python
async def main():
    # Initialize
    goal_manager = GoalManager(...)
    
    try:
        # Start
        await goal_manager.start()
        
        # Create and execute goals
        goal = await goal_manager.create_goal(
            description="Complete project milestone"
        )
        
        # Wait for completion
        while True:
            current = await goal_manager.get_goal(goal.id)
            if current.status in [GoalStatus.COMPLETE, GoalStatus.FAILED]:
                break
            await asyncio.sleep(10)
        
        print(f"Goal completed with status: {current.status}")
    
    finally:
        # Always shutdown properly
        await goal_manager.shutdown()

# Run
asyncio.run(main())
```

## Error Handling

### Example 19: Handle Storage Errors

```python
from Agent_Guru.goal_manager.exceptions import StorageError

try:
    goal = await goal_manager.create_goal(
        description="Implement new feature"
    )
except StorageError as e:
    print(f"Failed to persist goal: {e}")
    print("Retrying with exponential backoff...")
    # Goal Manager automatically retries, but you can handle it here
```

### Example 20: Handle Decomposition Errors

```python
from Agent_Guru.goal_manager.exceptions import DecompositionError

# Create a goal
goal = await goal_manager.create_goal(
    description="Very complex goal that might fail decomposition"
)

# Wait for decomposition
await asyncio.sleep(10)

# Check if decomposition failed
updated_goal = await goal_manager.get_goal(goal.id)
if updated_goal.status == GoalStatus.FAILED:
    print(f"Decomposition failed: {updated_goal.error_message}")
    
    # You can retry by creating a new goal with modified description
    retry_goal = await goal_manager.create_goal(
        description="Simplified version of the goal"
    )
```

### Example 21: Handle Validation Errors

```python
from Agent_Guru.goal_manager.exceptions import ValidationError

try:
    # Try to create goal with circular dependency
    goal_a = await goal_manager.create_goal(
        description="Feature A"
    )
    
    goal_b = await goal_manager.create_goal(
        description="Feature B",
        dependencies=[goal_a.id]
    )
    
    # This will raise ValidationError
    goal_a_updated = await goal_manager.create_goal(
        description="Feature A updated",
        dependencies=[goal_b.id]
    )
    
except ValidationError as e:
    print(f"Validation error: {e}")
    print("Cannot create circular dependency")
```

### Example 22: Handle Execution Errors

```python
from Agent_Guru.goal_manager.exceptions import ExecutionError

# Create a goal
goal = await goal_manager.create_goal(
    description="Execute complex task"
)

# Monitor for execution errors
while True:
    current = await goal_manager.get_goal(goal.id)
    
    if current.status == GoalStatus.FAILED:
        print(f"Execution failed: {current.error_message}")
        
        # Check which sub-goal failed
        for sub_goal_id in current.sub_goal_ids:
            sub_goal = await goal_manager.get_goal(sub_goal_id)
            if sub_goal.status == GoalStatus.FAILED:
                print(f"Failed sub-goal: {sub_goal.description}")
                print(f"Error: {sub_goal.error_message}")
        
        break
    
    elif current.status == GoalStatus.COMPLETE:
        print("Goal completed successfully")
        break
    
    await asyncio.sleep(10)
```

## Advanced Use Cases

### Example 23: Update Goal Priority

```python
# Create a goal with default priority
goal = await goal_manager.create_goal(
    description="Implement analytics dashboard"
)

print(f"Initial priority: {goal.priority}")  # MEDIUM

# Update priority to HIGH
await goal_manager.update_priority(goal.id, Priority.HIGH)

# Verify update
updated_goal = await goal_manager.get_goal(goal.id)
print(f"Updated priority: {updated_goal.priority}")  # HIGH
```

### Example 24: Modify Goal Description

```python
# Create a goal
goal = await goal_manager.create_goal(
    description="Implement feature X"
)

# Modify description (only for PENDING goals)
if goal.status == GoalStatus.PENDING:
    await goal_manager.modify_goal(
        goal.id,
        description="Implement enhanced feature X with additional capabilities"
    )
    
    # Re-decompose with new description
    await goal_manager.re_decompose_goal(goal.id)
```

### Example 25: Add Notes to Completed Goal

```python
# Get a completed goal
completed_goals = await goal_manager.query_goals(
    status=GoalStatus.COMPLETE
)

if completed_goals:
    goal = completed_goals[0]
    
    # Add notes to completed goal
    goal.metadata["completion_notes"] = "Completed ahead of schedule"
    goal.metadata["lessons_learned"] = "Better planning reduced execution time"
    
    # Update goal
    await goal_manager.storage.update_goal(goal)
```

### Example 26: Export and Import Goals

```python
# Export all goals to JSON file
await goal_manager.storage.export_to_json("goals_backup.json")
print("Goals exported to goals_backup.json")

# Import goals from JSON file
count = await goal_manager.storage.import_from_json("goals_backup.json")
print(f"Imported {count} goals from backup")
```

### Example 27: Monitor Real-Time Progress

```python
import asyncio

async def monitor_goal_progress(goal_id: str):
    """Monitor goal progress in real-time."""
    while True:
        goal = await goal_manager.get_goal(goal_id)
        
        print(f"\rProgress: {goal.progress * 100:.1f}% | Status: {goal.status}", end="")
        
        if goal.status in [GoalStatus.COMPLETE, GoalStatus.FAILED, GoalStatus.CANCELLED]:
            print()  # New line
            break
        
        await asyncio.sleep(1)

# Create goal and monitor
goal = await goal_manager.create_goal(
    description="Process large dataset"
)

await monitor_goal_progress(goal.id)
```

### Example 28: Batch Goal Creation

```python
# Create multiple goals at once
goal_descriptions = [
    "Implement user authentication",
    "Build REST API",
    "Create admin dashboard",
    "Add email notifications",
    "Implement search functionality"
]

created_goals = []
for description in goal_descriptions:
    goal = await goal_manager.create_goal(
        description=description,
        priority=Priority.HIGH
    )
    created_goals.append(goal)
    print(f"Created: {goal.id}")

print(f"Created {len(created_goals)} goals")
```

### Example 29: Find Goals by Metadata

```python
# Create goals with metadata
goal1 = await goal_manager.create_goal(
    description="Implement payment processing",
    metadata={"component": "payments", "sprint": "sprint-5"}
)

goal2 = await goal_manager.create_goal(
    description="Add payment webhooks",
    metadata={"component": "payments", "sprint": "sprint-5"}
)

# Query all goals and filter by metadata
all_goals = await goal_manager.query_goals()
payment_goals = [
    g for g in all_goals
    if g.metadata.get("component") == "payments"
]

print(f"Found {len(payment_goals)} payment-related goals")
```

### Example 30: Implement Custom Goal Workflow

```python
async def create_and_track_goal(description: str, priority: Priority = Priority.MEDIUM):
    """Create goal and track until completion."""
    # Create goal
    goal = await goal_manager.create_goal(
        description=description,
        priority=priority
    )
    
    print(f"Created goal: {goal.id}")
    print(f"Description: {description}")
    print(f"Priority: {priority}")
    
    # Wait for decomposition
    print("Waiting for decomposition...")
    await asyncio.sleep(5)
    
    # Get sub-goals
    updated_goal = await goal_manager.get_goal(goal.id)
    print(f"Decomposed into {len(updated_goal.sub_goal_ids)} sub-goals")
    
    # Track progress
    while updated_goal.status not in [GoalStatus.COMPLETE, GoalStatus.FAILED]:
        await asyncio.sleep(10)
        updated_goal = await goal_manager.get_goal(goal.id)
        print(f"Progress: {updated_goal.progress * 100:.1f}%")
    
    # Report final status
    print(f"Final status: {updated_goal.status}")
    
    if updated_goal.status == GoalStatus.COMPLETE:
        print("✓ Goal completed successfully")
    else:
        print(f"✗ Goal failed: {updated_goal.error_message}")
    
    return updated_goal

# Use the workflow
goal = await create_and_track_goal(
    description="Implement complete user management system",
    priority=Priority.HIGH
)
```

## Best Practices

### 1. Always Use Async/Await

```python
# Good
goal = await goal_manager.create_goal("Implement feature")

# Bad (will not work)
goal = goal_manager.create_goal("Implement feature")
```

### 2. Handle Errors Gracefully

```python
try:
    goal = await goal_manager.create_goal("Complex goal")
except Exception as e:
    print(f"Error creating goal: {e}")
    # Handle error appropriately
```

### 3. Always Shutdown Properly

```python
try:
    await goal_manager.start()
    # ... use goal manager
finally:
    await goal_manager.shutdown()
```

### 4. Use Descriptive Goal Descriptions

```python
# Good
goal = await goal_manager.create_goal(
    description="Implement user authentication with JWT tokens and refresh token rotation"
)

# Bad (too vague)
goal = await goal_manager.create_goal(
    description="Do auth"
)
```

### 5. Set Appropriate Priorities

```python
# Critical: Security issues, production bugs
goal = await goal_manager.create_goal(
    description="Fix SQL injection vulnerability",
    priority=Priority.CRITICAL
)

# High: Important features, blocking issues
goal = await goal_manager.create_goal(
    description="Implement payment processing",
    priority=Priority.HIGH
)

# Medium: Regular features (default)
goal = await goal_manager.create_goal(
    description="Add user profile page"
)

# Low: Nice-to-have features
goal = await goal_manager.create_goal(
    description="Add dark mode theme",
    priority=Priority.LOW
)
```

### 6. Use Metadata for Organization

```python
goal = await goal_manager.create_goal(
    description="Implement feature X",
    metadata={
        "component": "frontend",
        "sprint": "sprint-10",
        "assignee": "john@example.com",
        "estimated_hours": 8,
        "tags": ["ui", "enhancement"]
    }
)
```

### 7. Monitor Progress Regularly

```python
# Check progress every 10 seconds
while True:
    goal = await goal_manager.get_goal(goal_id)
    if goal.status in [GoalStatus.COMPLETE, GoalStatus.FAILED]:
        break
    print(f"Progress: {goal.progress * 100:.1f}%")
    await asyncio.sleep(10)
```

---

**Status**: Production Ready ✅  
**Version**: 1.0.0  
**Last Updated**: 2024-01-15  
**Maintainer**: Agent_Guru Team
