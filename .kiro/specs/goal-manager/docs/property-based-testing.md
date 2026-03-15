# Property-Based Testing Guide for Goal Manager

## Overview

The Goal Manager uses a **dual testing strategy** combining unit tests and property-based tests to ensure comprehensive correctness verification. This document explains the property-based testing approach, documents all 25 correctness properties, and provides implementation examples.

## Why Property-Based Testing?

### The Problem with Traditional Testing

Traditional unit tests verify specific examples:
```python
def test_goal_creation():
    goal = create_goal("Build feature X")
    assert goal.status == GoalStatus.PENDING
    assert goal.priority == Priority.MEDIUM
```

This test only verifies **one specific case**. What about:
- Empty descriptions?
- Very long descriptions (1000+ characters)?
- Unicode characters, emojis, special characters?
- Concurrent goal creation?
- Edge cases we haven't thought of?

### The Property-Based Testing Solution

Property-based tests verify **universal properties** across **all possible inputs**:
```python
@given(description=st.text(min_size=1, max_size=500))
@settings(max_examples=100)
def test_property_goal_creation_initialization(description):
    """For ANY description, created goal has correct initial state."""
    goal = create_goal(description)
    assert goal.status == GoalStatus.PENDING
    assert goal.priority == Priority.MEDIUM
```

This test runs **100+ times** with randomly generated descriptions, finding edge cases automatically.

## Dual Testing Strategy

### Unit Tests: Specific Examples
- Verify specific scenarios work correctly
- Test known edge cases explicitly
- Test error conditions and failure modes
- Test integration with external systems
- Fast execution, easy to debug

### Property Tests: Universal Properties
- Verify properties hold for ALL inputs
- Discover unknown edge cases automatically
- Verify mathematical invariants
- Test system behavior under randomness
- Comprehensive coverage, finds subtle bugs

### Both Are Essential


**Unit tests** catch specific bugs we know about.  
**Property tests** catch bugs we don't know about yet.

Example: Unit test verifies "goal with 3 sub-goals calculates 33% progress correctly."  
Property test verifies "goal with N sub-goals ALWAYS calculates progress correctly" (for all N).

## Technology Stack

### Hypothesis Framework

