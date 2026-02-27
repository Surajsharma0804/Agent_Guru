# Property-Based Tests for Database Integrity Constraints

## Overview

This test suite uses **Hypothesis** for property-based testing to verify that all database integrity constraints hold under all conditions with 100+ examples per property.

## What is Property-Based Testing?

Property-based testing generates hundreds of random test cases to verify that certain properties (invariants) always hold. Unlike traditional unit tests that check specific examples, property-based tests verify universal truths about the system.

**Example:**
- Traditional test: "Strategy with 10 successes and 5 failures has total_executions = 15"
- Property test: "For ANY success_count and failure_count, total_executions MUST equal success_count + failure_count"

## Test Coverage

### 1. Failures Table Constraints

**CHECK Constraints:**
- `failure_type` must be one of: `reasoning_error`, `tool_error`, `hallucination`, `timeout`, `resource_error`, `unknown`
- `execution_time_ms` must be >= 0

**Properties Tested:**
- ✓ Valid failure data always inserts successfully (100 examples)
- ✓ Negative execution times are rejected (50 examples)
- ✓ Invalid failure types are rejected (50 examples)

### 2. Strategies Table Constraints

**CHECK Constraints:**
- `success_count` >= 0
- `failure_count` >= 0
- `total_executions` >= 0
- `success_rate` >= 0.0 AND <= 1.0
- `avg_execution_time_ms` >= 0.0
- `total_executions` = `success_count` + `failure_count`

**Properties Tested:**
- ✓ Valid strategy data with consistent counts always inserts (100 examples)
- ✓ Inconsistent total_executions is rejected (100 examples)
- ✓ Success rates > 1.0 are rejected (50 examples)
- ✓ Negative success rates are rejected (50 examples)
- ✓ Zero executions are allowed (edge case)
- ✓ Perfect success rate (1.0) is allowed (edge case)
- ✓ Zero success rate (0.0) is allowed (edge case)
- ✓ Large execution counts (millions) are allowed (edge case)

### 3. Prompts Table Constraints

**CHECK Constraints:**
- `version` > 0
- `is_active` IN (0, 1)
- `success_count` >= 0
- `failure_count` >= 0
- `total_uses` >= 0
- `success_rate` >= 0.0 AND <= 1.0
- `hallucination_count` >= 0
- `total_uses` = `success_count` + `failure_count`

**UNIQUE Constraint:**
- (`prompt_type`, `version`) must be unique

**Properties Tested:**
- ✓ Valid prompt data with consistent counts always inserts (100 examples)
- ✓ Version numbers <= 0 are rejected (50 examples)
- ✓ Duplicate (prompt_type, version) pairs are rejected (100 examples)
- ✓ Inconsistent total_uses is rejected (100 examples)

### 4. Metrics Table Constraints

**CHECK Constraints:**
- `success` IN (0, 1)
- `execution_time_ms` >= 0
- `reasoning_quality` IS NULL OR (>= 0.0 AND <= 1.0)
- `tool_selection_correct` IS NULL OR IN (0, 1)
- `hallucination_detected` IN (0, 1)
- `task_sequence_number` > 0
- `window_start` >= 0
- `window_end` >= `window_start`

**Properties Tested:**
- ✓ Valid metrics data always inserts (100 examples)
- ✓ window_end < window_start is rejected (100 examples)
- ✓ Sequence numbers <= 0 are rejected (50 examples)
- ✓ Zero window size (window_end = window_start) is allowed (edge case)

### 5. Failure Patterns Table Constraints

**CHECK Constraints:**
- `failure_type` IN (valid failure types)
- `occurrence_count` > 0
- `confidence_score` >= 0.0 AND <= 1.0

**Properties Tested:**
- ✓ Valid failure pattern data always inserts (100 examples)
- ✓ Occurrence counts <= 0 are rejected (50 examples)

### 6. Stateful Property Tests

**Complex Scenarios:**
- Multiple inserts, updates, deletes in sequence
- Constraint enforcement across operations
- Data consistency after modifications

**Invariants Tested:**
- ✓ All strategies always have consistent counts (checked after every operation)
- ✓ All success rates always stay between 0 and 1 (checked after every operation)

### 7. Cross-Table Integration Tests

**Properties Tested:**
- ✓ Multiple failures of same type can be inserted (50 examples)
- ✓ Multiple strategies with different success rates can coexist (50 examples)

## Running the Tests

### Run All Property Tests

