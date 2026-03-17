# Platform Integration API Reference

## Overview

The `Agent_Guru.platform` package provides complete laptop/desktop/mobile control through voice commands. All public APIs are documented here with examples, parameters, and error handling.

---

## PlatformDetector

**Module**: `Agent_Guru.platform.platform_detector`

Detects the current operating system and provides platform-specific helpers.

### Methods

#### `PlatformDetector.detect() -> PlatformInfo`
Returns cached platform information. Thread-safe, O(1) after first call.

```python
from Agent_Guru.platform.platform_detector import PlatformDetector

info = PlatformDetector.detect()
print(info.os_name)      # "Windows", "Darwin", "Linux"
print(info.os_version)   # "10.0.22621"
print(info.architecture) # "x86_64"
```

#### `PlatformDetector.is_windows() -> bool`
#### `PlatformDetector.is_macos() -> bool`
#### `PlatformDetector.is_linux() -> bool`

```python
if PlatformDetector.is_windows():
    # Windows-specific logic
    pass
```

**Raises**: `UnsupportedPlatformError` if platform is not Windows, macOS, or Linux.

---

## OSController

**Module**: `Agent_Guru.platform.os_controller`

Main facade for all OS operations. Routes commands to the appropriate controller.

### Constructor

```python
from Agent_Guru.platform.os_controller import OSController

controller = OSController()
```

### Methods

#### `execute_operation(operation: Operation) -> OperationResult`
Execute any platform operation. Validates permissions, logs to audit trail, and routes to the correct controller.

```python
from Agent_Guru.platform.os_controller import OSController, Operation, OperationType

controller = OSController()
result = controller.execute_operation(
    Operation(type=OperationType.FILE_READ, path="/tmp/data.txt")
)
print(result.success)  # True
print(result.data)     # file contents
```

**Parameters**:
- `operation`: `Operation` dataclass with `type`, `path`, `command`, `args`, `content` fields

**Returns**: `OperationResult` with `success: bool`, `data: Any`, `error: str | None`

**Raises**: `PermissionError`, `OperationError`

---

## FileOperationsController

**Module**: `Agent_Guru.platform.controllers.file_operations`

Create, read, update, delete, move, and copy files and directories.

### Constructor

```python
from Agent_Guru.platform.controllers.file_operations import FileOperationsController

fc = FileOperationsController()
```

### Methods

#### `create_file(path: str, content: str = "") -> bool`
```python
fc.create_file("/tmp/hello.txt", "Hello, World!")
```

#### `read_file(path: str) -> str`
```python
content = fc.read_file("/tmp/hello.txt")
```

#### `write_file(path: str, content: str) -> bool`
```python
fc.write_file("/tmp/hello.txt", "Updated content")
```

#### `delete_file(path: str) -> bool`
Requires confirmation for destructive operations.
```python
fc.delete_file("/tmp/hello.txt")
```

#### `move_file(src: str, dst: str) -> bool`
```python
fc.move_file("/tmp/old.txt", "/tmp/new.txt")
```

#### `copy_file(src: str, dst: str) -> bool`
```python
fc.copy_file("/tmp/source.txt", "/tmp/dest.txt")
```

#### `file_exists(path: str) -> bool`
```python
if fc.file_exists("/tmp/data.txt"):
    content = fc.read_file("/tmp/data.txt")
```

#### `list_directory(path: str) -> list[str]`
```python
files = fc.list_directory("/tmp")
```

**Raises**: `FileNotFoundError`, `PermissionError`, `FileOperationError`

---

## ProcessManager

**Module**: `Agent_Guru.platform.process_manager`

List, start, and terminate processes cross-platform.

### Constructor

```python
from Agent_Guru.platform.process_manager import ProcessManager

pm = ProcessManager()
```

### Methods

#### `list_processes() -> list[ProcessInfo]`
```python
processes = pm.list_processes()
for p in processes:
    print(p.pid, p.name, p.status)
```

#### `start_process(command: str, args: list[str] = []) -> ProcessInfo`
```python
proc = pm.start_process("notepad.exe")
print(proc.pid)
```

