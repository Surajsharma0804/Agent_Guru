# Property-Based Testing Examples (Continued)

## Property 25: Corruption Recovery

**Statement**: *For any* goal with corrupted data detected during loading, the system should either successfully recover the goal or mark it as failed with an appropriate error message (no crashes or data loss).

**Validates**: Requirements 6.4, 11.3

**Implementation**:
```python
# Feature: goal-manager, Property 25: Corruption Recovery
@given(
    goal=goal_strategy(),
    corruption_type=st.sampled_from([
        "missing_id",
        "missing_description",
        "invalid_timestamps",
        "invalid_progress",
        "malformed_json"
    ])
)
@settings(max_examples=100)
async def test_property_corruption_recovery(goal: Goal, corruption_type: str):
    """For any corrupted goal, system recovers or marks failed."""
    # Store valid goal
    await storage.store_goal(goal)
    
    # Corrupt the data in database
    conn = sqlite3.connect(storage.db_path)
    cursor = conn.cursor()
    
    if corruption_type == "missing_id":
        cursor.execute("UPDATE goals SET id = NULL WHERE id = ?", (goal.id,))
    elif corruption_type == "missing_description":
        cursor.execute("UPDATE goals SET description = NULL WHERE id = ?", (goal.id,))
    elif corruption_type == "invalid_timestamps":
        cursor.execute(
            "UPDATE goals SET started_at = ?, completed_at = ? WHERE id = ?",
            ("2020-01-01", "2019-01-01", goal.id)  # completed before started
        )
    elif corruption_type == "invalid_progress":
        cursor.execute("UPDATE goals SET progress = ? WHERE id = ?", (2.5, goal.id))
    elif corruption_type == "malformed_json":
        cursor.execute("UPDATE goals SET metadata = ? WHERE id = ?", ("invalid json", goal.id))
    
    conn.commit()
    conn.close()
    
    # Attempt to load goals - should not crash
    try:
        await session_manager.load_goals()
        
        # Check if goal was recovered or marked failed
        recovered_goal = await storage.get_goal(goal.id)
        
        if recovered_goal:
            # Either recovered successfully or marked as failed
            if recovered_goal.status == GoalStatus.FAILED:
                assert "corruption" in recovered_goal.error_message.lower()
        # If goal not found, it was removed (acceptable)
    
    except Exception as e:
        # Should not crash - fail the test
        pytest.fail(f"System crashed on corrupted data: {e}")
```

**Why This Matters**: Prevents data loss, ensures system stability.

---

## Running Property Tests

### Command Line

```bash
# Run all property tests
pytest -m property

# Run with verbose output
pytest -m property -v

# Run specific property test
pytest -k "test_property_goal_creation_initialization"

# Run with coverage
pytest -m property --cov=Agent_Guru/goal_manager --cov-report=html

# Run with Hypothesis statistics
pytest -m property --hypothesis-show-statistics
```


### Configuration

```python
# pytest.ini
[pytest]
markers =
    property: Property-based tests (100+ iterations)
    unit: Unit tests (specific examples)
    integration: Integration tests
    slow: Slow-running tests

# Hypothesis settings
[tool:pytest]
hypothesis_profile = default

[hypothesis]
max_examples = 100
deadline = None
suppress_health_check = too_slow
```

### Continuous Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest hypothesis pytest-asyncio
      
      - name: Run unit tests
        run: pytest -m unit
      
      - name: Run property tests
        run: pytest -m property --hypothesis-show-statistics
      
      - name: Generate coverage report
        run: pytest --cov=Agent_Guru/goal_manager --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```


---

## Debugging Property Test Failures

### Understanding Shrinking

When Hypothesis finds a failing test case, it automatically **shrinks** the input to the minimal failing example:

```
Original failing input: "Lorem ipsum dolor sit amet consectetur adipiscing elit..."
Shrunk to: "a"

Original failing input: [1, 5, 3, 9, 2, 7, 4, 8, 6]
Shrunk to: [1, 2]
```

This makes debugging much easier by removing irrelevant complexity.

### Example Debugging Session

```python
# Test fails with:
# AssertionError: Progress calculation incorrect
# Falsifying example: test_property_progress_calculation(
#     num_sub_goals=2,
#     sub_goal_progress_values=[0.0, 1.0]
# )

# Hypothesis found the minimal case that breaks the property!
# Now we can debug with this specific input:

@given(...)
def test_property_progress_calculation(...):
    # Add debugging
    print(f"Sub-goals: {num_sub_goals}")
    print(f"Progress values: {sub_goal_progress_values}")
    
    # ... rest of test
```

### Reproducing Failures

Hypothesis remembers failures across runs. To reproduce a specific failure:

```python
@given(...)
@example(num_sub_goals=2, sub_goal_progress_values=[0.0, 1.0])  # Add explicit example
def test_property_progress_calculation(...):
    # This example will always run first
    pass
```


---

## Best Practices

### 1. Write Properties, Not Examples

**Bad** (example-based):
```python
def test_progress_with_three_subgoals():
    # Tests only one specific case
    assert calculate_progress([0.0, 0.5, 1.0]) == 0.5
```

**Good** (property-based):
```python
@given(progress_values=st.lists(st.floats(0.0, 1.0), min_size=1, max_size=10))
def test_progress_calculation(progress_values):
    # Tests all possible cases
    result = calculate_progress(progress_values)
    assert 0.0 <= result <= 1.0
    assert result == sum(progress_values) / len(progress_values)
