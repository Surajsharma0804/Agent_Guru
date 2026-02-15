# Testing Standards for AGENT_GURU

## Overview

This document defines the mandatory testing standards for all components in the AGENT_GURU project. These standards ensure consistent quality, comprehensive coverage, and maintainable test suites across all specifications.

## Core Principles

1. **Dual Testing Approach**: Every component MUST implement both unit tests and property-based tests
2. **High Coverage**: Minimum 90% code coverage for all modules
3. **Property-First Design**: Define correctness properties before implementation
4. **Automated Testing**: All tests run automatically in CI/CD pipeline
5. **Fast Feedback**: Unit tests complete in <5 seconds, full suite in <2 minutes

## Testing Frameworks

### Required Libraries

All projects MUST use these testing libraries:

```python
# Core testing
pytest>=7.4.0              # Test runner and framework
pytest-cov>=4.1.0          # Coverage measurement
pytest-asyncio>=0.21.0     # Async test support

# Property-based testing
hypothesis>=6.82.0         # Property-based testing framework

# Mocking and fixtures
pytest-mock>=3.11.1        # Mocking utilities
pytest-fixtures>=0.1.0     # Shared fixtures
freezegun>=1.2.2           # Time mocking
pyfakefs>=5.2.4            # Filesystem mocking

# Performance testing
pytest-benchmark>=4.0.0    # Performance benchmarking
```

### Configuration

All projects MUST include `pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --cov=guru
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=90
    --hypothesis-show-statistics
    --benchmark-disable
asyncio_mode = auto
```

## Dual Testing Approach

### Unit Tests

**Purpose**: Test specific examples, edge cases, and integration points

**Requirements**:
- Test specific input/output examples
- Test boundary conditions (empty, zero, max values)
- Test error conditions (invalid input, missing data)
- Test integration between components
- Use descriptive test names: `test_<component>_<scenario>_<expected_result>`

**Example**:
```python
def test_package_manager_install_valid_package_succeeds():
    """Test that installing a valid package succeeds."""
    manager = PackageManager()
    package_path = Path("test_package-1.0.0.whl")
    target_env = Path("/tmp/test_env")
    
    manager.install_package(package_path, target_env)
    
    assert manager.get_installed_packages(target_env)[0].name == "test_package"
    assert manager.get_installed_packages(target_env)[0].version == "1.0.0"

def test_package_manager_install_invalid_checksum_raises_error():
    """Test that installing a package with invalid checksum raises error."""
    manager = PackageManager()
    package_path = Path("corrupted_package.whl")
    
    with pytest.raises(ChecksumError):
        manager.install_package(package_path, Path("/tmp/test_env"))
```

### Property-Based Tests

**Purpose**: Verify universal properties across all inputs

**Requirements**:
- Implement ALL correctness properties from design document
- Minimum 100 iterations per property test (configurable via `@settings(max_examples=100)`)
- Use custom strategies for domain-specific data generation
- Tag each test with property reference: `# Feature: <spec-name>, Property N: <property-title>`
- Use descriptive test names: `test_property_<N>_<property_description>`

**Example**:
```python
from hypothesis import given, settings, strategies as st

@settings(max_examples=100)
@given(
    package_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))),
    version=st.from_regex(r'^\d+\.\d+\.\d+$', fullmatch=True)
)
def test_property_1_package_installation_round_trip(package_name, version):
    """
    Feature: guru-deployment-system, Property 1: Package Installation Round Trip
    
    For any valid package with correct checksum and signature, when the package
    is downloaded, verified, and installed, then the package SHALL appear in the
    package registry with correct metadata.
    """
    manager = PackageManager()
    registry = PackageRegistry()
    
    # Create valid test package
    package_path = create_test_package(package_name, version)
    
    # Install package
    manager.install_package(package_path, Path("/tmp/test_env"))
    
    # Verify package in registry
    installed = registry.get_package(package_name)
    assert installed is not None
    assert installed.name == package_name
    assert installed.version == version
    assert installed.install_timestamp is not None
```

## Custom Strategies

Create domain-specific Hypothesis strategies in `tests/strategies.py`:

