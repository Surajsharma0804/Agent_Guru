# Platform Integration Troubleshooting Guide

## Common Issues and Solutions

---

### 1. `UnsupportedPlatformError` on startup

**Symptom**:
```
Agent_Guru.platform.platform_detector.UnsupportedPlatformError: Unsupported platform: ...
```

**Cause**: Running on an OS that is not Windows, macOS, or Linux (e.g., FreeBSD, Cygwin).

**Solution**:
- Verify you are running on a supported OS: `python -c "import platform; print(platform.system())"`
- If running in WSL, ensure `platform.system()` returns `"Linux"`, not `"Windows"`
- For Docker, ensure the base image is Linux-based

---

### 2. `PermissionDeniedError` for file operations

**Symptom**:
```
PermissionDeniedError: Access denied to path '/etc/passwd' (mode: write)
```

**Cause**: The path is not in the `allowed_paths` list in your permissions config, or the requested permission type is not granted.

**Solution**:
1. Check your permissions config:
   ```bash
   cat Agent_Guru/platform/permissions/config.yaml
   ```
2. Add the path with the required permissions:
   ```yaml
   file_system:
     allowed_paths:
       - path: "/your/path"
         permissions: ["read", "write"]
   ```
3. Hot-reload the config without restart:
   ```python
   manager.reload()
   ```

---

### 3. `QuotaExceededError`

**Symptom**:
```
QuotaExceededError: file_operations quota exceeded (1000/hour)
```

**Cause**: The operation quota for the current hour has been reached.

**Solution**:
- Wait for the quota to reset (resets at the top of each hour)
- Increase the quota in config:
  ```yaml
  quotas:
    file_operations:
      per_hour: 5000
  ```
- Check current quota usage:
  ```python
  from Agent_Guru.platform.permissions.quota_manager import QuotaManager
  qm = QuotaManager()
  print(qm.get_usage("file_operations"))
  ```

---

### 4. `CircuitBreakerOpenError`

**Symptom**:
```
CircuitBreakerOpenError: Circuit breaker OPEN for service 'github_api' (cooldown: 45s remaining)
```

**Cause**: The circuit breaker tripped after 5 consecutive failures. It will remain open for 60 seconds.

**Solution**:
- Wait for the cooldown period to expire (default: 60s)
- Check the underlying service health
- Manually reset if needed:
  ```python
  from Agent_Guru.platform.error_handling.circuit_breaker import CircuitBreaker
  cb = CircuitBreaker.get("github_api")
  cb.reset()  # Force back to CLOSED state
  ```

---

### 5. High memory usage

**Symptom**: Process memory exceeds 2 GB.

**Diagnosis**:
```python
from Agent_Guru.platform.monitoring.resource_monitor import ResourceMonitor
monitor = ResourceMonitor()
snapshot = monitor.get_current_usage()
print(f"Memory: {snapshot.memory_bytes / 1e9:.2f} GB")
print(f"Process count: {snapshot.process_count}")
```

**Common causes and fixes**:

| Cause | Fix |
|-------|-----|
| `history_size` too large | Reduce `ResourceMonitorConfig.history_size` |
| Duplicate detector cache too large | Reduce `DuplicateOperationDetector.max_cache_size` |
| Memory leak in long-running process | Restart service; check for unbounded collections |
| Too many concurrent processes | Reduce `max_process_count` in resource limits |

---

### 6. Operations being throttled unexpectedly

**Symptom**: Operations return `should_throttle=True` even when system seems idle.

**Diagnosis**:
```python
throttler = AutomaticThrottler(monitor, ThrottleConfig())
history = throttler.get_throttle_history()
for event in history[-10:]:
    print(event.reason, event.cpu_at_throttle, event.memory_at_throttle)
```

**Solution**:
- Check if another process is consuming resources: `psutil.process_iter(['pid', 'name', 'cpu_percent'])`
- Adjust throttle thresholds in `ThrottleConfig`:
  ```python
  config = ThrottleConfig(
      cpu_throttle_threshold=90.0,    # was 80.0
      memory_throttle_threshold=90.0, # was 85.0
  )
  ```

---

### 7. Duplicate operations not being detected

**Symptom**: The same file is being read multiple times despite duplicate detection.

**Cause**: TTL has expired, or the operation fingerprint differs (e.g., different `path` normalization).

**Diagnosis**:
```python
detector = DuplicateOperationDetector(max_cache_size=1000, ttl=300)
stats = detector.get_cache_stats()
print(f"Cache size: {stats.current_size}")
print(f"Hit rate: {stats.hit_rate:.2%}")
print(f"Evictions: {stats.evictions}")
```

**Solution**:
- Increase TTL: `DuplicateOperationDetector(ttl=600)`
- Normalize paths before creating `Operation` objects:
  ```python
  import os
  op = Operation(type=OperationType.FILE_READ, path=os.path.abspath(path))
  ```

---

### 8. GPU monitoring not working

**Symptom**: `snapshot.gpu_usage` is always `None`.

