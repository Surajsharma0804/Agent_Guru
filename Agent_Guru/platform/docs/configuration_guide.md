# Platform Integration Configuration Guide

## Overview

The platform integration system is configured through YAML files and environment variables. This guide covers all configuration options with examples for development, staging, and production environments.

---

## Permission Model Configuration

The permission model is loaded from a YAML file (default: `permissions/config.yaml`). It controls what files, commands, and network resources the agent can access.

### Loading Configuration

```python
from Agent_Guru.platform.permissions.model_manager import PermissionModelManager

manager = PermissionModelManager(config_path="permissions/config.yaml")
manager.load()

# Hot reload without restart
manager.reload()
```

### Full Configuration Reference

```yaml
version: "1.0"
environment: "production"  # development | staging | production

# --- File System Permissions ---
file_system:
  allowed_paths:
    - path: "/home/agent_guru/workspace"
      permissions: ["read", "write", "delete", "execute"]

    # Time-restricted path (business hours only)
    - path: "/home/agent_guru/sensitive"
      permissions: ["read"]
      time_restrictions:
        - days: ["monday", "tuesday", "wednesday", "thursday", "friday"]
          hours: "09:00-17:00"
          timezone: "UTC"

    - path: "/var/log/agent_guru"
      permissions: ["read", "write"]

    - path: "/tmp/agent_guru"
      permissions: ["read", "write", "delete", "execute"]

  # Block dangerous file types
  blocked_extensions:
    - ".exe"
    - ".dll"
    - ".bat"
    - ".cmd"
    - ".ps1"

  max_file_size: 104857600  # 100 MB

# --- Command Execution Permissions ---
commands:
  # Allowed patterns (regex, checked after blocked)
  allowed_patterns:
    - "^git .*"
    - "^npm (install|test|build|run)"
    - "^python3? .*\\.py$"
    - "^node .*\\.js$"
    - "^ls .*"
    - "^cat .*"
    - "^grep .*"

  # Blocked patterns (checked first - security)
  blocked_patterns:
    - ".*rm -rf.*"
    - ".*sudo.*"
    - ".*format.*"
    - ".*shutdown.*"
    - ".*reboot.*"
    - ".*curl.*\\|.*bash.*"
    - ".*wget.*\\|.*sh.*"

# --- Network Permissions ---
network:
  allowed_domains:
    - "api.github.com"
    - "*.googleapis.com"
    - "api.openai.com"
    - "api.anthropic.com"
    - "pypi.org"

  allowed_methods: ["GET", "POST", "PUT", "DELETE", "PATCH"]

  rate_limits:
    default: 100      # requests per minute
    github: 5000      # requests per hour
    openai: 3500

# --- Resource Limits ---
resources:
  max_cpu_percent: 80.0
  max_memory_bytes: 2147483648      # 2 GB
  min_disk_free_bytes: 1073741824   # 1 GB
  max_process_count: 10
  max_network_bandwidth_mbps: 100.0

# --- Operation Quotas ---
quotas:
  file_operations:
    per_hour: 1000
    per_day: 10000
  command_executions:
    per_hour: 500
    per_day: 5000
  network_requests:
    per_hour: 10000
    per_day: 100000

# --- Emergency Lockdown ---
lockdown_mode:
  enabled: false
  allowed_operations:
    - "read_file"
    - "get_system_info"
    - "get_hardware_status"
```

---

## Resource Monitor Configuration

```python
from Agent_Guru.platform.monitoring.resource_monitor import (
    ResourceMonitor, ResourceMonitorConfig, ResourceLimits
)

config = ResourceMonitorConfig(
    sampling_interval=5.0,        # seconds between samples
    history_size=100,             # max snapshots retained in memory
    enable_gpu_monitoring=True,   # requires GPUtil
    cpu_alert_threshold=80.0,     # % CPU to trigger alert
    memory_alert_threshold=85.0,  # % memory to trigger alert
    disk_alert_threshold=90.0,    # % disk to trigger alert
)

limits = ResourceLimits(
    max_cpu_percent=80.0,
    max_memory_bytes=2 * 1024**3,   # 2 GB
    min_disk_free_bytes=1 * 1024**3, # 1 GB
)

monitor = ResourceMonitor(config, limits=limits)
```

### Environment-Specific Settings

| Setting | Development | Staging | Production |
|---------|-------------|---------|------------|
| `sampling_interval` | `1.0` | `5.0` | `5.0` |
| `history_size` | `50` | `100` | `500` |
| `cpu_alert_threshold` | `90.0` | `85.0` | `80.0` |
| `memory_alert_threshold` | `90.0` | `87.0` | `85.0` |
| `enable_gpu_monitoring` | `False` | `True` | `True` |