```python
from hypothesis import strategies as st

# Package names: lowercase letters, numbers, hyphens
package_names = st.text(
    min_size=1, 
    max_size=50,
    alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), whitelist_characters='-_')
).filter(lambda x: x[0].isalpha())

# Semantic versions: X.Y.Z
semantic_versions = st.from_regex(r'^\d+\.\d+\.\d+$', fullmatch=True)

# File paths: valid Unix/Windows paths
file_paths = st.text(
    min_size=1,
    max_size=200,
    alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='/-_.')
).map(lambda x: Path(x))

# Process IDs: positive integers
process_ids = st.integers(min_value=1, max_value=65535)

# Trust scores: 0.0 to 1.0
trust_scores = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
```

## Test Organization

### Directory Structure

```
tests/
├── unit/                          # Unit tests
│   ├── test_<component1>.py
│   ├── test_<component2>.py
│   └── ...
├── property/                      # Property-based tests
│   ├── test_properties_<domain1>.py
│   ├── test_properties_<domain2>.py
│   └── ...
├── integration/                   # Integration tests
│   ├── test_<workflow1>.py
│   ├── test_<workflow2>.py
│   └── ...
├── performance/                   # Performance tests
│   ├── test_perf_<component1>.py
│   └── ...
├── strategies.py                  # Custom Hypothesis strategies
├── conftest.py                    # Shared fixtures
└── __init__.py
```

### File Naming

- Unit tests: `test_<component_name>.py`
- Property tests: `test_properties_<domain>.py`
- Integration tests: `test_<workflow_name>.py`
- Performance tests: `test_perf_<component_name>.py`

### Test Naming

- Unit tests: `test_<component>_<scenario>_<expected_result>`
- Property tests: `test_property_<N>_<property_description>`
- Integration tests: `test_<workflow>_<scenario>_<expected_result>`

## Coverage Requirements

### Minimum Coverage

- **Overall**: 90% code coverage
- **Critical paths**: 100% coverage (authentication, cryptography, policy evaluation)
- **Error paths**: 100% coverage (all error conditions tested)
- **Property tests**: All correctness properties from design document implemented

### Coverage Exclusions

Only these patterns may be excluded from coverage:

```python
# pragma: no cover - for defensive code that should never execute
if TYPE_CHECKING:  # pragma: no cover
    from typing import ...

# pragma: no cover - for abstract methods
def abstract_method(self):  # pragma: no cover
    raise NotImplementedError()

# pragma: no cover - for platform-specific code not testable on current platform
if sys.platform == "win32":  # pragma: no cover
    ...
```

### Coverage Reporting

- HTML report generated in `htmlcov/`
- Terminal report shows missing lines
- CI/CD fails if coverage drops below 90%
- Coverage badge in README.md

## Fixtures and Mocking

### Shared Fixtures

Define shared fixtures in `tests/conftest.py`:

```python
import pytest
from pathlib import Path
from pyfakefs.fake_filesystem import FakeFilesystem

@pytest.fixture
def temp_env(tmp_path):
    """Create temporary Python environment for testing."""
    env_path = tmp_path / "test_env"
    env_path.mkdir()
    return env_path

@pytest.fixture
def mock_package_registry(tmp_path):
    """Create mock package registry with test data."""
    registry = PackageRegistry(db_path=tmp_path / "registry.db")
    # Add test packages
    registry.add_package(PackageInfo(name="test-pkg", version="1.0.0", ...))
    return registry

@pytest.fixture
def fake_filesystem(fs: FakeFilesystem):
    """Provide fake filesystem for testing."""
    return fs
```

### Mocking Guidelines

1. **Mock External Dependencies**: Network requests, filesystem, time, subprocess
2. **Don't Mock Internal Logic**: Test real implementations, not mocks
3. **Use Dependency Injection**: Pass dependencies as parameters for easy mocking
4. **Verify Mock Calls**: Use `assert_called_once_with()` to verify interactions

**Example**:
```python
def test_package_manager_download_retries_on_network_error(mocker):
    """Test that download retries on network error."""
    mock_requests = mocker.patch('requests.get')
    mock_requests.side_effect = [
        requests.ConnectionError(),  # First attempt fails
        requests.ConnectionError(),  # Second attempt fails
        mocker.Mock(status_code=200, content=b'package_data')  # Third succeeds
    ]
    
    manager = PackageManager()
    result = manager.download_package("test-pkg", "1.0.0", "https://pypi.org")
    
    assert mock_requests.call_count == 3
    assert result.exists()
```

## Performance Testing

### Performance Requirements