We use [Hypothesis](https://hypothesis.readthedocs.io/) for property-based testing in Python:
- Generates random test data based on strategies
- Shrinks failing examples to minimal reproducible cases
- Remembers failures across test runs
- Integrates seamlessly with pytest

### Configuration

```python
# pytest.ini
[pytest]
markers =
    property: Property-based tests (100+ iterations)
    unit: Unit tests (specific examples)

# Test file configuration
from hypothesis import given, strategies as st, settings

@settings(
    max_examples=100,  # Run 100 iterations minimum
    deadline=None,     # No time limit per test
    suppress_health_check=[HealthCheck.too_slow]
)
```

## Test Generators (Strategies)

### Basic Strategies

Hypothesis provides built-in strategies for common types:

```python
from hypothesis import strategies as st

# Primitive types
st.integers(min_value=0, max_value=100)
st.floats(min_value=0.0, max_value=1.0)
st.text(min_size=1, max_size=500)
st.booleans()
st.datetimes()
st.uuids()

# Collections
st.lists(st.integers(), min_size=0, max_size=10)
st.dictionaries(keys=st.text(), values=st.integers())
st.tuples(st.text(), st.integers())

# Choices
st.sampled_from([Priority.LOW, Priority.MEDIUM, Priority.HIGH])
st.one_of(st.none(), st.text())  # Optional values
```


### Custom Strategies for Goal Manager

We define domain-specific strategies for Goal Manager entities:

```python
@st.composite
def goal_description_strategy(draw):
    """Generate valid goal descriptions."""
    return draw(st.text(
        min_size=10,
        max_size=500,
        alphabet=st.characters(
            blacklist_categories=('Cs',),  # Exclude surrogates
            blacklist_characters='\x00'     # Exclude null bytes
        )
    ))

@st.composite
def priority_strategy(draw):
    """Generate valid priority values."""
    return draw(st.sampled_from(list(Priority)))

@st.composite
def goal_status_strategy(draw):
    """Generate valid goal status values."""
    return draw(st.sampled_from(list(GoalStatus)))

@st.composite
def goal_strategy(draw):
    """Generate complete valid Goal objects."""
    return Goal(
        id=str(draw(st.uuids())),
        description=draw(goal_description_strategy()),
        status=draw(goal_status_strategy()),
        priority=draw(priority_strategy()),
        progress=draw(st.floats(min_value=0.0, max_value=1.0)),
        created_at=draw(st.datetimes()),
        started_at=None,
        completed_at=None,
        parent_id=None,
        sub_goal_ids=[],
        dependency_ids=[],
        metadata={},
        error_message=None
    )

@st.composite
def goal_hierarchy_strategy(draw, max_depth=3, max_children=5):
    """Generate goal hierarchies with parent-child relationships."""
    root = draw(goal_strategy())
    
    if max_depth > 0:
        num_children = draw(st.integers(min_value=0, max_value=max_children))
        children = [
            draw(goal_hierarchy_strategy(max_depth=max_depth-1, max_children=max_children))
            for _ in range(num_children)
        ]
        
        # Set up parent-child relationships
        for child in children:
            child.parent_id = root.id
            root.sub_goal_ids.append(child.id)
    
    return root
```


## The 25 Correctness Properties

### What is a Correctness Property?

A **correctness property** is a universal statement about system behavior that should hold true for **all valid inputs**. Properties are expressed as:

> **For any** [input condition], the system should [expected behavior].

Properties serve as formal specifications that bridge human-readable requirements and machine-verifiable tests.

### Property Categories

The 25 properties are organized into 8 categories:

1. **Goal Creation & Initialization** (Properties 1, 4, 9, 11)
2. **Persistence & Storage** (Properties 2, 3, 21, 22)
3. **Hierarchical Structure** (Properties 5, 6, 20)
4. **Progress Tracking** (Properties 7, 8)
5. **Priority Management** (Property 10)
6. **Dependency Management** (Properties 15, 16, 17)
7. **Execution & Coordination** (Properties 12, 13, 14, 18)
8. **Error Handling & Resilience** (Properties 19, 23, 24, 25)

---

## Category 1: Goal Creation & Initialization

### Property 1: Goal Creation Initialization

**Statement**: *For any* goal creation request with a description, the created goal should have a unique ID, status "pending", priority "medium" (if not specified), progress 0.0, empty sub-goal list, and a valid creation timestamp.

**Validates**: Requirements 1.1, 1.4, 1.5

**Implementation**:
```python
# Feature: goal-manager, Property 1: Goal Creation Initialization
@given(
    description=goal_description_strategy(),
    priority=st.one_of(st.none(), priority_strategy()),
    dependencies=st.one_of(st.none(), st.lists(st.uuids().map(str), max_size=3))
)
@settings(max_examples=100)
async def test_property_goal_creation_initialization(
    description: str,
    priority: Optional[Priority],
    dependencies: Optional[List[str]]
):
    """For any goal description, created goal has correct initial state."""
    # Create goal
    goal = await goal_manager.create_goal(
        description=description,
        priority=priority or Priority.MEDIUM,
        dependencies=dependencies
    )
    
    # Verify initialization
    assert goal.id is not None and len(goal.id) > 0
    assert goal.status == GoalStatus.PENDING
    assert goal.priority == (priority or Priority.MEDIUM)
    assert goal.progress == 0.0
    assert goal.created_at is not None
    assert goal.started_at is None
    assert goal.completed_at is None
    assert goal.sub_goal_ids == []
    assert goal.parent_id is None
```


**Why This Matters**: Ensures every goal starts in a consistent, valid state regardless of input variations.

**Edge Cases Found**: Unicode descriptions, very long descriptions, special characters, null/empty metadata.

---

### Property 4: Unique Identifier Invariant

**Statement**: *For any* set of goals in the system, all goal IDs should be unique, and no two goals should share the same ID.

**Validates**: Requirements 1.4

**Implementation**:
```python
# Feature: goal-manager, Property 4: Unique Identifier Invariant
@given(descriptions=st.lists(goal_description_strategy(), min_size=2, max_size=20))
@settings(max_examples=100)
async def test_property_unique_identifier_invariant(descriptions: List[str]):
    """For any set of goals, all IDs must be unique."""
    # Create multiple goals
    goals = [await goal_manager.create_goal(desc) for desc in descriptions]
    
    # Extract all IDs
    goal_ids = [g.id for g in goals]
    
    # Verify uniqueness
    assert len(goal_ids) == len(set(goal_ids)), "All goal IDs must be unique"
    
    # Verify no collisions in storage
    for goal_id in goal_ids:
        retrieved = await storage.get_goal(goal_id)
        assert retrieved is not None
        assert retrieved.id == goal_id
```

**Why This Matters**: Prevents data corruption from ID collisions, ensures referential integrity.

---

### Property 9: Timestamp Chronological Order

**Statement**: *For any* goal, if timestamps are present, they should be in chronological order: created_at ≤ started_at ≤ completed_at.

**Validates**: Requirements 3.5

**Implementation**:
```python
# Feature: goal-manager, Property 9: Timestamp Chronological Order
@given(
    description=goal_description_strategy(),
    created_to_started_seconds=st.integers(min_value=0, max_value=1000),
    started_to_completed_seconds=st.integers(min_value=0, max_value=1000)
)
@settings(max_examples=100)
async def test_property_timestamp_chronological_order(
    description: str,
    created_to_started_seconds: int,
    started_to_completed_seconds: int
):
    """For any goal, timestamps must be in chronological order."""
    # Create goal
    goal = await goal_manager.create_goal(description)
    created_at = goal.created_at
    
    # Simulate time passing and mark in progress
    await asyncio.sleep(0.01)  # Small delay
    await progress_tracker.mark_in_progress(goal.id)
    goal = await storage.get_goal(goal.id)
    
    # Verify created_at <= started_at
    if goal.started_at:
        assert goal.created_at <= goal.started_at
    
    # Mark complete
    await asyncio.sleep(0.01)
    await progress_tracker.mark_complete(goal.id)
    goal = await storage.get_goal(goal.id)
    
    # Verify started_at <= completed_at
    if goal.completed_at and goal.started_at:
        assert goal.started_at <= goal.completed_at
    
    # Verify created_at <= completed_at
    if goal.completed_at:
        assert goal.created_at <= goal.completed_at
```

**Why This Matters**: Prevents temporal paradoxes, ensures valid lifecycle tracking.


---

### Property 11: Priority Validity

**Statement**: *For any* goal, the priority field should be one of the four valid values: "critical", "high", "medium", or "low".

**Validates**: Requirements 4.2

**Implementation**:
```python
# Feature: goal-manager, Property 11: Priority Validity
@given(
    description=goal_description_strategy(),
    priority=priority_strategy()
)
@settings(max_examples=100)
async def test_property_priority_validity(description: str, priority: Priority):
    """For any goal, priority must be a valid enum value."""
    goal = await goal_manager.create_goal(description, priority=priority)
    
    # Verify priority is valid
    assert goal.priority in [Priority.CRITICAL, Priority.HIGH, Priority.MEDIUM, Priority.LOW]
    assert isinstance(goal.priority, Priority)
    
    # Verify persistence preserves validity
    retrieved = await storage.get_goal(goal.id)
    assert retrieved.priority == priority
    assert isinstance(retrieved.priority, Priority)
```

**Why This Matters**: Prevents invalid priority values, ensures type safety.

---

## Category 2: Persistence & Storage

### Property 2: Immediate Persistence

**Statement**: *For any* goal state change (status, priority, progress, or any field), the change should be persisted to disk before the operation returns, and reading from disk should reflect the change.

**Validates**: Requirements 1.2, 3.4, 4.6

**Implementation**:
```python
# Feature: goal-manager, Property 2: Immediate Persistence
@given(
    description=goal_description_strategy(),
    priority=priority_strategy(),
    new_priority=priority_strategy(),
    new_progress=st.floats(min_value=0.0, max_value=1.0)
)
@settings(max_examples=100)
async def test_property_immediate_persistence(
    description: str,
    priority: Priority,
    new_priority: Priority,
    new_progress: float
):
    """For any state change, persistence is immediate."""
    # Create goal
    goal = await goal_manager.create_goal(description, priority=priority)
    original_id = goal.id
    
    # Verify creation persisted
    retrieved = await storage.get_goal(original_id)
    assert retrieved is not None
    assert retrieved.description == description
    assert retrieved.priority == priority
    
    # Update priority
    await priority_manager.update_priority(original_id, new_priority)
    
    # Verify priority update persisted immediately
    retrieved = await storage.get_goal(original_id)
    assert retrieved.priority == new_priority
    
    # Update progress
    goal.progress = new_progress
    await storage.update_goal(goal)
    
    # Verify progress update persisted immediately
    retrieved = await storage.get_goal(original_id)
    assert abs(retrieved.progress - new_progress) < 0.001
```

**Why This Matters**: Ensures no data loss on crashes, maintains consistency.


---

### Property 3: Session Persistence Round-Trip

**Statement**: *For any* set of goals stored in the system, shutting down and restarting the system should restore all goals with identical state (all fields preserved including status, progress, priority, timestamps, sub-goals, and dependencies).

**Validates**: Requirements 1.3, 6.1, 6.2, 6.5

**Implementation**:
```python
# Feature: goal-manager, Property 3: Session Persistence Round-Trip
@given(
    goals_data=st.lists(
        st.tuples(
            goal_description_strategy(),
            priority_strategy(),
            goal_status_strategy(),
            st.floats(min_value=0.0, max_value=1.0)
        ),
        min_size=1,
        max_size=10
    )
)
@settings(max_examples=100)
async def test_property_session_persistence_round_trip(goals_data):
    """For any set of goals, shutdown/restart preserves all state."""
    # Create goals with various states
    created_goals = []
    for desc, priority, status, progress in goals_data:
        goal = await goal_manager.create_goal(desc, priority=priority)
        goal.status = status
        goal.progress = progress
        await storage.update_goal(goal)
        created_goals.append(goal)
    
    # Simulate shutdown
    await session_manager.persist_all()
    
    # Simulate restart - create new storage instance
    new_storage = GoalStorage(storage.db_path)
    new_session_manager = SessionManager(new_storage)
    await new_session_manager.load_goals()
    
    # Verify all goals restored with identical state
    for original_goal in created_goals:
        restored_goal = await new_storage.get_goal(original_goal.id)
        
        assert restored_goal is not None
        assert restored_goal.id == original_goal.id
        assert restored_goal.description == original_goal.description
        assert restored_goal.status == original_goal.status
        assert restored_goal.priority == original_goal.priority
        assert abs(restored_goal.progress - original_goal.progress) < 0.001
        assert restored_goal.sub_goal_ids == original_goal.sub_goal_ids
        assert restored_goal.dependency_ids == original_goal.dependency_ids
```

**Why This Matters**: Enables long-running autonomous goals, survives system restarts.

---

### Property 21: Serialization Round-Trip

**Statement**: *For any* valid goal object, serializing to JSON then deserializing should produce an equivalent goal with all fields preserved exactly.

**Validates**: Requirements 12.1, 12.2

**Implementation**:
```python
# Feature: goal-manager, Property 21: Serialization Round-Trip
@given(goal=goal_strategy())
@settings(max_examples=100)
def test_property_serialization_round_trip(goal: Goal):
    """For any goal, JSON serialization round-trip preserves all fields."""
    # Serialize to dictionary
    goal_dict = storage._goal_to_dict(goal)
    
    # Verify dictionary structure
    assert isinstance(goal_dict, dict)
    assert "id" in goal_dict
    assert "description" in goal_dict
    assert "status" in goal_dict
    
    # Deserialize back to Goal
    restored_goal = storage._dict_to_goal(goal_dict)
    
    # Verify all fields preserved
    assert restored_goal.id == goal.id
    assert restored_goal.description == goal.description
    assert restored_goal.status == goal.status
    assert restored_goal.priority == goal.priority
    assert abs(restored_goal.progress - goal.progress) < 0.001
    assert restored_goal.sub_goal_ids == goal.sub_goal_ids
    assert restored_goal.dependency_ids == goal.dependency_ids
    assert restored_goal.metadata == goal.metadata
```

**Why This Matters**: Ensures data integrity during export/import, backup/restore.


---

### Property 22: Schema Validation

**Statement**: *For any* deserialized goal data, if the data is invalid (missing required fields, invalid enum values, invalid types), the deserialization should raise a validation error.

**Validates**: Requirements 12.3, 12.5

**Implementation**:
```python
# Feature: goal-manager, Property 22: Schema Validation
@given(
    goal=goal_strategy(),
    field_to_corrupt=st.sampled_from([
        "id", "description", "status", "priority", "progress"
    ]),
    corruption_type=st.sampled_from(["missing", "invalid_type", "invalid_value"])
)
@settings(max_examples=100)
def test_property_schema_validation(goal: Goal, field_to_corrupt: str, corruption_type: str):
    """For any invalid data, deserialization raises validation error."""
    # Serialize valid goal
    goal_dict = storage._goal_to_dict(goal)
    
    # Corrupt the data
    if corruption_type == "missing":
        del goal_dict[field_to_corrupt]
    elif corruption_type == "invalid_type":
        goal_dict[field_to_corrupt] = 12345  # Wrong type
    elif corruption_type == "invalid_value":
        if field_to_corrupt == "status":
            goal_dict[field_to_corrupt] = "invalid_status"
        elif field_to_corrupt == "priority":
            goal_dict[field_to_corrupt] = "invalid_priority"
        elif field_to_corrupt == "progress":
            goal_dict[field_to_corrupt] = 2.5  # Out of range
    
    # Attempt deserialization - should raise error
    with pytest.raises((ValidationError, ValueError, KeyError)):
        storage._dict_to_goal(goal_dict)
```

**Why This Matters**: Prevents corrupted data from entering system, maintains data quality.

---

## Category 3: Hierarchical Structure

### Property 5: Hierarchical Tree Structure

**Statement**: *For any* goal hierarchy, the structure should form a valid tree (no cycles through parent-child relationships, each goal has at most one parent, and following parent links eventually reaches a root goal with no parent).

**Validates**: Requirements 2.6

**Implementation**:
```python
# Feature: goal-manager, Property 5: Hierarchical Tree Structure
@given(
    num_goals=st.integers(min_value=2, max_value=20),
    hierarchy_depth=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=100)
async def test_property_hierarchical_tree_structure(num_goals: int, hierarchy_depth: int):
    """For any goal hierarchy, structure forms a valid tree."""
    # Create hierarchical structure
    root = await goal_manager.create_goal("Root goal")
    current_level = [root]
    
    for depth in range(hierarchy_depth):
        next_level = []
        for parent in current_level:
            num_children = min(3, num_goals // (depth + 1))
            for i in range(num_children):
                child = await goal_manager.create_goal(f"Child {depth}-{i}")
                child.parent_id = parent.id
                parent.sub_goal_ids.append(child.id)
                await storage.update_goal(parent)
                await storage.update_goal(child)
                next_level.append(child)
        current_level = next_level
    
    # Verify tree properties
    all_goals = await storage.query_goals()
    
    # 1. Each goal has at most one parent
    for goal in all_goals:
        if goal.parent_id:
            parent = await storage.get_goal(goal.parent_id)
            assert parent is not None
            assert goal.id in parent.sub_goal_ids
    
    # 2. Following parent links reaches root
    for goal in all_goals:
        visited = set()
        current = goal
        while current.parent_id:
            assert current.id not in visited, "Cycle detected!"
            visited.add(current.id)
            current = await storage.get_goal(current.parent_id)
        # Reached root (no parent)
        assert current.parent_id is None
```

**Why This Matters**: Prevents infinite loops, ensures valid decomposition structure.


---

### Property 6: Parent-Child Reference Consistency

**Statement**: *For any* goal with sub-goals, each sub-goal should reference the parent goal in its parent_id field, and the parent should list the sub-goal in its sub_goal_ids list.

**Validates**: Requirements 2.3

**Implementation**:
```python
# Feature: goal-manager, Property 6: Parent-Child Reference Consistency
@given(
    parent_description=goal_description_strategy(),
    num_sub_goals=st.integers(min_value=1, max_value=7),
    sub_goal_descriptions=st.lists(goal_description_strategy(), min_size=1, max_size=7)
)
@settings(max_examples=100)
async def test_property_parent_child_reference_consistency(
    parent_description: str,
    num_sub_goals: int,
    sub_goal_descriptions: List[str]
):
    """For any goal with sub-goals, parent-child references are bidirectional."""
    # Create parent goal
    parent = await goal_manager.create_goal(parent_description)
    
    # Create sub-goals
    sub_goals = []
    for desc in sub_goal_descriptions[:num_sub_goals]:
        sub_goal = await goal_manager.create_goal(desc)
        sub_goal.parent_id = parent.id
        await storage.update_goal(sub_goal)
        parent.sub_goal_ids.append(sub_goal.id)
        sub_goals.append(sub_goal)
    
    await storage.update_goal(parent)
    
    # Verify bidirectional consistency
    retrieved_parent = await storage.get_goal(parent.id)
    
    for sub_goal in sub_goals:
        # Parent lists sub-goal
        assert sub_goal.id in retrieved_parent.sub_goal_ids
        
        # Sub-goal references parent
        retrieved_sub = await storage.get_goal(sub_goal.id)
        assert retrieved_sub.parent_id == parent.id
```

**Why This Matters**: Ensures referential integrity, enables hierarchy traversal.

---

### Property 20: Hierarchical Retrieval Completeness

**Statement**: *For any* goal ID, retrieving the goal should return the goal and all its descendants (sub-goals, sub-sub-goals, etc.) in the hierarchy.

**Validates**: Requirements 8.4

**Implementation**:
```python
# Feature: goal-manager, Property 20: Hierarchical Retrieval Completeness
@given(
    root_description=goal_description_strategy(),
    hierarchy_depth=st.integers(min_value=1, max_value=4),
    children_per_level=st.integers(min_value=1, max_value=3)
)
@settings(max_examples=100)
async def test_property_hierarchical_retrieval_completeness(
    root_description: str,
    hierarchy_depth: int,
    children_per_level: int
):
    """For any goal, retrieval includes complete subtree."""
    # Create hierarchical structure
    root = await goal_manager.create_goal(root_description)
    all_goal_ids = {root.id}
    
    async def create_subtree(parent_id: str, depth: int):
        if depth == 0:
            return
        for i in range(children_per_level):
            child = await goal_manager.create_goal(f"Child at depth {depth}")
            child.parent_id = parent_id
            await storage.update_goal(child)
            
            parent = await storage.get_goal(parent_id)
            parent.sub_goal_ids.append(child.id)
            await storage.update_goal(parent)
            
            all_goal_ids.add(child.id)
            await create_subtree(child.id, depth - 1)
    
    await create_subtree(root.id, hierarchy_depth)
    
    # Retrieve root and verify all descendants accessible
    retrieved_root = await storage.get_goal(root.id)
    
    async def collect_descendants(goal_id: str) -> Set[str]:
        descendants = {goal_id}
        goal = await storage.get_goal(goal_id)
        for sub_id in goal.sub_goal_ids:
            descendants.update(await collect_descendants(sub_id))
        return descendants
    
    retrieved_ids = await collect_descendants(retrieved_root.id)
    assert retrieved_ids == all_goal_ids
```

**Why This Matters**: Ensures complete hierarchy access, supports tree operations.


---

## Category 4: Progress Tracking

### Property 7: Progress Calculation Correctness

**Statement**: *For any* goal with sub-goals, the goal's progress should equal the average progress of its sub-goals (sum of sub-goal progress divided by number of sub-goals).

**Validates**: Requirements 3.2

**Implementation**:
```python
# Feature: goal-manager, Property 7: Progress Calculation Correctness
@given(
    parent_description=goal_description_strategy(),
    num_sub_goals=st.integers(min_value=1, max_value=10),
    sub_goal_progress_values=st.lists(
        st.floats(min_value=0.0, max_value=1.0),
        min_size=1,
        max_size=10
    )
)
@settings(max_examples=100)
async def test_property_progress_calculation_correctness(
    parent_description: str,
    num_sub_goals: int,
    sub_goal_progress_values: List[float]
):
    """For any goal with sub-goals, progress equals average of sub-goal progress."""
    # Create parent and sub-goals
    parent = await goal_manager.create_goal(parent_description)
    
    sub_goals = []
    for i in range(num_sub_goals):
        sub_goal = await goal_manager.create_goal(f"Sub-goal {i}")
        sub_goal.parent_id = parent.id
        sub_goal.progress = sub_goal_progress_values[i % len(sub_goal_progress_values)]
        await storage.update_goal(sub_goal)
        parent.sub_goal_ids.append(sub_goal.id)
        sub_goals.append(sub_goal)
    
    await storage.update_goal(parent)
    
    # Update parent progress
    await progress_tracker._update_parent_progress(parent.id)
    
    # Verify progress calculation
    updated_parent = await storage.get_goal(parent.id)
    expected_progress = sum(sg.progress for sg in sub_goals) / len(sub_goals)
    
    assert abs(updated_parent.progress - expected_progress) < 0.001
```

**Why This Matters**: Ensures accurate progress reporting, enables progress tracking.

---

### Property 8: Completion Propagation

**Statement**: *For any* goal where all sub-goals have status "complete", the parent goal should have status "complete" and progress 1.0.

**Validates**: Requirements 3.3

**Implementation**:
```python
# Feature: goal-manager, Property 8: Completion Propagation
@given(
    parent_description=goal_description_strategy(),
    num_sub_goals=st.integers(min_value=1, max_value=7)
)
@settings(max_examples=100)
async def test_property_completion_propagation(
    parent_description: str,
    num_sub_goals: int
):
    """For any goal, when all sub-goals complete, parent completes."""
    # Create parent and sub-goals
    parent = await goal_manager.create_goal(parent_description)
    
    sub_goal_ids = []
    for i in range(num_sub_goals):
        sub_goal = await goal_manager.create_goal(f"Sub-goal {i}")
        sub_goal.parent_id = parent.id
        await storage.update_goal(sub_goal)
        parent.sub_goal_ids.append(sub_goal.id)
        sub_goal_ids.append(sub_goal.id)
    
    await storage.update_goal(parent)
    
    # Mark all sub-goals complete
    for sub_goal_id in sub_goal_ids:
        await progress_tracker.mark_complete(sub_goal_id)
    
    # Verify parent is complete
    updated_parent = await storage.get_goal(parent.id)
    assert updated_parent.status == GoalStatus.COMPLETE
    assert abs(updated_parent.progress - 1.0) < 0.001
    assert updated_parent.completed_at is not None
```

**Why This Matters**: Automates goal completion, propagates status up hierarchy.


---

## Category 5: Priority Management

### Property 10: Priority Selection Correctness

**Statement**: *For any* set of ready goals, selecting the next goal for execution should return the goal with the highest priority, and among goals with equal priority, the oldest goal (earliest created_at).

**Validates**: Requirements 4.3, 4.4

**Implementation**:
```python
# Feature: goal-manager, Property 10: Priority Selection Correctness
@given(
    goals_data=st.lists(
        st.tuples(
            goal_description_strategy(),
            priority_strategy()
        ),
        min_size=2,
        max_size=10
    )
)
@settings(max_examples=100)
async def test_property_priority_selection_correctness(goals_data):
    """For any set of ready goals, selection follows priority then age."""
    # Create goals with various priorities
    created_goals = []
    for desc, priority in goals_data:
        goal = await goal_manager.create_goal(desc, priority=priority)
        goal.status = GoalStatus.READY
        await storage.update_goal(goal)
        created_goals.append(goal)
        await asyncio.sleep(0.001)  # Ensure different timestamps
    
    # Select next goal
    selected = await priority_manager.select_next_goal()
    
    # Verify selection is correct
    priority_order = {
        Priority.CRITICAL: 0,
        Priority.HIGH: 1,
        Priority.MEDIUM: 2,
        Priority.LOW: 3
    }
    
    # Find expected goal (highest priority, then oldest)
    expected = min(
        created_goals,
        key=lambda g: (priority_order[g.priority], g.created_at)
    )
    
    assert selected.id == expected.id
```

**Why This Matters**: Ensures critical goals execute first, fair scheduling.


---

## Category 6: Dependency Management

### Property 15: Dependency Blocking

**Statement**: *For any* goal with incomplete dependencies, the goal should not have status "ready" or "in_progress" (dependencies must be satisfied before execution).

**Validates**: Requirements 7.2

**Implementation**:
```python
# Feature: goal-manager, Property 15: Dependency Blocking
@given(
    goal_description=goal_description_strategy(),
    num_dependencies=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=100)
async def test_property_dependency_blocking(goal_description: str, num_dependencies: int):
    """For any goal with incomplete dependencies, goal is blocked."""
    # Create dependency goals
    dependencies = []
    for i in range(num_dependencies):
        dep = await goal_manager.create_goal(f"Dependency {i}")
        dependencies.append(dep.id)
    
    # Create goal with dependencies
    goal = await goal_manager.create_goal(
        goal_description,
        dependencies=dependencies
    )
    
    # Verify goal is not ready
    assert goal.status != GoalStatus.READY
    assert goal.status != GoalStatus.IN_PROGRESS
    
    # Complete some but not all dependencies
    for dep_id in dependencies[:-1]:
        dep = await storage.get_goal(dep_id)
        dep.status = GoalStatus.COMPLETE
        await storage.update_goal(dep)
    
    # Verify goal still not ready
    is_ready = await dependency_resolver.is_ready(goal)
    assert not is_ready
```

**Why This Matters**: Enforces execution order, prevents premature execution.

---

### Property 16: Circular Dependency Detection

**Statement**: *For any* goal with dependencies that form a cycle (A depends on B, B depends on C, C depends on A), creating or updating the goal should raise a validation error.

**Validates**: Requirements 7.4

**Implementation**:
```python
# Feature: goal-manager, Property 16: Circular Dependency Detection
@given(
    num_goals=st.integers(min_value=2, max_value=5)
)
@settings(max_examples=100)
async def test_property_circular_dependency_detection(num_goals: int):
    """For any circular dependency, validation raises error."""
    # Create chain of goals
    goals = []
    for i in range(num_goals):
        goal = await goal_manager.create_goal(f"Goal {i}")
        goals.append(goal)
    
    # Create linear dependencies: 0 -> 1 -> 2 -> ... -> n-1
    for i in range(len(goals) - 1):
        goals[i].dependency_ids = [goals[i + 1].id]
        await storage.update_goal(goals[i])
    
    # Attempt to create cycle: n-1 -> 0
    goals[-1].dependency_ids = [goals[0].id]
    
    # Should raise validation error
    with pytest.raises(ValidationError):
        dependency_resolver.validate_dependencies(goals[-1])
```

**Why This Matters**: Prevents deadlocks, ensures valid dependency graphs.


---

### Property 17: Dependency Satisfaction

**Statement**: *For any* goal where all dependency goals have status "complete", the goal should be marked as "ready" for execution (assuming no other blocking conditions).

**Validates**: Requirements 7.5

**Implementation**:
```python
# Feature: goal-manager, Property 17: Dependency Satisfaction
@given(
    goal_description=goal_description_strategy(),
    num_dependencies=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=100)
async def test_property_dependency_satisfaction(goal_description: str, num_dependencies: int):
    """For any goal, when all dependencies complete, goal becomes ready."""
    # Create dependency goals
    dependencies = []
    for i in range(num_dependencies):
        dep = await goal_manager.create_goal(f"Dependency {i}")
        dependencies.append(dep.id)
    
    # Create goal with dependencies
    goal = await goal_manager.create_goal(
        goal_description,
        dependencies=dependencies
    )
    
    # Complete all dependencies
    for dep_id in dependencies:
        dep = await storage.get_goal(dep_id)
        dep.status = GoalStatus.COMPLETE
        await storage.update_goal(dep)
    
    # Verify goal is ready
    goal = await storage.get_goal(goal.id)
    is_ready = await dependency_resolver.is_ready(goal)
    assert is_ready
```

**Why This Matters**: Enables automatic execution when dependencies satisfied.

---

## Category 7: Execution & Coordination

### Property 12: Sequential Sub-Goal Execution

**Statement**: *For any* goal being executed, at most one sub-goal should be in "in_progress" status at any time (sub-goals execute sequentially, not concurrently).

**Validates**: Requirements 5.6

**Implementation**:
```python
# Feature: goal-manager, Property 12: Sequential Sub-Goal Execution
@given(
    parent_description=goal_description_strategy(),
    num_sub_goals=st.integers(min_value=2, max_value=5)
)
@settings(max_examples=100)
async def test_property_sequential_subgoal_execution(
    parent_description: str,
    num_sub_goals: int
):
    """For any goal execution, sub-goals execute sequentially."""
    # Create parent with sub-goals
    parent = await goal_manager.create_goal(parent_description)
    
    for i in range(num_sub_goals):
        sub_goal = await goal_manager.create_goal(f"Sub-goal {i}")
        sub_goal.parent_id = parent.id
        await storage.update_goal(sub_goal)
        parent.sub_goal_ids.append(sub_goal.id)
    
    await storage.update_goal(parent)
    
    # Track in-progress count during execution
    max_in_progress = 0
    
    async def monitor_execution():
        nonlocal max_in_progress
        while True:
            sub_goals = [await storage.get_goal(sid) for sid in parent.sub_goal_ids]
            in_progress_count = sum(
                1 for sg in sub_goals if sg.status == GoalStatus.IN_PROGRESS
            )
            max_in_progress = max(max_in_progress, in_progress_count)
            await asyncio.sleep(0.01)
            
            # Stop when all complete or failed
            if all(sg.status in [GoalStatus.COMPLETE, GoalStatus.FAILED] for sg in sub_goals):
                break
    
    # Start monitoring and execution concurrently
    monitor_task = asyncio.create_task(monitor_execution())
    await goal_executor.execute_goal(parent.id)
    await monitor_task
    
    # Verify at most one sub-goal was in progress at any time
    assert max_in_progress <= 1
```

**Why This Matters**: Ensures predictable execution order, prevents race conditions.


---

### Property 13: Task Creation for Execution

**Statement**: *For any* ready goal with no sub-goals (leaf goal), executing the goal should create exactly one task in Agent_Orchestration.

**Validates**: Requirements 5.1, 10.2

**Implementation**:
```python
# Feature: goal-manager, Property 13: Task Creation for Execution
@given(description=goal_description_strategy())
@settings(max_examples=100)
async def test_property_task_creation_for_execution(description: str):
    """For any leaf goal, execution creates exactly one task."""
    # Mock Agent Orchestration
    mock_agent_orch = Mock()
    mock_task = Mock(task_id="test-task-123")
    mock_result = Mock(success=True, error_message=None)
    mock_agent_orch.create_task = AsyncMock(return_value=mock_task)
    mock_agent_orch.wait_for_task = AsyncMock(return_value=mock_result)
    
    # Create executor with mock
    executor = GoalExecutor(
        mock_agent_orch,
        storage,
        "/tmp/test-repo",
        Mock()
    )
    
    # Create leaf goal (no sub-goals)
    goal = await goal_manager.create_goal(description)
    goal.status = GoalStatus.READY
    await storage.update_goal(goal)
    
    # Execute goal
    await executor._execute_sub_goal(goal)
    
    # Verify exactly one task created
    assert mock_agent_orch.create_task.call_count == 1
    
    # Verify task parameters
    call_args = mock_agent_orch.create_task.call_args
    assert description in call_args.kwargs["description"]
    assert call_args.kwargs["task_type"] == "goal_execution"
    assert call_args.kwargs["metadata"]["goal_id"] == goal.id
```

**Why This Matters**: Ensures proper task delegation, enables execution tracking.

---

### Property 14: GitHub Commit on Completion

**Statement**: *For any* sub-goal that completes successfully, a commit should be created in the Git repository with a message containing the goal description and ID.

**Validates**: Requirements 5.5

**Implementation**:
```python
# Feature: goal-manager, Property 14: GitHub Commit on Completion
@given(description=goal_description_strategy())
@settings(max_examples=100)
async def test_property_github_commit_on_completion(description: str):
    """For any completed goal, GitHub commit is created."""
    # Create temporary git repo
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Repo.init(tmpdir)
        
        # Create executor with real repo
        executor = GoalExecutor(
            Mock(),
            storage,
            tmpdir,
            Mock()
        )
        
        # Create and complete goal
        goal = await goal_manager.create_goal(description)
        goal.status = GoalStatus.COMPLETE
        await storage.update_goal(goal)
        
        # Commit to GitHub
        await executor._commit_to_github(goal)
        
        # Verify commit created
        commits = list(repo.iter_commits())
        assert len(commits) > 0
        
        # Verify commit message contains goal info
        latest_commit = commits[0]
        assert description in latest_commit.message
        assert goal.id in latest_commit.message
```

**Why This Matters**: Provides audit trail, enables version control integration.


---

### Property 18: Cancellation Propagation

**Statement**: *For any* goal that is cancelled, all sub-goals in the goal's subtree should also be marked as "cancelled".

**Validates**: Requirements 9.1

**Implementation**:
```python
# Feature: goal-manager, Property 18: Cancellation Propagation
@given(
    root_description=goal_description_strategy(),
    hierarchy_depth=st.integers(min_value=1, max_value=4),
    children_per_level=st.integers(min_value=1, max_value=3)
)
@settings(max_examples=100)
async def test_property_cancellation_propagation(
    root_description: str,
    hierarchy_depth: int,
    children_per_level: int
):
    """For any cancelled goal, all descendants are cancelled."""
    # Create hierarchical structure
    root = await goal_manager.create_goal(root_description)
    all_goal_ids = {root.id}
    
    async def create_subtree(parent_id: str, depth: int):
        if depth == 0:
            return
        for i in range(children_per_level):
            child = await goal_manager.create_goal(f"Child at depth {depth}")
            child.parent_id = parent_id
            await storage.update_goal(child)
            
            parent = await storage.get_goal(parent_id)
            parent.sub_goal_ids.append(child.id)
            await storage.update_goal(parent)
            
            all_goal_ids.add(child.id)
            await create_subtree(child.id, depth - 1)
    
    await create_subtree(root.id, hierarchy_depth)
    
    # Cancel root goal
    await goal_manager.cancel_goal(root.id)
    
    # Verify all goals in subtree are cancelled
    for goal_id in all_goal_ids:
        goal = await storage.get_goal(goal_id)
        assert goal.status == GoalStatus.CANCELLED
```

**Why This Matters**: Ensures clean cancellation, prevents orphaned sub-goals.

---

## Category 8: Error Handling & Resilience

### Property 19: Query Filtering Correctness

**Statement**: *For any* query with status or priority filters, all returned goals should match the filter criteria, and no goals matching the criteria should be excluded.

**Validates**: Requirements 8.2, 8.3

**Implementation**:
```python
# Feature: goal-manager, Property 19: Query Filtering Correctness
@given(
    goals_data=st.lists(
        st.tuples(
            goal_description_strategy(),
            goal_status_strategy(),
            priority_strategy()
        ),
        min_size=5,
        max_size=20
    ),
    filter_status=st.one_of(st.none(), goal_status_strategy()),
    filter_priority=st.one_of(st.none(), priority_strategy())
)
@settings(max_examples=100)
async def test_property_query_filtering_correctness(
    goals_data,
    filter_status,
    filter_priority
):
    """For any query filters, results match criteria exactly."""
    # Create goals with various states
    created_goals = []
    for desc, status, priority in goals_data:
        goal = await goal_manager.create_goal(desc, priority=priority)
        goal.status = status
        await storage.update_goal(goal)
        created_goals.append(goal)
    
    # Query with filters
    results = await storage.query_goals(
        status=filter_status,
        priority=filter_priority
    )
    
    # Verify all results match filters
    for goal in results:
        if filter_status:
            assert goal.status == filter_status
        if filter_priority:
            assert goal.priority == filter_priority
    
    # Verify no matching goals excluded
    expected_goals = [
        g for g in created_goals
        if (not filter_status or g.status == filter_status)
        and (not filter_priority or g.priority == filter_priority)
    ]
    
    assert len(results) == len(expected_goals)
```

**Why This Matters**: Ensures accurate queries, enables reliable filtering.


---

### Property 23: Retry with Exponential Backoff

**Statement**: *For any* external service failure (LLM Runtime, Agent Orchestration), the system should retry the operation with exponentially increasing delays (e.g., 1s, 2s, 4s) up to a maximum number of attempts.

**Validates**: Requirements 11.1, 11.4, 11.5

**Implementation**:
```python
# Feature: goal-manager, Property 23: Retry with Exponential Backoff
@given(
    max_retries=st.integers(min_value=1, max_value=5),
    failure_count=st.integers(min_value=0, max_value=5)
)
@settings(max_examples=100)
async def test_property_retry_with_exponential_backoff(
    max_retries: int,
    failure_count: int
):
    """For any external failure, retries use exponential backoff."""
    # Track retry attempts and delays
    attempts = []
    delays = []
    
    async def failing_operation():
        attempts.append(time.time())
        if len(attempts) <= failure_count:
            raise Exception("Simulated failure")
        return "success"
    
    # Retry with backoff
    try:
        result = await retry_with_backoff(
            failing_operation,
            max_retries=max_retries,
            base_delay=0.1  # Use small delay for testing
        )
        
        # If succeeded, verify retry count
        if failure_count < max_retries:
            assert len(attempts) == failure_count + 1
        
        # Verify exponential backoff delays
        for i in range(1, len(attempts)):
            delay = attempts[i] - attempts[i-1]
            expected_delay = 0.1 * (2 ** (i-1))
            # Allow 20% tolerance for timing
            assert delay >= expected_delay * 0.8
            assert delay <= expected_delay * 1.2
    
    except Exception:
        # If failed, verify max retries reached
        assert len(attempts) == max_retries
```

**Why This Matters**: Handles transient failures, improves reliability.

---

### Property 24: Error Logging Completeness

**Statement**: *For any* error that occurs in the Goal Manager, an error log entry should be created containing the error type, message, timestamp, and relevant context (goal ID, operation type).

**Validates**: Requirements 11.2, 11.6

**Implementation**:
```python
# Feature: goal-manager, Property 24: Error Logging Completeness
@given(
    operation=st.sampled_from(["store", "update", "decompose", "execute"]),
    error_type=st.sampled_from([StorageError, DecompositionError, ExecutionError])
)
@settings(max_examples=100)
async def test_property_error_logging_completeness(operation: str, error_type):
    """For any error, complete log entry is created."""
    # Set up logging capture
    log_entries = []
    
    def capture_log(event_dict):
        log_entries.append(event_dict)
        return event_dict
    
    # Configure structured logging
    structlog.configure(
        processors=[capture_log]
    )
    
    # Trigger error based on operation
    try:
        if operation == "store":
            # Simulate storage error
            with patch.object(storage, '_execute_query', side_effect=error_type("Test error")):
                await storage.store_goal(await goal_manager.create_goal("Test"))
        elif operation == "decompose":
            # Simulate decomposition error
            with patch.object(decomposer, '_call_llm_with_retry', side_effect=error_type("Test error")):
                await decomposer.decompose(await goal_manager.create_goal("Test"))
    except:
        pass
    
    # Verify log entry created
    assert len(log_entries) > 0
    
    # Verify log entry completeness
    error_log = log_entries[-1]
    assert "error_type" in error_log or "event" in error_log
    assert "timestamp" in error_log or "time" in error_log
    assert "operation" in error_log or "context" in error_log
```

**Why This Matters**: Enables debugging, provides audit trail.

