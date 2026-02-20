# Testing Guide - Disk Space Management

## Problem

Running the full test suite can consume significant disk space due to:
- Hypothesis cache storing test examples (`.hypothesis/`)
- PyTorch/CUDA libraries (several GB)
- ML model files (`model.safetensors` ~500MB+)
- Test artifacts and coverage reports
- Python bytecode cache

This can cause your system to run out of space and crash, especially when tests reach 90%+ completion.

## Solution

We've created tools to manage disk space during testing:

### 1. Cleanup Script

Run before tests to free space:

```bash
python cleanup_test_artifacts.py
```

This removes:
- Hypothesis cache (`.hypothesis/`)
- Pytest cache (`.pytest_cache/`)
- Python bytecode (`__pycache__/`, `*.pyc`)
- Coverage reports (`htmlcov/`, `.coverage`)
- MyPy cache (`.mypy_cache/`)
- Build artifacts (`build/`, `dist/`, `*.egg-info`)
- Temporary files (`*.tmp`, `*.log`)

### 2. Safe Test Runner

Runs tests in small batches with space monitoring:

```bash
python run_tests_safe.py
```

Features:
- Monitors disk space before each batch
- Runs tests in batches of 3 files
- Cleans up between batches
- Stops if space drops below 2GB
- No coverage collection (saves space)
- Disables pytest cache

### 3. Manual Test Running

If you need to run specific tests:

```bash
# Run single test file (no cache, no coverage)
pytest -v --tb=short -p no:cacheprovider Agent_Guru/reasoning/tests/test_models.py

# Run specific test
pytest -v --tb=short -p no:cacheprovider Agent_Guru/reasoning/tests/test_models.py::TestIntent::test_creation

# Run with markers (unit tests only)
pytest -v --tb=short -p no:cacheprovider -m unit
```

## Disk Space Requirements

Minimum recommended free space:
- **Development**: 5GB free
- **Running tests**: 3GB free
- **Full test suite with coverage**: 5GB free

## Preventing Space Issues

### 1. Regular Cleanup

Run cleanup script regularly:

```bash
# Add to your workflow
python cleanup_test_artifacts.py
```

### 2. Exclude Large Files from Git

Already configured in `.gitignore`:
- `.hypothesis/`
- `.pytest_cache/`
- `__pycache__/`
- `htmlcov/`
- `.coverage`
- `*.pyc`
- Model files (`*.safetensors`, `*.bin`)

### 3. Use Virtual Environment

Keep dependencies isolated:

```bash
# Create venv
python -m venv agent_gpu

# Activate
agent_gpu\Scripts\activate  # Windows
source agent_gpu/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 4. Hypothesis Configuration

Configured in `pytest.ini` to limit cache:

```ini
[hypothesis]
max_examples = 100
derandomize = True
print_blob = True
```

### 5. Disable Coverage When Not Needed

Coverage collection creates extra files:

```bash
# Without coverage (faster, less space)
pytest -v

# With coverage (slower, more space)
pytest -v --cov=Agent_Guru --cov-report=html
```

## Monitoring Disk Space

### Check Free Space

```bash
# Windows PowerShell
Get-PSDrive C | Select-Object Used,Free

# Python (cross-platform)
python -c "import psutil; print(f'Free: {psutil.disk_usage(\".\").free / (1024**3):.2f} GB')"
```

### Install psutil for Monitoring

```bash
pip install psutil
```

The safe test runner will automatically monitor space if psutil is installed.

## Troubleshooting

### "Disk space running out during tests"

1. Stop tests immediately (Ctrl+C)
2. Run cleanup script:
   ```bash
   python cleanup_test_artifacts.py
   ```
3. Check free space:
   ```bash
   python -c "import psutil; print(f'Free: {psutil.disk_usage(\".\").free / (1024**3):.2f} GB')"
   ```
4. Use safe test runner:
   ```bash
   python run_tests_safe.py
   ```

### "System crashes at 90% test completion"

This happens when:
- Hypothesis cache grows too large
- Coverage data accumulates
- Temporary files not cleaned up

Solution:
- Use safe test runner (cleans between batches)
- Disable coverage: `pytest -v -p no:cacheprovider`
- Run tests in smaller groups

### "Cannot run full test suite"

If you can't run all tests at once:

1. Run by category:
   ```bash
   pytest -m unit  # Unit tests only
   pytest -m property  # Property tests only
   pytest -m integration  # Integration tests only
   ```

2. Run specific modules:
   ```bash
   pytest Agent_Guru/reasoning/tests/test_models.py
   pytest Agent_Guru/reasoning/tests/test_config.py
   ```

3. Use safe test runner (automatic batching):
   ```bash
   python run_tests_safe.py
   ```

## CI/CD Considerations

For GitHub Actions, ensure:
- Cleanup step before tests
- Sufficient runner disk space (7GB+ free)
- Cache cleanup between jobs
- Artifact retention limits

Example workflow:

```yaml
- name: Cleanup before tests
  run: python cleanup_test_artifacts.py

- name: Run tests safely
  run: python run_tests_safe.py

- name: Cleanup after tests
  if: always()
  run: python cleanup_test_artifacts.py
```

## Best Practices

1. **Clean regularly**: Run cleanup script daily
2. **Monitor space**: Check free space before running tests
3. **Use safe runner**: Prefer `run_tests_safe.py` over direct pytest
4. **Batch testing**: Run tests in small groups
5. **Disable cache**: Use `-p no:cacheprovider` flag
6. **Skip coverage**: Only run coverage when needed
7. **Delete old models**: Remove unused model checkpoints

## Summary

- **Problem**: Tests consume disk space and crash system
- **Solution**: Use `run_tests_safe.py` for automatic space management
- **Cleanup**: Run `cleanup_test_artifacts.py` regularly
- **Minimum space**: Keep 3GB+ free when running tests
- **Monitoring**: Install `psutil` for automatic space monitoring

---

**Remember**: Disk space issues are preventable with proper cleanup and monitoring. Always use the safe test runner for full test suites!