#### `terminate_process(pid: int) -> bool`
```python
pm.terminate_process(1234)
```

#### `get_process_status(pid: int) -> ProcessStatus`
```python
status = pm.get_process_status(1234)
print(status.is_running)
```

---

## PermissionManager

**Module**: `Agent_Guru.platform.permissions.manager`

Validate permissions before executing operations.

### Constructor

```python
from Agent_Guru.platform.permissions.manager import PermissionManager

pm = PermissionManager()
```

### Methods

#### `can_access_path(path: str, mode: str) -> bool`
Check if the current process can access a path. `mode` is `"r"`, `"w"`, or `"x"`.

```python
if pm.can_access_path("/etc/passwd", "r"):
    content = open("/etc/passwd").read()
```

#### `is_admin() -> bool`
```python
if pm.is_admin():
    # Elevated operations
    pass
```

#### `check_operation_permission(operation_type: str) -> bool`
```python
pm.check_operation_permission("file_delete")
```

**Raises**: `PermissionDeniedError` with descriptive message.

---

## ResourceMonitor

**Module**: `Agent_Guru.platform.monitoring.resource_monitor`

Real-time CPU, memory, disk, network, and GPU monitoring.

### Constructor

```python
from Agent_Guru.platform.monitoring.resource_monitor import (
    ResourceMonitor, ResourceMonitorConfig
)

config = ResourceMonitorConfig(
    sampling_interval=5.0,   # seconds
    history_size=100,
    enable_gpu_monitoring=True,
)
monitor = ResourceMonitor(config)
```

### Methods

#### `start_monitoring() -> None`
Start background monitoring thread.
```python
monitor.start_monitoring()
```

#### `stop_monitoring() -> None`
```python
monitor.stop_monitoring()
```

#### `get_current_usage() -> ResourceSnapshot`
```python
snapshot = monitor.get_current_usage()
print(f"CPU: {snapshot.cpu_percent}%")
print(f"Memory: {snapshot.memory_bytes / 1e9:.1f} GB")
print(f"Disk: {snapshot.disk_usage}")
```

#### `get_history() -> list[ResourceSnapshot]`
```python
history = monitor.get_history()
```

#### `add_alert_callback(callback: Callable[[ResourceAlert], None]) -> None`
```python
def on_alert(alert):
    print(f"ALERT: {alert.metric} at {alert.value}%")

monitor.add_alert_callback(on_alert)
```

### ResourceMonitorConfig Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sampling_interval` | `float` | `5.0` | Seconds between samples |
| `history_size` | `int` | `100` | Max snapshots to retain |
| `enable_gpu_monitoring` | `bool` | `True` | Enable GPU metrics |
| `cpu_alert_threshold` | `float` | `80.0` | CPU % alert threshold |
| `memory_alert_threshold` | `float` | `85.0` | Memory % alert threshold |

---

## AutomaticThrottler

**Module**: `Agent_Guru.platform.monitoring.throttling`

Automatically throttle operations when resources are constrained.

### Constructor

```python
from Agent_Guru.platform.monitoring.throttling import (
    AutomaticThrottler, ThrottleConfig
)

throttler = AutomaticThrottler(monitor, ThrottleConfig())
throttler.start()
```

### Methods

#### `should_throttle(operation: str, priority: OperationPriority) -> bool`
```python
from Agent_Guru.platform.monitoring.throttling import OperationPriority

if not throttler.should_throttle("file_write", OperationPriority.LOW):
    fc.write_file(path, content)
```

#### `get_throttle_history() -> list[ThrottleEvent]`
```python
history = throttler.get_throttle_history()
```

#### `stop() -> None`

---

## DuplicateOperationDetector

**Module**: `Agent_Guru.platform.optimization.duplicate_detector`

Prevent duplicate operations using LRU cache with TTL.

### Constructor

```python
from Agent_Guru.platform.optimization.duplicate_detector import (
    DuplicateOperationDetector
)

detector = DuplicateOperationDetector(max_cache_size=1000, ttl=300)
```

