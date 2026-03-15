# Goal Manager - Deployment and Operations Guide

## Overview

This guide provides comprehensive instructions for deploying, configuring, monitoring, and operating the Goal Manager in production environments. The Goal Manager is a critical autonomous component that requires careful setup and ongoing maintenance to ensure reliable goal execution across system restarts.

**Target Audience**: DevOps engineers, system administrators, and developers deploying Agent_Guru

**Prerequisites**:
- Python 3.11+ installed
- SQLite3 available
- Git repository initialized
- Access to LLM Runtime, Agent Orchestration, Memory System, and Self-Improvement Engine

---

## Table of Contents

1. [Database Setup and Migration](#database-setup-and-migration)
2. [Configuration Options](#configuration-options)
3. [Monitoring and Logging](#monitoring-and-logging)
4. [Backup and Restore Procedures](#backup-and-restore-procedures)
5. [Troubleshooting Common Issues](#troubleshooting-common-issues)
6. [Performance Tuning](#performance-tuning)
7. [Security Considerations](#security-considerations)
8. [Operational Runbooks](#operational-runbooks)

---

## Database Setup and Migration

### Initial Database Setup

The Goal Manager uses SQLite for persistent storage. The database is automatically initialized on first run, but you can manually set it up:

```python
from Agent_Guru.goal_manager.goal_storage import GoalStorage

# Initialize storage with database path
storage = GoalStorage(db_path="/path/to/goals.db")
```

**Database Location**:
- **Development**: `./data/goals.db` (relative to project root)
- **Production**: `/var/lib/agent_guru/goals.db` (system-wide)
- **User-specific**: `~/.agent_guru/goals.db` (per-user)

### Database Schema

The Goal Manager creates the following schema automatically:

```sql
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    priority TEXT NOT NULL,
    progress REAL NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    parent_id TEXT,
    sub_goal_ids TEXT NOT NULL,  -- JSON array
    dependency_ids TEXT NOT NULL,  -- JSON array
    metadata TEXT NOT NULL,  -- JSON object
    error_message TEXT,
    FOREIGN KEY (parent_id) REFERENCES goals(id)
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_status ON goals(status);
CREATE INDEX IF NOT EXISTS idx_priority ON goals(priority);
CREATE INDEX IF NOT EXISTS idx_parent ON goals(parent_id);
CREATE INDEX IF NOT EXISTS idx_created_at ON goals(created_at);
```

### Schema Verification

Verify the database schema is correctly initialized:

```bash
# Check database file exists
ls -lh /var/lib/agent_guru/goals.db

# Inspect schema
sqlite3 /var/lib/agent_guru/goals.db ".schema goals"

# Check indexes
sqlite3 /var/lib/agent_guru/goals.db ".indexes goals"

# Count goals
sqlite3 /var/lib/agent_guru/goals.db "SELECT COUNT(*) FROM goals;"
```

### Database Migration

The Goal Manager uses schema versioning for migrations. When upgrading:

**Step 1: Backup existing database**
```bash
cp /var/lib/agent_guru/goals.db /var/lib/agent_guru/goals.db.backup
```

**Step 2: Run migration script**
```python
from Agent_Guru.goal_manager.migrations import run_migrations

# Automatically detects schema version and applies migrations
run_migrations(db_path="/var/lib/agent_guru/goals.db")
```

**Step 3: Verify migration**
```bash
# Check schema version
sqlite3 /var/lib/agent_guru/goals.db "PRAGMA user_version;"

# Verify data integrity
python -m Agent_Guru.goal_manager.tools.verify_db
```

### Database Maintenance

**Vacuum database** (reclaim space, optimize):
```bash
sqlite3 /var/lib/agent_guru/goals.db "VACUUM;"
```

**Analyze database** (update statistics):
```bash
sqlite3 /var/lib/agent_guru/goals.db "ANALYZE;"
```

**Check database integrity**:
```bash
sqlite3 /var/lib/agent_guru/goals.db "PRAGMA integrity_check;"
```

**Recommended maintenance schedule**:
- **Daily**: Integrity check (automated)
- **Weekly**: Vacuum (if >10% fragmentation)
- **Monthly**: Full backup and restore test

---

## Configuration Options

### Environment Variables

The Goal Manager supports configuration via environment variables:

```bash
# Database configuration
export GOAL_MANAGER_DB_PATH="/var/lib/agent_guru/goals.db"
export GOAL_MANAGER_DB_TIMEOUT=30  # SQLite timeout in seconds

# Git repository configuration
export GOAL_MANAGER_GIT_REPO="/path/to/agent_guru/repo"
export GOAL_MANAGER_GIT_REMOTE="origin"
export GOAL_MANAGER_GIT_BRANCH="main"

# Retry configuration
export GOAL_MANAGER_MAX_RETRIES=3
export GOAL_MANAGER_BASE_DELAY=1.0  # seconds

# LLM decomposition configuration
export GOAL_MANAGER_LLM_MAX_TOKENS=2000
export GOAL_MANAGER_LLM_TEMPERATURE=0.7
export GOAL_MANAGER_LLM_TIMEOUT=30  # seconds

# Logging configuration
export GOAL_MANAGER_LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
export GOAL_MANAGER_LOG_FILE="/var/log/agent_guru/goal_manager.log"
export GOAL_MANAGER_LOG_FORMAT="json"  # json or text

# Performance configuration
export GOAL_MANAGER_MAX_CONCURRENT_GOALS=10
export GOAL_MANAGER_DECOMPOSITION_CACHE_SIZE=100
```

### Configuration File

Alternatively, use a configuration file (`goal_manager.yaml`):

```yaml
# goal_manager.yaml
database:
  path: "/var/lib/agent_guru/goals.db"
  timeout: 30
  wal_mode: true  # Write-Ahead Logging for better concurrency

git:
  repo_path: "/path/to/agent_guru/repo"
  remote: "origin"
  branch: "main"
  auto_push: true
  commit_on_completion: true

retry:
  max_retries: 3
  base_delay: 1.0
  max_delay: 60.0

llm:
  max_tokens: 2000
  temperature: 0.7
  timeout: 30
  model: "gpt-4"  # or "gemini-pro", "claude-3"

logging:
  level: "INFO"
  file: "/var/log/agent_guru/goal_manager.log"
  format: "json"
  rotation: "daily"
  retention_days: 30

performance:
  max_concurrent_goals: 10
  decomposition_cache_size: 100
  query_cache_ttl: 300  # seconds

monitoring:
  prometheus_port: 9090
  health_check_port: 8080
  metrics_enabled: true
```

**Load configuration**:
```python
from Agent_Guru.goal_manager.config import load_config

config = load_config("/etc/agent_guru/goal_manager.yaml")
```

### Configuration Validation

Validate configuration before starting:

```bash
python -m Agent_Guru.goal_manager.tools.validate_config \
  --config /etc/agent_guru/goal_manager.yaml
```

---

## Monitoring and Logging

### Structured Logging

The Goal Manager uses `structlog` for structured logging with rich context:

**Log Format (JSON)**:
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "event": "goal_created",
  "goal_id": "550e8400-e29b-41d4-a716-446655440000",
  "description": "Implement feature X",
  "priority": "high",
  "user_id": "user123",
  "session_id": "session456"
}
```

**Log Levels**:
- **DEBUG**: Detailed diagnostic information (decomposition prompts, LLM responses)
- **INFO**: Normal operations (goal created, status changes, execution started)
- **WARNING**: Recoverable issues (retry attempts, temporary failures)
- **ERROR**: Errors requiring attention (storage failures, LLM failures)
- **CRITICAL**: System-level failures (database corruption, unrecoverable errors)

### Key Log Events

Monitor these critical events:

| Event | Level | Description | Action Required |
|-------|-------|-------------|-----------------|
| `goal_created` | INFO | New goal created | None |
| `goal_decomposed` | INFO | Goal decomposed into sub-goals | None |
| `goal_execution_started` | INFO | Goal execution began | None |
| `goal_completed` | INFO | Goal completed successfully | None |
| `goal_failed` | ERROR | Goal execution failed | Investigate error_message |
| `storage_error` | ERROR | Database operation failed | Check database health |
| `llm_failure` | WARNING | LLM decomposition failed | Check LLM Runtime status |
| `circular_dependency` | ERROR | Circular dependency detected | Review goal dependencies |
| `corruption_detected` | CRITICAL | Database corruption found | Restore from backup |
| `session_loaded` | INFO | Goals loaded on startup | None |
| `session_persisted` | INFO | Goals persisted on shutdown | None |

### Prometheus Metrics

The Goal Manager exposes Prometheus metrics for monitoring:

**Metrics Endpoint**: `http://localhost:9090/metrics`

**Key Metrics**:

```python
# Goal lifecycle metrics
goal_manager_goals_total{status="pending|in_progress|complete|failed"}
goal_manager_goals_created_total
goal_manager_goals_completed_total
goal_manager_goals_failed_total

# Performance metrics
goal_manager_execution_duration_seconds{quantile="0.5|0.95|0.99"}
goal_manager_decomposition_duration_seconds{quantile="0.5|0.95|0.99"}
goal_manager_storage_operation_duration_seconds{operation="store|update|query"}

# Error metrics
goal_manager_errors_total{type="storage|llm|validation|execution"}
goal_manager_retries_total{operation="storage|llm|agent_orchestration"}

# Resource metrics
goal_manager_database_size_bytes
goal_manager_active_executions
goal_manager_cache_hit_rate
```

**Grafana Dashboard**:

Import the pre-built dashboard from `grafana/goal_manager_dashboard.json`:

```bash
# Import dashboard
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana/goal_manager_dashboard.json
```

### Health Checks

**Health Check Endpoint**: `http://localhost:8080/health`

**Response**:
```json
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "git_repo": "ok",
    "llm_runtime": "ok",
    "agent_orchestration": "ok"
  },
  "uptime_seconds": 86400,
  "goals_total": 150,
  "goals_in_progress": 5
}
```

**Kubernetes Liveness Probe**:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10
```

**Kubernetes Readiness Probe**:
```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
```

### Alerting Rules

Configure alerts for critical conditions:

**Prometheus Alert Rules** (`alerts.yml`):
```yaml
groups:
  - name: goal_manager
    interval: 30s
    rules:
      # High error rate
      - alert: GoalManagerHighErrorRate
        expr: rate(goal_manager_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in Goal Manager"
          description: "Error rate is {{ $value }} errors/sec"

      # Database corruption
      - alert: GoalManagerDatabaseCorruption
        expr: goal_manager_corruption_detected_total > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Database corruption detected"
          description: "Immediate action required"

      # High execution latency
      - alert: GoalManagerHighLatency
        expr: goal_manager_execution_duration_seconds{quantile="0.95"} > 300
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High goal execution latency"
          description: "95th percentile latency is {{ $value }}s"

      # Storage failures
      - alert: GoalManagerStorageFailures
        expr: rate(goal_manager_errors_total{type="storage"}[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Storage failures detected"
          description: "Database may be unavailable"

      # LLM failures
      - alert: GoalManagerLLMFailures
        expr: rate(goal_manager_errors_total{type="llm"}[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "LLM decomposition failures"
          description: "Check LLM Runtime connectivity"
```

---

## Backup and Restore Procedures

### Backup Strategy

**Backup Types**:
1. **Full Backup**: Complete database snapshot
2. **Incremental Backup**: Changes since last backup
3. **Export Backup**: JSON export for portability

### Full Database Backup

**Manual Backup**:
```bash
# Stop Goal Manager (optional but recommended)
systemctl stop agent_guru_goal_manager

# Create backup with timestamp
BACKUP_FILE="/backup/goals_$(date +%Y%m%d_%H%M%S).db"
cp /var/lib/agent_guru/goals.db "$BACKUP_FILE"

# Compress backup
gzip "$BACKUP_FILE"

# Restart Goal Manager
systemctl start agent_guru_goal_manager
```

**Automated Backup Script** (`backup_goals.sh`):
```bash
#!/bin/bash
set -e

BACKUP_DIR="/backup/goal_manager"
DB_PATH="/var/lib/agent_guru/goals.db"
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Create backup with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/goals_$TIMESTAMP.db"

# Use SQLite backup command (online backup, no downtime)
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

# Compress backup
gzip "$BACKUP_FILE"

# Verify backup integrity
gunzip -c "$BACKUP_FILE.gz" | sqlite3 :memory: "PRAGMA integrity_check;"

# Remove old backups
find "$BACKUP_DIR" -name "goals_*.db.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_FILE.gz"
```

**Schedule with cron**:
```bash
# Daily backup at 2 AM
0 2 * * * /usr/local/bin/backup_goals.sh >> /var/log/agent_guru/backup.log 2>&1
```

### JSON Export Backup

**Export all goals to JSON**:
```python
from Agent_Guru.goal_manager.goal_storage import GoalStorage
import asyncio

async def export_goals():
    storage = GoalStorage("/var/lib/agent_guru/goals.db")
    await storage.export_to_json("/backup/goals_export.json")

asyncio.run(export_goals())
```

**Command-line tool**:
```bash
python -m Agent_Guru.goal_manager.tools.export \
  --db /var/lib/agent_guru/goals.db \
  --output /backup/goals_export_$(date +%Y%m%d).json
```

### Restore Procedures

**Restore from full backup**:
```bash
# Stop Goal Manager
systemctl stop agent_guru_goal_manager

# Restore database
gunzip -c /backup/goals_20240115_020000.db.gz > /var/lib/agent_guru/goals.db

# Verify integrity
sqlite3 /var/lib/agent_guru/goals.db "PRAGMA integrity_check;"

# Restart Goal Manager
systemctl start agent_guru_goal_manager
```

**Restore from JSON export**:
```python
from Agent_Guru.goal_manager.goal_storage import GoalStorage
import asyncio

async def import_goals():
    storage = GoalStorage("/var/lib/agent_guru/goals.db")
    count = await storage.import_from_json("/backup/goals_export.json")
    print(f"Imported {count} goals")

asyncio.run(import_goals())
```

**Command-line tool**:
```bash
python -m Agent_Guru.goal_manager.tools.import \
  --db /var/lib/agent_guru/goals.db \
  --input /backup/goals_export.json
```

### Disaster Recovery

**Recovery Time Objective (RTO)**: < 1 hour  
**Recovery Point Objective (RPO)**: < 15 minutes

**Disaster Recovery Steps**:

1. **Assess damage**: Determine extent of data loss
2. **Identify latest backup**: Find most recent valid backup
3. **Restore database**: Follow restore procedure above
4. **Verify data integrity**: Run integrity checks
5. **Resume operations**: Restart Goal Manager
6. **Validate functionality**: Test goal creation and execution
7. **Monitor closely**: Watch for anomalies

**Test disaster recovery quarterly**:
```bash
# Simulate disaster recovery
./scripts/test_disaster_recovery.sh
```

---

## Troubleshooting Common Issues

### Issue 1: Database Locked

**Symptoms**:
- `sqlite3.OperationalError: database is locked`
- Storage operations timing out

**Causes**:
- Multiple processes accessing database
- Long-running transactions
- WAL mode not enabled

**Solutions**:

```bash
# Check for processes holding database lock
lsof /var/lib/agent_guru/goals.db

# Enable WAL mode for better concurrency
sqlite3 /var/lib/agent_guru/goals.db "PRAGMA journal_mode=WAL;"

# Increase timeout in configuration
export GOAL_MANAGER_DB_TIMEOUT=60
```

### Issue 2: LLM Decomposition Failures

**Symptoms**:
- Goals stuck in "decomposing" status
- `DecompositionError` in logs
- High LLM failure rate

**Causes**:
- LLM Runtime unavailable
- Rate limiting
- Invalid LLM responses
- Network issues

**Solutions**:

```bash
# Check LLM Runtime connectivity
curl http://llm-runtime:8000/health

# Review LLM logs
tail -f /var/log/agent_guru/llm_runtime.log

# Manually retry decomposition
python -m Agent_Guru.goal_manager.tools.retry_decomposition \
  --goal-id 550e8400-e29b-41d4-a716-446655440000

# Adjust retry configuration
export GOAL_MANAGER_MAX_RETRIES=5
export GOAL_MANAGER_BASE_DELAY=2.0
```

### Issue 3: Goals Not Resuming After Restart

**Symptoms**:
- IN_PROGRESS goals remain stuck after restart
- No execution activity after startup

**Causes**:
- Session Manager not loading goals
- Corrupted goal state
- Agent Orchestration unavailable

**Solutions**:

```bash
# Check session load logs
grep "session_loaded" /var/log/agent_guru/goal_manager.log

# Manually trigger resume
python -m Agent_Guru.goal_manager.tools.resume_goals

# Verify Agent Orchestration connectivity
curl http://agent-orchestration:8000/health
```

### Issue 4: Circular Dependency Errors

**Symptoms**:
- `ValidationError: Circular dependency detected`
- Cannot create or update goals

**Causes**:
- Goals depend on each other in a cycle
- Incorrect dependency specification

**Solutions**:

```bash
# Visualize dependency graph
python -m Agent_Guru.goal_manager.tools.visualize_dependencies \
  --output /tmp/dependencies.png

# Find circular dependencies
python -m Agent_Guru.goal_manager.tools.find_cycles

# Remove problematic dependencies
python -m Agent_Guru.goal_manager.tools.remove_dependency \
  --goal-id <goal-id> \
  --dependency-id <dep-id>
```

### Issue 5: Database Corruption

**Symptoms**:
- `corruption_detected` events in logs
- Goals marked as FAILED with "Data corruption" error
- Integrity check failures

**Causes**:
- Disk errors
- Improper shutdown
- SQLite bugs (rare)

**Solutions**:

```bash
# Check database integrity
sqlite3 /var/lib/agent_guru/goals.db "PRAGMA integrity_check;"

# Attempt automatic recovery
python -m Agent_Guru.goal_manager.tools.recover_db \
  --db /var/lib/agent_guru/goals.db

# If recovery fails, restore from backup
./scripts/restore_from_backup.sh /backup/goals_latest.db.gz

# Export recoverable data
sqlite3 /var/lib/agent_guru/goals.db ".dump" > /tmp/goals_dump.sql
```

### Issue 6: High Memory Usage

**Symptoms**:
- Goal Manager process using excessive memory
- OOM (Out of Memory) errors
- System slowdown

**Causes**:
- Memory leaks
- Large goal hierarchies
- Inefficient caching

**Solutions**:

```bash
# Monitor memory usage
ps aux | grep goal_manager

# Profile memory usage
python -m memory_profiler Agent_Guru/goal_manager/goal_manager.py

# Reduce cache sizes
export GOAL_MANAGER_DECOMPOSITION_CACHE_SIZE=50
export GOAL_MANAGER_QUERY_CACHE_TTL=60

# Restart Goal Manager
systemctl restart agent_guru_goal_manager
```

### Issue 7: GitHub Push Failures

**Symptoms**:
- Goals complete but no GitHub commits
- `Failed to commit to GitHub` warnings in logs

**Causes**:
- Git authentication issues
- Network connectivity
- Repository permissions
- Merge conflicts

**Solutions**:

```bash
# Check Git configuration
cd /path/to/agent_guru/repo
git config --list

# Test Git push manually
git push origin main

# Verify SSH keys or credentials
ssh -T git@github.com

# Check repository permissions
ls -la /path/to/agent_guru/repo/.git

# Manually commit pending changes
python -m Agent_Guru.goal_manager.tools.commit_pending
```

---

## Performance Tuning

### Database Optimization

**Enable WAL mode** (Write-Ahead Logging):
```sql
PRAGMA journal_mode=WAL;
```
Benefits: Better concurrency, faster writes

**Optimize cache size**:
```sql
PRAGMA cache_size=-64000;  -- 64MB cache
```

**Increase page size** (for new databases):
```sql
PRAGMA page_size=4096;  -- 4KB pages
VACUUM;  -- Apply changes
```

**Analyze query performance**:
```sql
EXPLAIN QUERY PLAN SELECT * FROM goals WHERE status='in_progress';
```

### Application-Level Optimization

**Connection pooling**:
```python
from Agent_Guru.goal_manager.goal_storage import GoalStoragePool

# Use connection pool for concurrent access
pool = GoalStoragePool(
    db_path="/var/lib/agent_guru/goals.db",
    pool_size=10,
    max_overflow=20
)
```

**Query result caching**:
```python
from functools import lru_cache

@lru_cache(maxsize=100)
async def get_goal_cached(goal_id: str):
    return await storage.get_goal(goal_id)
```

**Batch operations**:
```python
# Instead of individual updates
for goal in goals:
    await storage.update_goal(goal)

# Use batch update
await storage.batch_update_goals(goals)
```

### Concurrency Tuning

**Adjust concurrent goal execution**:
```yaml
performance:
  max_concurrent_goals: 20  # Increase for more parallelism
```

**Async operation tuning**:
```python
# Increase asyncio event loop workers
import asyncio
asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
```

### Resource Limits

**Set resource limits** (systemd):
```ini
[Service]
# Limit memory usage
MemoryMax=2G
MemoryHigh=1.5G

# Limit CPU usage
CPUQuota=200%  # 2 cores

# Limit file descriptors
LimitNOFILE=10000
```

### Performance Benchmarks

**Expected Performance**:
- Goal creation: < 10ms (p95)
- Goal query: < 5ms (p95)
- Goal decomposition: < 2s (p95)
- Goal execution: Depends on task complexity
- Database operations: < 1ms (p95)

**Run performance tests**:
```bash
python -m pytest Agent_Guru/goal_manager/tests/test_performance.py -v
```

---

## Security Considerations

### Database Security

**File permissions**:
```bash
# Restrict database access
chmod 600 /var/lib/agent_guru/goals.db
chown agent_guru:agent_guru /var/lib/agent_guru/goals.db
```

**Encryption at rest**:
```bash
# Use encrypted filesystem (LUKS)
cryptsetup luksFormat /dev/sdb1
cryptsetup open /dev/sdb1 goals_encrypted
mkfs.ext4 /dev/mapper/goals_encrypted
mount /dev/mapper/goals_encrypted /var/lib/agent_guru
```

**SQLite encryption** (using SQLCipher):
```python
from pysqlcipher3 import dbapi2 as sqlite

conn = sqlite.connect("/var/lib/agent_guru/goals.db")
conn.execute("PRAGMA key='your-encryption-key'")
```

### Access Control

**Run as dedicated user**:
```bash
# Create dedicated user
useradd -r -s /bin/false agent_guru

# Set ownership
chown -R agent_guru:agent_guru /var/lib/agent_guru
```

**Restrict API access**:
```python
# Require authentication for Goal Manager API
from Agent_Guru.security import require_auth

@require_auth
async def create_goal(request):
    # Only authenticated users can create goals
    pass
```

### Audit Logging

**Enable audit logging**:
```yaml
logging:
  audit_enabled: true
  audit_file: "/var/log/agent_guru/audit.log"
  audit_events:
    - goal_created
    - goal_modified
    - goal_cancelled
    - priority_changed
```

**Audit log format**:
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "event": "goal_created",
  "user_id": "user123",
  "goal_id": "550e8400-e29b-41d4-a716-446655440000",
  "ip_address": "192.168.1.100",
  "user_agent": "Agent_Guru/1.0"
}
```

### Secrets Management

**Store sensitive configuration securely**:
```bash
# Use environment variables
export GOAL_MANAGER_DB_ENCRYPTION_KEY=$(cat /etc/agent_guru/secrets/db_key)

# Or use secrets management service
export GOAL_MANAGER_DB_ENCRYPTION_KEY=$(vault kv get -field=key secret/goal_manager/db)
```

---

## Operational Runbooks

### Runbook 1: System Startup

**Objective**: Start Goal Manager and verify healthy operation

**Steps**:
1. Verify prerequisites
   ```bash
   # Check database exists
   ls -lh /var/lib/agent_guru/goals.db
   
   # Check Git repository
   cd /path/to/agent_guru/repo && git status
   
   # Check dependencies available
   curl http://llm-runtime:8000/health
   curl http://agent-orchestration:8000/health
   ```

2. Start Goal Manager
   ```bash
   systemctl start agent_guru_goal_manager
   ```

3. Verify startup
   ```bash
   # Check service status
   systemctl status agent_guru_goal_manager
   
   # Check logs for session_loaded event
   journalctl -u agent_guru_goal_manager -f | grep session_loaded
   
   # Verify health endpoint
   curl http://localhost:8080/health
   ```

4. Verify goal resumption
   ```bash
   # Check for resumed goals
   python -m Agent_Guru.goal_manager.tools.list_goals --status in_progress
   ```

**Expected Duration**: 2-5 minutes  
**Rollback**: `systemctl stop agent_guru_goal_manager`

### Runbook 2: System Shutdown

**Objective**: Gracefully shutdown Goal Manager

**Steps**:
1. Stop accepting new goals
   ```bash
   # Set maintenance mode
   curl -X POST http://localhost:8080/maintenance/enable
   ```

2. Wait for in-progress goals to complete (optional)
   ```bash
   # Monitor active executions
   watch -n 5 'curl -s http://localhost:8080/metrics | grep active_executions'
   ```

3. Shutdown Goal Manager
   ```bash
   systemctl stop agent_guru_goal_manager
   ```

4. Verify clean shutdown
   ```bash
   # Check for session_persisted event
   journalctl -u agent_guru_goal_manager | tail -20 | grep session_persisted
   
   # Verify no active processes
   ps aux | grep goal_manager
   ```

**Expected Duration**: 1-2 minutes  
**Force Shutdown**: `systemctl kill agent_guru_goal_manager`

### Runbook 3: Database Backup

**Objective**: Create verified backup of goal database

**Steps**:
1. Trigger backup
   ```bash
   /usr/local/bin/backup_goals.sh
   ```

2. Verify backup created
   ```bash
   ls -lh /backup/goal_manager/goals_*.db.gz | tail -1
   ```

3. Verify backup integrity
   ```bash
   LATEST_BACKUP=$(ls -t /backup/goal_manager/goals_*.db.gz | head -1)
   gunzip -c "$LATEST_BACKUP" | sqlite3 :memory: "PRAGMA integrity_check;"
   ```

4. Test restore (optional, in test environment)
   ```bash
   ./scripts/test_restore.sh "$LATEST_BACKUP"
   ```

**Expected Duration**: 1-5 minutes (depends on database size)  
**Frequency**: Daily at 2 AM

### Runbook 4: Handle Database Corruption

**Objective**: Recover from database corruption

**Steps**:
1. Detect corruption
   ```bash
   sqlite3 /var/lib/agent_guru/goals.db "PRAGMA integrity_check;"
   ```

2. Stop Goal Manager
   ```bash
   systemctl stop agent_guru_goal_manager
   ```

3. Backup corrupted database (for forensics)
   ```bash
   cp /var/lib/agent_guru/goals.db /tmp/goals_corrupted_$(date +%Y%m%d_%H%M%S).db
   ```

4. Attempt recovery
   ```bash
   python -m Agent_Guru.goal_manager.tools.recover_db \
     --db /var/lib/agent_guru/goals.db \
     --output /var/lib/agent_guru/goals_recovered.db
   ```

5. If recovery fails, restore from backup
   ```bash
   LATEST_BACKUP=$(ls -t /backup/goal_manager/goals_*.db.gz | head -1)
   gunzip -c "$LATEST_BACKUP" > /var/lib/agent_guru/goals.db
   ```

6. Verify integrity
   ```bash
   sqlite3 /var/lib/agent_guru/goals.db "PRAGMA integrity_check;"
   ```

7. Restart Goal Manager
   ```bash
   systemctl start agent_guru_goal_manager
   ```

8. Verify functionality
   ```bash
   python -m Agent_Guru.goal_manager.tools.verify_system
   ```

**Expected Duration**: 10-30 minutes  
**Escalation**: If recovery fails, contact database administrator

### Runbook 5: Scale Up for High Load

**Objective**: Handle increased goal creation and execution load

**Steps**:
1. Monitor current load
   ```bash
   # Check metrics
   curl -s http://localhost:9090/metrics | grep goal_manager_goals_total
   curl -s http://localhost:9090/metrics | grep goal_manager_active_executions
   ```

2. Increase concurrent execution limit
   ```bash
   # Update configuration
   sed -i 's/max_concurrent_goals: 10/max_concurrent_goals: 20/' \
     /etc/agent_guru/goal_manager.yaml
   ```

3. Increase database cache
   ```bash
   sqlite3 /var/lib/agent_guru/goals.db "PRAGMA cache_size=-128000;"  # 128MB
   ```

4. Restart Goal Manager
   ```bash
   systemctl restart agent_guru_goal_manager
   ```

5. Monitor performance
   ```bash
   # Watch execution latency
   watch -n 5 'curl -s http://localhost:9090/metrics | grep execution_duration'
   ```

**Expected Duration**: 5-10 minutes  
**Rollback**: Revert configuration changes and restart

### Runbook 6: Investigate Failed Goals

**Objective**: Diagnose and resolve goal execution failures

**Steps**:
1. Identify failed goals
   ```bash
   python -m Agent_Guru.goal_manager.tools.list_goals --status failed
   ```

2. Get goal details
   ```bash
   python -m Agent_Guru.goal_manager.tools.get_goal \
     --goal-id <goal-id> \
     --verbose
   ```

3. Review error logs
   ```bash
   journalctl -u agent_guru_goal_manager | grep <goal-id>
   ```

4. Check sub-goal failures
   ```bash
   python -m Agent_Guru.goal_manager.tools.get_goal_tree \
     --goal-id <goal-id> \
     --show-errors
   ```

5. Determine root cause
   - LLM decomposition failure?
   - Agent Orchestration task failure?
   - Dependency issue?
   - Resource constraint?

6. Take corrective action
   ```bash
   # Retry decomposition
   python -m Agent_Guru.goal_manager.tools.retry_decomposition --goal-id <goal-id>
   
   # Or manually fix and resume
   python -m Agent_Guru.goal_manager.tools.reset_goal --goal-id <goal-id>
   python -m Agent_Guru.goal_manager.tools.resume_goal --goal-id <goal-id>
   ```

**Expected Duration**: 15-60 minutes  
**Escalation**: If root cause unclear, escalate to development team

---

## Quick Reference

### Common Commands

```bash
# Start/stop/restart
systemctl start agent_guru_goal_manager
systemctl stop agent_guru_goal_manager
systemctl restart agent_guru_goal_manager

# View logs
journalctl -u agent_guru_goal_manager -f
tail -f /var/log/agent_guru/goal_manager.log

# Check health
curl http://localhost:8080/health

# List goals
python -m Agent_Guru.goal_manager.tools.list_goals

# Backup database
/usr/local/bin/backup_goals.sh

# Check database integrity
sqlite3 /var/lib/agent_guru/goals.db "PRAGMA integrity_check;"

# View metrics
curl http://localhost:9090/metrics
```

### Configuration Files

- **Main config**: `/etc/agent_guru/goal_manager.yaml`
- **Database**: `/var/lib/agent_guru/goals.db`
- **Logs**: `/var/log/agent_guru/goal_manager.log`
- **Backups**: `/backup/goal_manager/`
- **Systemd unit**: `/etc/systemd/system/agent_guru_goal_manager.service`

### Support Contacts

- **On-call Engineer**: [pager-duty-link]
- **Database Admin**: [contact-info]
- **Development Team**: [slack-channel]
- **Documentation**: [wiki-link]

---

## Appendix: Systemd Service Configuration

**File**: `/etc/systemd/system/agent_guru_goal_manager.service`

```ini
[Unit]
Description=Agent Guru Goal Manager
After=network.target postgresql.service
Wants=network-online.target

[Service]
Type=notify
User=agent_guru
Group=agent_guru
WorkingDirectory=/opt/agent_guru
Environment="GOAL_MANAGER_CONFIG=/etc/agent_guru/goal_manager.yaml"
ExecStart=/opt/agent_guru/venv/bin/python -m Agent_Guru.goal_manager
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=10s

# Resource limits
MemoryMax=2G
MemoryHigh=1.5G
CPUQuota=200%
LimitNOFILE=10000

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/agent_guru /var/log/agent_guru

[Install]
WantedBy=multi-user.target
```

**Enable and start**:
```bash
systemctl daemon-reload
systemctl enable agent_guru_goal_manager
systemctl start agent_guru_goal_manager
```

---

**Document Version**: 1.0  
**Last Updated**: 2024-01-15  
**Maintained By**: Agent Guru DevOps Team