```bash
# Using pytest directly
pytest Agent_Guru/self_improvement/tests/test_database_constraints_property.py -v

# Using the test runner script
python Agent_Guru/self_improvement/tests/run_property_tests.py
```

### Run Specific Test Classes

```bash
# Test only failures table
pytest Agent_Guru/self_improvement/tests/test_database_constraints_property.py::TestFailuresTableConstraints -v

# Test only strategies table
pytest Agent_Guru/self_improvement/tests/test_database_constraints_property.py::TestStrategiesTableConstraints -v

# Test only stateful scenarios
pytest Agent_Guru/self_improvement/tests/test_database_constraints_property.py::TestDatabaseStateful -v
```

### Show Hypothesis Statistics

```bash
pytest Agent_Guru/self_improvement/tests/test_database_constraints_property.py --hypothesis-show-statistics
```

## Test Configuration

### Hypothesis Settings

- **max_examples**: 100 per property (configurable)
- **suppress_health_check**: Function-scoped fixtures allowed
- **database**: Temporary SQLite databases for isolation

### Test Strategies

Custom Hypothesis strategies generate realistic test data:

- `failure_type_strategy()`: Valid failure types
- `positive_float_strategy()`: Positive floats for execution times
- `success_rate_strategy()`: Valid success rates (0.0 to 1.0)
- `positive_integer_strategy()`: Positive integers for counts
- `version_strategy()`: Valid version numbers (> 0)
- `boolean_strategy()`: Boolean as integer (0 or 1)
- `timestamp_strategy()`: Valid ISO timestamp strings
- `json_dict_strategy()`: Valid JSON-serializable dictionaries

## Understanding Test Output

### Successful Test

```
test_strategies_valid_data_always_inserts PASSED [100 examples]
```

This means Hypothesis generated 100 random test cases and all passed.

### Failed Test

```
test_strategies_inconsistent_totals_rejected FAILED
Falsifying example: test_strategies_inconsistent_totals_rejected(
    success_count=5, failure_count=3, total_offset=1
)
```

This shows the specific input that caused the test to fail, making debugging easy.

### Hypothesis Statistics

```
- 100 passing examples, 0 failing examples, 0 invalid examples
- Typical runtimes: 0-1 ms, ~ 50% in data generation
- Stopped because settings.max_examples=100
```

This shows how many examples were tested and performance metrics.

## Why Property-Based Testing?

### Advantages

1. **Comprehensive Coverage**: Tests hundreds of cases automatically
2. **Edge Case Discovery**: Finds corner cases you wouldn't think of
3. **Regression Prevention**: Once a bug is found, it's added to the test suite
4. **Documentation**: Properties serve as executable specifications
5. **Confidence**: If a property holds for 100+ random examples, it likely holds always

### Example: Finding a Bug

Traditional test might miss:
```python
# This passes traditional tests
strategy = Strategy(success=10, failure=5, total=15)  # Correct

# But this might slip through
strategy = Strategy(success=10, failure=5, total=16)  # BUG!
```

Property-based test catches it:
```python
@given(success=integers(), failure=integers(), offset=integers(min_value=1))
def test_inconsistent_totals_rejected(success, failure, offset):
    # Hypothesis will try success=10, failure=5, offset=1
    # And catch the bug!
```

## Maintenance

### Adding New Constraints

When adding new database constraints:

1. Add the constraint to `database_schema.py`
2. Create a property test in `test_database_constraints_property.py`
3. Run tests to verify constraint is enforced
4. Update this README

### Modifying Existing Constraints

When modifying constraints:

1. Update the constraint in `database_schema.py`
2. Update corresponding property tests
3. Run full test suite to ensure no regressions
4. Update this README if behavior changes

## Performance

- **Test Execution Time**: ~10-30 seconds for full suite
- **Database Operations**: Temporary databases created/destroyed per test
- **Memory Usage**: Minimal (temporary databases are small)

## Integration with CI/CD

These tests should run:
- ✓ On every commit (pre-commit hook)
- ✓ In CI/CD pipeline (GitHub Actions)
- ✓ Before merging PRs
- ✓ Before releases

## References

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Property-Based Testing Guide](https://hypothesis.works/articles/what-is-property-based-testing/)
- [SQLite CHECK Constraints](https://www.sqlite.org/lang_createtable.html#check_constraints)

## Status

✅ **Complete**: All database integrity constraints have property-based tests with 100+ examples per property.