```

### 2. Use Assumptions to Filter Invalid Inputs

```python
@given(
    numerator=st.integers(),
    denominator=st.integers()
)
def test_division(numerator, denominator):
    assume(denominator != 0)  # Skip invalid cases
    result = numerator / denominator
    assert result * denominator == numerator
```

### 3. Test Invariants, Not Implementation

**Bad** (tests implementation):
```python
def test_uses_sqlite():
    assert isinstance(storage.conn, sqlite3.Connection)
```

**Good** (tests behavior):
```python
@given(goal=goal_strategy())
def test_storage_persistence(goal):
    storage.store(goal)
    retrieved = storage.get(goal.id)
    assert retrieved == goal
```

### 4. Combine Unit and Property Tests

```python
# Unit test: Specific known edge case
def test_empty_sub_goals_list():
    goal = Goal(sub_goal_ids=[])
    assert calculate_progress(goal) == 0.0

# Property test: Universal behavior
@given(goal=goal_strategy())
def test_progress_always_in_range(goal):
    progress = calculate_progress(goal)
    assert 0.0 <= progress <= 1.0
```


### 5. Tag Tests with Feature and Property Number

```python
# Feature: goal-manager, Property 7: Progress Calculation Correctness
@given(...)
def test_property_progress_calculation(...):
    """For any goal with sub-goals, progress equals average."""
    pass
```

This enables:
- Easy traceability to requirements
- Filtering tests by property
- Documentation generation

### 6. Use Realistic Strategies

**Bad** (unrealistic):
```python
@given(description=st.text())  # Includes null bytes, surrogates, etc.
```

**Good** (realistic):
```python
@given(description=st.text(
    min_size=10,
    max_size=500,
    alphabet=st.characters(blacklist_categories=('Cs',))
))
```

### 7. Test Error Paths

```python
@given(
    goal_dict=st.dictionaries(st.text(), st.text()),
    field_to_remove=st.sampled_from(["id", "description", "status"])
)
def test_deserialization_validates_required_fields(goal_dict, field_to_remove):
    if field_to_remove in goal_dict:
        del goal_dict[field_to_remove]
    
    with pytest.raises(ValidationError):
        Goal.from_dict(goal_dict)
```

---

## Common Pitfalls

### 1. Flaky Tests Due to Timing

**Problem**: Tests fail intermittently due to timing issues.

**Solution**: Use deterministic time or add sufficient delays.

```python
# Bad
@given(...)
async def test_timestamp_order(...):
    goal1 = await create_goal("A")
    goal2 = await create_goal("B")
    assert goal1.created_at < goal2.created_at  # Flaky!

# Good
@given(...)
async def test_timestamp_order(...):
    goal1 = await create_goal("A")
    await asyncio.sleep(0.01)  # Ensure time passes
    goal2 = await create_goal("B")
    assert goal1.created_at < goal2.created_at
```


### 2. Tests That Are Too Slow

**Problem**: Property tests take too long to run.

**Solution**: Reduce max_examples or optimize test code.

```python
# Slow
@given(goals=st.lists(goal_strategy(), max_size=100))
@settings(max_examples=100)  # 100 * 100 = 10,000 goals!
def test_query_performance(goals):
    pass

# Fast
@given(goals=st.lists(goal_strategy(), max_size=20))
@settings(max_examples=50)  # 50 * 20 = 1,000 goals
def test_query_performance(goals):
    pass
```

### 3. Overly Constrained Strategies

**Problem**: Strategy generates too few valid examples.

**Solution**: Relax constraints or use `assume()`.

```python
# Bad - too constrained
@given(
    x=st.integers(min_value=1, max_value=10),
    y=st.integers(min_value=1, max_value=10)
)
def test_something(x, y):
    assume(x > y)  # Rejects 50% of inputs
    assume(x % 2 == 0)  # Rejects another 50%
    assume(y % 3 == 0)  # Rejects another 67%
    # Very few valid examples!

# Good - generate valid examples directly
@given(
    y=st.integers(min_value=1, max_value=5).filter(lambda n: n % 3 == 0),
    x_offset=st.integers(min_value=1, max_value=5)
)
def test_something(y, x_offset):
    x = (y + x_offset) * 2  # Ensure x > y and x is even
```

### 4. Non-Deterministic Behavior

**Problem**: Test results vary between runs.

**Solution**: Use Hypothesis's deterministic mode or seed.

```python
# Set seed for reproducibility
@given(...)
@settings(derandomize=True)
def test_something(...):
    pass
```

---

## Summary: Property Testing Checklist

When writing property tests for Goal Manager:

- [ ] Test runs 100+ iterations (`@settings(max_examples=100)`)
- [ ] Test is tagged with feature and property number
- [ ] Test uses appropriate strategies (realistic inputs)
- [ ] Test verifies universal property, not specific example
- [ ] Test includes docstring explaining the property
- [ ] Test handles async operations correctly
- [ ] Test cleans up resources (database, files)
- [ ] Test is deterministic (no flaky failures)
- [ ] Test completes in reasonable time (<5 seconds)
- [ ] Test is documented in this guide

---

## Resources

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Property-Based Testing with Hypothesis](https://hypothesis.works/articles/what-is-property-based-testing/)
- [Choosing Properties for Property-Based Testing](https://fsharpforfunandprofit.com/posts/property-based-testing-2/)
- [Goal Manager Design Document](.kiro/specs/goal-manager/design.md)
- [Goal Manager Requirements](.kiro/specs/goal-manager/requirements.md)

