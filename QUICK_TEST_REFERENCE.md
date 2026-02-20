# Quick Test Reference - Space-Safe Commands

## 🚨 CRITICAL: Prevent System Crashes

Your system runs out of space during tests. **Always use these commands:**

## ✅ Recommended Commands

### 1. Safe Test Runner (BEST OPTION)
```bash
python run_tests_safe.py
```
- Monitors disk space automatically
- Runs tests in small batches
- Cleans up between batches
- Stops if space < 2GB

### 2. Cleanup Before Tests
```bash
python cleanup_test_artifacts.py
```
- Frees disk space
- Removes caches and artifacts
- Run this BEFORE any testing

### 3. Single Test File (Space-Safe)
```bash
pytest -v --tb=short -p no:cacheprovider Agent_Guru/reasoning/tests/test_models.py
```
- No cache (saves space)
- No coverage (saves space)
- Single file only

### 4. Specific Test (Space-Safe)
```bash
pytest -v --tb=short -p no:cacheprovider Agent_Guru/reasoning/tests/test_models.py::TestIntent
```

## ❌ AVOID These Commands

### DON'T: Run full pytest without flags
```bash
pytest  # ❌ Will consume too much space
```

### DON'T: Run with coverage
```bash
pytest --cov  # ❌ Creates large coverage files
```

### DON'T: Run all tests at once
```bash
pytest Agent_Guru/  # ❌ Too many tests, will crash
```

## 📊 Check Disk Space

### Before Running Tests
```bash
# Windows PowerShell
Get-PSDrive C | Select-Object Free

# Python (if psutil installed)
python -c "import psutil; print(f'{psutil.disk_usage(\".\").free / (1024**3):.2f} GB free')"
```

### Minimum Required
- **3GB free**: Minimum for safe testing
- **5GB free**: Recommended for development

## 🧹 Emergency Cleanup

If system is running out of space:

1. **Stop tests immediately**: Ctrl+C
2. **Run cleanup**:
   ```bash
   python cleanup_test_artifacts.py
   ```
3. **Check space**:
   ```bash
   python -c "import psutil; print(f'{psutil.disk_usage(\".\").free / (1024**3):.2f} GB')"
   ```
4. **Resume with safe runner**:
   ```bash
   python run_tests_safe.py
   ```

## 📝 Test by Category

### Unit Tests Only
```bash
pytest -v --tb=short -p no:cacheprovider -m unit
```

### Property Tests Only
```bash
pytest -v --tb=short -p no:cacheprovider -m property
```

### Integration Tests Only
```bash
pytest -v --tb=short -p no:cacheprovider -m integration
```

## 🔧 Configuration

### Hypothesis (Property Tests)
- **Max examples**: 100 (configured in pytest.ini)
- **Database**: Disabled (no cache)
- **Derandomize**: True (reproducible)

### Pytest
- **Cache**: Disabled (`-p no:cacheprovider`)
- **Coverage**: Disabled (unless explicitly needed)
- **Warnings**: Disabled (`--disable-warnings`)

## 💡 Tips

1. **Always cleanup first**: `python cleanup_test_artifacts.py`
2. **Use safe runner**: `python run_tests_safe.py`
3. **Monitor space**: Check before running tests
4. **Test in batches**: Don't run all tests at once
5. **Skip coverage**: Only run when needed

## 🆘 Help

See full guide: `TESTING_GUIDE.md`

---

**Remember**: Your system crashes at 90% because of space. Always use the safe test runner!