### Methods

#### `is_duplicate(operation: Operation) -> bool`
```python
from Agent_Guru.platform.optimization.duplicate_detector import (
    Operation, OperationType
)

op = Operation(type=OperationType.FILE_READ, path="/tmp/data.txt")
if not detector.is_duplicate(op):
    result = fc.read_file("/tmp/data.txt")
    detector.mark_executed(op, result=result)
```

#### `mark_executed(operation: Operation, result: Any) -> None`

#### `cleanup_expired() -> int`
Remove expired entries. Returns count of removed entries.

#### `get_cache_stats() -> CacheStats`
```python
stats = detector.get_cache_stats()
print(f"Size: {stats.current_size}, Hit rate: {stats.hit_rate:.2%}")
```

---

## SecurityAuditor

**Module**: `Agent_Guru.platform.security.auditor`

Immutable audit logging with sensitive data redaction.

### Constructor

```python
from Agent_Guru.platform.security.auditor import SecurityAuditor

auditor = SecurityAuditor(log_dir="/var/log/agent_guru")
```

### Methods

#### `log_operation(operation: str, user: str, result: str, metadata: dict) -> AuditEntry`
```python
auditor.log_operation(
    operation="file_read",
    user="guru",
    result="success",
    metadata={"path": "/tmp/data.txt"}
)
```

#### `get_audit_log(start: datetime, end: datetime) -> list[AuditEntry]`

#### `detect_suspicious_patterns() -> list[SecurityAlert]`

#### `generate_compliance_report(standard: str) -> ComplianceReport`
`standard` is one of: `"gdpr"`, `"ccpa"`, `"hipaa"`, `"soc2"`

---

## NetworkManager

**Module**: `Agent_Guru.platform.network.manager`

HTTP client with rate limiting, caching, connection pooling, and streaming.

### Constructor

```python
from Agent_Guru.platform.network.manager import NetworkManager

nm = NetworkManager()
```

### Methods

#### `get(url: str, headers: dict = {}, timeout: float = 30.0) -> Response`
#### `post(url: str, body: Any, headers: dict = {}) -> Response`
#### `put(url: str, body: Any) -> Response`
#### `delete(url: str) -> Response`

```python
response = nm.get("https://api.example.com/data")
print(response.status_code)
print(response.json())
```

#### `stream_download(url: str, dest_path: str, progress_callback=None) -> bool`
```python
nm.stream_download(
    "https://example.com/large_file.zip",
    "/tmp/large_file.zip",
    progress_callback=lambda pct: print(f"{pct:.0f}%")
)
```

---

## GitHubIntegrator

**Module**: `Agent_Guru.platform.github.integrator`

Git operations with automatic commit, push, and conflict resolution.

### Constructor

```python
from Agent_Guru.platform.github.integrator import GitHubIntegrator

git = GitHubIntegrator(repo_path=".")
```

### Methods

#### `commit_and_push(message: str, files: list[str] = []) -> bool`
```python
git.commit_and_push("feat: add new feature", files=["src/feature.py"])
```

#### `create_pull_request(title: str, body: str, branch: str) -> PullRequest`

#### `get_status() -> RepoStatus`
```python
status = git.get_status()
print(status.branch, status.uncommitted_files)
```

---

## Error Types

| Error | Module | Description |
|-------|--------|-------------|
| `UnsupportedPlatformError` | `platform_detector` | OS not supported |
| `PermissionDeniedError` | `permissions.manager` | Insufficient permissions |
| `FileOperationError` | `controllers.file_operations` | File operation failed |
| `OperationError` | `os_controller` | Generic operation failure |
| `NetworkError` | `network.manager` | HTTP request failed |
| `SecurityViolationError` | `security.auditor` | Dangerous command detected |
| `QuotaExceededError` | `permissions.quota_manager` | Operation quota exceeded |
| `CircuitBreakerOpenError` | `error_handling.circuit_breaker` | Circuit breaker tripped |