**Cause**: GPUtil not installed, or no NVIDIA GPU present.

**Solution**:
```bash
# Install GPUtil
pip install gputil

# Verify GPU is visible
python -c "import GPUtil; print(GPUtil.getGPUs())"

# If no GPU, disable GPU monitoring
config = ResourceMonitorConfig(enable_gpu_monitoring=False)
```

---

### 9. Audit log not writing

**Symptom**: No entries appearing in `/var/log/agent_guru/audit/`.

**Cause**: Log directory doesn't exist or lacks write permissions.

**Solution**:
```bash
# Linux/macOS
sudo mkdir -p /var/log/agent_guru/audit
sudo chown $USER:$USER /var/log/agent_guru/audit
chmod 755 /var/log/agent_guru/audit

# Verify
python -c "
from Agent_Guru.platform.security.auditor import SecurityAuditor
a = SecurityAuditor(log_dir='/var/log/agent_guru/audit')
a.log_operation('test', 'user', 'success', {})
print('Audit log working')
"
```

---

### 10. Network requests failing with SSL errors

**Symptom**:
```
NetworkError: SSL certificate verification failed for https://api.example.com
```

**Solution**:
```bash
# Update CA certificates
pip install --upgrade certifi

# Or for corporate proxies with custom CA:
export REQUESTS_CA_BUNDLE=/path/to/corporate-ca.crt
export SSL_CERT_FILE=/path/to/corporate-ca.crt
```

---

## Error Message Reference

| Error Code | Message Pattern | Meaning |
|------------|-----------------|---------|
| `PERM_001` | `Access denied to path` | Path not in allowed_paths |
| `PERM_002` | `Permission type not granted` | Operation type not allowed for path |
| `PERM_003` | `Admin privileges required` | Operation needs elevated rights |
| `QUOTA_001` | `quota exceeded` | Hourly/daily quota reached |
| `QUOTA_002` | `Lockdown mode active` | Emergency lockdown enabled |
| `NET_001` | `Domain not in whitelist` | Domain blocked by network policy |
| `NET_002` | `Rate limit exceeded` | Too many requests to service |
| `NET_003` | `SSL certificate verification failed` | TLS error |
| `SEC_001` | `Dangerous command detected` | Command matches blocked pattern |
| `SEC_002` | `Injection attack detected` | Command injection attempt |
| `CB_001` | `Circuit breaker OPEN` | Service temporarily unavailable |
| `PLAT_001` | `Unsupported platform` | OS not supported |

---

## Debug Logging

Enable verbose debug logging to diagnose issues:

```python
import logging
import structlog

# Enable debug logging for platform module
logging.basicConfig(level=logging.DEBUG)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
)
```

Or via environment variable:
```bash
export AGENT_GURU_LOG_LEVEL=DEBUG
```

### Useful debug commands

```bash
# Check platform detection
python -c "
from Agent_Guru.platform.platform_detector import PlatformDetector
import json
info = PlatformDetector.detect()
print(json.dumps(info.__dict__, default=str, indent=2))
"

# Check permission config
python -c "
from Agent_Guru.platform.permissions.model_manager import PermissionModelManager
m = PermissionModelManager()
m.load()
print('Config loaded successfully')
print('Allowed paths:', [p.path for p in m.config.file_system.allowed_paths])
"

# Check resource usage
python -c "
from Agent_Guru.platform.monitoring.resource_monitor import ResourceMonitor, ResourceMonitorConfig
m = ResourceMonitor(ResourceMonitorConfig(enable_gpu_monitoring=False))
s = m.get_current_usage()
print(f'CPU: {s.cpu_percent:.1f}%')
print(f'Memory: {s.memory_bytes / 1e9:.2f} GB ({s.memory_percent:.1f}%)')
"

# Check cache stats
python -c "
from Agent_Guru.platform.optimization.duplicate_detector import DuplicateOperationDetector
d = DuplicateOperationDetector()
stats = d.get_cache_stats()
print(f'Cache size: {stats.current_size}')
print(f'Hit rate: {stats.hit_rate:.2%}')
"
```

---

## Performance Troubleshooting

### Slow file operations

1. Check disk I/O: `psutil.disk_io_counters()`
2. Check if antivirus is scanning files (Windows)
3. Use `tracemalloc` to check for memory pressure
4. Verify duplicate detector is working (reduces redundant reads)

### High CPU during monitoring

1. Increase `sampling_interval` (e.g., from `1.0` to `5.0`)
2. Disable GPU monitoring if not needed: `enable_gpu_monitoring=False`
3. Reduce `history_size` to limit memory pressure

### Slow network requests

1. Check rate limiter status: `nm.get_rate_limit_status()`
2. Verify connection pool is being reused: `nm.get_pool_stats()`
3. Check response cache hit rate: `nm.get_cache_stats()`
4. Enable request logging to identify slow endpoints:
   ```python
   config = NetworkConfig(log_requests=True)
   ```