All performance-critical operations MUST have performance tests:

```python
def test_perf_dependency_resolution_completes_within_time_limit(benchmark):
    """Test that dependency resolution completes within 5 seconds."""
    resolver = DependencyResolver()
    
    result = benchmark(resolver.resolve_dependencies, "complex-package", "1.0.0", [])
    
    assert result.duration < 5.0  # seconds
```

### Benchmarking

Use `pytest-benchmark` for performance regression testing:

```python
def test_benchmark_package_installation(benchmark):
    """Benchmark package installation performance."""
    manager = PackageManager()
    package_path = Path("test_package.whl")
    
    result = benchmark(manager.install_package, package_path, Path("/tmp/env"))
    
    # Verify performance bounds
    assert result.stats.mean < 1.0  # Average < 1 second
    assert result.stats.max < 2.0   # Max < 2 seconds
```

## Continuous Integration

### CI/CD Pipeline

All tests MUST run automatically in CI/CD:

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run unit tests
        run: pytest tests/unit/ -v
      - name: Run property tests
        run: pytest tests/property/ -v --hypothesis-show-statistics
      - name: Run integration tests
        run: pytest tests/integration/ -v
      - name: Check coverage
        run: pytest --cov=guru --cov-fail-under=90
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Pre-commit Hooks

All commits MUST pass pre-commit checks:

```bash
# .git/hooks/pre-commit
#!/bin/bash
set -e

echo "Running pre-commit checks..."

# Format code
black guru/ tests/

# Lint code
flake8 guru/ tests/

# Type check
mypy guru/

# Run fast tests
pytest tests/unit/ -x --tb=short

echo "Pre-commit checks passed!"
```

## Test Documentation

### Test Docstrings

Every test MUST have a docstring explaining:
- What is being tested
- What the expected behavior is
- For property tests: reference to design document property

**Example**:
```python
def test_crypto_verifier_rejects_invalid_signature():
    """
    Test that CryptoVerifier rejects packages with invalid signatures.
    
    Given a package with an invalid Ed25519 signature, when verify_package_signature
    is called, then it should return False and log a security event.
    """
    # Test implementation
```

### Property Test Documentation

Property tests MUST include:
- Feature reference
- Property number and title
- Property statement from design document

**Example**:
```python
def test_property_5_signature_verification_correctness():
    """
    Feature: guru-deployment-system, Property 5: Signature Verification Correctness
    
    For any package with a signature, when the signature is verified using the
    correct public key, then packages with valid signatures SHALL be marked as
    trusted and packages with invalid signatures SHALL be rejected.
    
    Validates: Requirements 2.1, 2.2, 2.3
    """
    # Test implementation
```

## Best Practices

### DO

✅ Write tests before implementation (TDD)
✅ Test one thing per test
✅ Use descriptive test names
✅ Use fixtures for common setup
✅ Mock external dependencies
✅ Test error conditions
✅ Use property-based testing for general behavior
✅ Keep tests fast (<5 seconds for unit tests)
✅ Clean up resources in teardown
✅ Use parametrize for similar test cases

### DON'T

❌ Test implementation details
❌ Mock internal logic
❌ Write flaky tests (non-deterministic)
❌ Skip tests without good reason
❌ Ignore test failures
❌ Write tests that depend on external services
❌ Write tests that depend on test execution order
❌ Use sleep() for timing (use freezegun instead)
❌ Hardcode file paths (use tmp_path fixture)
❌ Leave commented-out test code

## Compliance

### Mandatory Requirements

All specifications MUST:
1. Include "Testing Strategy" section in design document
2. Define all correctness properties
3. Implement unit tests with ≥90% coverage
4. Implement property tests for all correctness properties
5. Include test organization structure
6. Define custom Hypothesis strategies
7. Include CI/CD configuration

### Review Checklist

Before merging, verify:
- [ ] All tests pass
- [ ] Coverage ≥90%
- [ ] All correctness properties tested
- [ ] No skipped tests without justification
- [ ] Test documentation complete
- [ ] CI/CD pipeline configured
- [ ] Pre-commit hooks installed

## References

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [pytest Documentation](https://docs.pytest.org/)
- [Property-Based Testing Guide](https://increment.com/testing/in-praise-of-property-based-testing/)
- [Test-Driven Development](https://martinfowler.com/bliki/TestDrivenDevelopment.html)