---

## Network Manager Configuration

```python
from Agent_Guru.platform.network.manager import NetworkManager, NetworkConfig

config = NetworkConfig(
    timeout=30.0,              # default request timeout (seconds)
    max_retries=3,             # retry attempts on failure
    pool_size=100,             # max connections per host
    cache_size_mb=100,         # response cache size
    rate_limit_per_minute=100, # default rate limit
)

nm = NetworkManager(config)
```

---

## Security Configuration

```python
from Agent_Guru.platform.security.auditor import SecurityAuditor, AuditConfig

config = AuditConfig(
    log_dir="/var/log/agent_guru/audit",
    max_log_size_mb=500,
    retention_days=90,
    redact_patterns=[
        r"password\s*=\s*\S+",
        r"api_key\s*=\s*\S+",
        r"token\s*=\s*\S+",
        r"secret\s*=\s*\S+",
    ],
    enable_siem_export=True,
    siem_endpoint="https://siem.internal/ingest",
)

auditor = SecurityAuditor(config)
```

---

## Environment Variables

All configuration values can be overridden via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_GURU_ENV` | `development` | Environment name |
| `AGENT_GURU_PERMISSIONS_CONFIG` | `permissions/config.yaml` | Permissions config path |
| `AGENT_GURU_LOG_DIR` | `/var/log/agent_guru` | Log directory |
| `AGENT_GURU_MAX_MEMORY_GB` | `2` | Max memory in GB |
| `AGENT_GURU_MAX_CPU_PCT` | `80` | Max CPU % |
| `AGENT_GURU_AUDIT_RETENTION_DAYS` | `90` | Audit log retention |
| `AGENT_GURU_ENABLE_GPU` | `true` | Enable GPU monitoring |
| `AGENT_GURU_NETWORK_TIMEOUT` | `30` | HTTP timeout seconds |

### Loading from environment

```python
import os
from Agent_Guru.platform.monitoring.resource_monitor import ResourceMonitorConfig

config = ResourceMonitorConfig(
    enable_gpu_monitoring=os.getenv("AGENT_GURU_ENABLE_GPU", "true").lower() == "true",
    cpu_alert_threshold=float(os.getenv("AGENT_GURU_MAX_CPU_PCT", "80")),
)
```

---

## Environment-Specific Config Files

### Development (`permissions/dev_config.yaml`)

```yaml
version: "1.0"
environment: "development"

file_system:
  allowed_paths:
    - path: "."
      permissions: ["read", "write", "delete", "execute"]
    - path: "/tmp"
      permissions: ["read", "write", "delete"]

commands:
  allowed_patterns:
    - ".*"  # Allow all commands in development
  blocked_patterns:
    - ".*rm -rf /.*"  # Still block root deletion

resources:
  max_cpu_percent: 95.0
  max_memory_bytes: 4294967296  # 4 GB (relaxed for dev)

quotas:
  file_operations:
    per_hour: 10000
    per_day: 100000
```

### Production (`permissions/prod_config.yaml`)

```yaml
version: "1.0"
environment: "production"

file_system:
  allowed_paths:
    - path: "/home/agent_guru/workspace"
      permissions: ["read", "write"]
    - path: "/var/log/agent_guru"
      permissions: ["read", "write"]
    - path: "/tmp/agent_guru"
      permissions: ["read", "write", "delete"]

  blocked_extensions:
    - ".exe"
    - ".dll"
    - ".so"
    - ".dylib"
    - ".bat"
    - ".cmd"
    - ".ps1"
    - ".sh"  # Extra restriction in production

  max_file_size: 52428800  # 50 MB (stricter in production)

commands:
  allowed_patterns:
    - "^git (status|log|diff|fetch|pull)$"
    - "^python3 -m pytest .*"
  blocked_patterns:
    - ".*rm.*"
    - ".*sudo.*"
    - ".*format.*"
    - ".*shutdown.*"
    - ".*reboot.*"
    - ".*curl.*\\|.*"
    - ".*wget.*\\|.*"
    - ".*eval.*"
    - ".*exec.*"

resources:
  max_cpu_percent: 80.0
  max_memory_bytes: 2147483648  # 2 GB
  min_disk_free_bytes: 2147483648  # 2 GB (stricter)
  max_process_count: 5  # Fewer processes in production

lockdown_mode:
  enabled: false
  allowed_operations:
    - "read_file"
    - "get_system_info"
```
