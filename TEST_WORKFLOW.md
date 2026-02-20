# Test Workflow - Prevent System Crashes

## 🚨 Your Problem

Tests crash your system at ~90% completion due to disk space exhaustion.

## ✅ Solution: 3-Step Workflow

### Step 1: Check Readiness
```bash
python check_test_readiness.py
```

This checks:
- ✅ Disk space (need 3GB+ free)
- ✅ Test files exist
- ✅ Configuration is correct
- ✅ Tools are available

### Step 2: Cleanup (if needed)
```bash
python cleanup_test_artifacts.py
```

This removes:
- `.hypothesis/` cache
- `.pytest_cache/` cache
- `__pycache__/` bytecode
- Coverage reports
- Temporary files

### Step 3: Run Tests Safely
```bash
python run_tests_safe.py
```

This:
- Monitors disk space
- Runs tests in batches
- Cleans between batches
- Stops if space < 2GB

## 📋 Complete Workflow

```bash
# 1. Check if ready
python check_test_readiness.py

# 2. If not ready, cleanup
python cleanup_test_artifacts.py

# 3. Run tests safely
python run_tests_safe.py
```

## 🎯 Quick Commands

### Full Test Suite (Safe)
```bash
python run_tests_safe.py
```

### Single Test File
```bash
pytest -v --tb=short -p no:cacheprovider Agent_Guru/reasoning/tests/test_models.py
```

### Specific Test
```bash
pytest -v --tb=short -p no:cacheprovider Agent_Guru/reasoning/tests/test_models.py::TestIntent::test_creation
```

### By Category
```bash
# Unit tests only
pytest -v --tb=short -p no:cacheprovider -m unit

# Property tests only
pytest -v --tb=short -p no:cacheprovider -m property
```

## 🆘 Emergency: System Running Out of Space

1. **Stop tests**: Press Ctrl+C
2. **Cleanup**: `python cleanup_test_artifacts.py`
3. **Check space**: `python check_test_readiness.py`
4. **Resume**: `python run_tests_safe.py`

## 💡 Best Practices

1. **Always check first**: Run `check_test_readiness.py`
2. **Cleanup regularly**: Run cleanup script daily
3. **Use safe runner**: Don't run `pytest` directly for full suite
4. **Monitor space**: Keep 3GB+ free
5. **Test in batches**: Use safe runner for automatic batching

## 📚 More Information

- **Quick Reference**: `QUICK_TEST_REFERENCE.md`
- **Full Guide**: `TESTING_GUIDE.md`
- **Task List**: `.kiro/specs/core-reasoning-engine/tasks.md`

---

**Remember**: Your system crashes because of space. Always use the 3-step workflow!
