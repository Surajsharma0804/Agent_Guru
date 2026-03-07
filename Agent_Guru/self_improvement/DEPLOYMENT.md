# Self-Improvement Engine Deployment Guide

## Overview

This guide covers deploying the self-improvement engine in production environments.

## Prerequisites

- Python 3.10+
- SQLite 3.35+
- Git 2.30+
- 500MB RAM minimum
- 1GB disk space minimum

## Installation

### 1. Install Dependencies

```bash
# Install core dependencies
pip install -r requirements.txt

# Verify installation
python -c "from Agent_Guru.self_improvement import SelfImprovementEngine; print('OK')"
```

### 2. Initialize Database

```bash
# Create data directory
mkdir -p data/self_improvement

# Initialize database schema
python -c "
from Agent_Guru.self_improvement import SelfImprovementEngine
engine = SelfImprovementEngine(
    storage_path='data/self_improvement/learning.db',
    git_repo_path='.'
)
print('Database initialized')
"
```

### 3. Configure Git Integration

```bash
# Initialize Git repository (if not already done)
git init

# Configure Git user
git config user.name "Agent Guru"
git config user.email "agent@guru.ai"

# Create initial commit
git add .
git commit -m "Initial commit"

# Add remote (optional)
git remote add origin https://github.com/your-org/agent-guru.git
```

## Configuration

### Environment Variables

```bash
# Storage configuration
export SELF_IMPROVEMENT_STORAGE_PATH="data/self_improvement/learning.db"
export SELF_IMPROVEMENT_BACKUP_PATH="data/self_improvement/backups"

# Git configuration
export SELF_IMPROVEMENT_GIT_ENABLED="true"
export SELF_IMPROVEMENT_GIT_REPO="."

# Learning parameters
export SELF_IMPROVEMENT_THRESHOLD="0.15"  # 15% minimum improvement
export SELF_IMPROVEMENT_WINDOW="100"      # Measure every 100 tasks

# Environment
export ENVIRONMENT="production"  # production, staging, or development
export DEBUG="false"
export TEST_MODE="false"
```

### Configuration File

Create `config/self_improvement.py`:

```python
from Agent_Guru.self_improvement.deployment_config import DeploymentConfig

# Production configuration
config = DeploymentConfig.for_production()

# Or custom configuration
config = DeploymentConfig(
    storage_path="data/self_improvement/learning.db",
    git_enabled=True,
    improvement_threshold=0.15,
    measurement_window=100,
    environment="production"
)
```

## Deployment Options

### Option 1: Standalone Service

```python
# standalone_service.py
from Agent_Guru.self_improvement import SelfImprovementEngine
from Agent_Guru.self_improvement.deployment_config import get_config
from Agent_Guru.self_improvement.health_check import HealthChecker
from Agent_Guru.self_improvement.monitoring import ImprovementMonitor
import time

# Load configuration
config = get_config()

# Initialize engine
engine = SelfImprovementEngine(
    storage_path=config.storage_path,
    git_repo_path=config.git_repo_path,
    improvement_threshold=config.improvement_threshold,
    measurement_window=config.measurement_window
)

# Initialize monitoring
health_checker = HealthChecker(config.storage_path, config)
monitor = ImprovementMonitor(config.storage_path, config)

# Health check loop
while True:
    # Check health
    health = health_checker.check_health()
    print(f"Health: {health.status.value}")
    
    # Check for alerts
    alerts = monitor.check_all()
    for alert in alerts:
        print(f"Alert: {alert.title} - {alert.message}")
    
    # Wait for next check
    time.sleep(config.health_check_interval_seconds)
```

Run:
```bash
python standalone_service.py
```

### Option 2: Integrated with Agent Guru

```python
# In your Agent Guru initialization
from Agent_Guru.self_improvement import SelfImprovementEngine
from Agent_Guru.self_improvement.graceful_degradation import SelfImprovementEngineWrapper
from Agent_Guru.self_improvement.deployment_config import get_config

# Load configuration
config = get_config()

# Initialize engine
engine = SelfImprovementEngine(
    storage_path=config.storage_path,
    git_repo_path=config.git_repo_path,
    improvement_threshold=config.improvement_threshold,
    measurement_window=config.measurement_window
)

# Wrap with graceful degradation
engine = SelfImprovementEngineWrapper(engine)

# Use in agent orchestration
from Agent_Guru.agents import AgentOrchestrator
orchestrator = AgentOrchestrator(self_improvement_engine=engine)
```

### Option 3: Docker Container

Create `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY Agent_Guru/ ./Agent_Guru/
COPY config/ ./config/

# Create data directory
RUN mkdir -p data/self_improvement

# Set environment variables
ENV ENVIRONMENT=production
ENV SELF_IMPROVEMENT_STORAGE_PATH=data/self_improvement/learning.db

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "from Agent_Guru.self_improvement.health_check import HealthChecker; \
                 checker = HealthChecker('data/self_improvement/learning.db'); \
                 result = checker.check_health(); \
                 exit(0 if result.status.value == 'healthy' else 1)"

# Run service
CMD ["python", "standalone_service.py"]
```

Build and run:
```bash
docker build -t agent-guru-self-improvement .
docker run -d \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.git:/app/.git \
  --name self-improvement \
  agent-guru-self-improvement
```

## Monitoring

### Health Checks

```python
from Agent_Guru.self_improvement.health_check import HealthChecker

checker = HealthChecker('data/self_improvement/learning.db')
health = checker.check_health()

print(f"Status: {health.status.value}")
print(f"Message: {health.message}")
print(f"Details: {health.details}")
```

### Metrics Dashboard

```python
from Agent_Guru.self_improvement.monitoring import ImprovementMonitor

monitor = ImprovementMonitor('data/self_improvement/learning.db')
metrics = monitor.get_dashboard_metrics()

print(f"Total tasks: {metrics['overall']['total_tasks']}")
print(f"Success rate: {metrics['overall']['success_rate']:.1f}%")
print(f"Latest improvement: {metrics['improvement']['latest']:.1%}")
```

### Alerting

```python
from Agent_Guru.self_improvement.monitoring import ImprovementMonitor, Alert

def alert_handler(alert: Alert):
    """Custom alert handler."""
    print(f"[{alert.level.value.upper()}] {alert.title}")
    print(f"Message: {alert.message}")
    print(f"Details: {alert.details}")
    
    # Send to monitoring system (e.g., Prometheus, Grafana, PagerDuty)
    # send_to_monitoring_system(alert)

monitor = ImprovementMonitor(
    'data/self_improvement/learning.db',
    alert_callback=alert_handler
)

# Check for alerts
alerts = monitor.check_all()
```

## Backup and Recovery

### Automated Backups

```python
from Agent_Guru.self_improvement.database_schema import backup_database
from datetime import datetime
import shutil

# Backup database
backup_path = f"data/self_improvement/backups/learning_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
shutil.copy2('data/self_improvement/learning.db', backup_path)
print(f"Backup created: {backup_path}")
```

### Restore from Backup

```bash
# Stop service
docker stop self-improvement

# Restore database
cp data/self_improvement/backups/learning_20260307_120000.db data/self_improvement/learning.db

# Start service
docker start self-improvement
```

## Performance Tuning

### Database Optimization

```sql
-- Run periodically to optimize database
VACUUM;
ANALYZE;

-- Create additional indexes if needed
CREATE INDEX IF NOT EXISTS idx_task_executions_timestamp 
ON task_executions(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_failures_timestamp 
ON failures(timestamp DESC);
```

### Memory Optimization

```python
# Limit cache sizes in configuration
config = DeploymentConfig(
    max_pattern_cache_size=5000,  # Reduce from 10000
    max_memory_usage_mb=250,      # Reduce from 500
)
```

### Disk Space Management

```bash
# Prune old data (keep last 30 days)
python -c "
from Agent_Guru.self_improvement import SelfImprovementEngine
engine = SelfImprovementEngine('data/self_improvement/learning.db', '.')
# Implement pruning logic
"
```

## Troubleshooting

### Issue: Database locked

**Cause:** Multiple processes accessing database simultaneously

**Solution:**
```python
# Use connection pooling
from Agent_Guru.self_improvement.connection_pool import ConnectionPool

pool = ConnectionPool('data/self_improvement/learning.db', max_connections=5)
```

### Issue: Git push failures

**Cause:** Network issues or authentication problems

**Solution:**
```bash
# Check Git credentials
git config --list

# Test connectivity
git fetch origin

# Disable Git temporarily
export SELF_IMPROVEMENT_GIT_ENABLED="false"
```

### Issue: High memory usage

**Cause:** Large pattern cache or memory leaks

**Solution:**
```python
# Reduce cache size
config = DeploymentConfig(max_pattern_cache_size=1000)

# Monitor memory
from Agent_Guru.self_improvement.health_check import HealthChecker
checker = HealthChecker('data/self_improvement/learning.db')
health = checker._check_memory()
print(f"Memory usage: {health.details['memory_mb']:.1f}MB")
```

### Issue: Insufficient improvement

**Cause:** Not enough diverse tasks or poor task quality

**Solution:**
1. Ensure task diversity (different task types)
2. Verify failures are being properly categorized
3. Check that context is being captured
4. Review meta-learner patterns
5. Increase measurement window if needed

## Security

### API Key Storage

```python
# Store API keys securely (not in database)
import keyring

keyring.set_password("agent_guru", "openai_api_key", "sk-...")
api_key = keyring.get_password("agent_guru", "openai_api_key")
```

### Database Encryption

```bash
# Use SQLCipher for encrypted database
pip install sqlcipher3

# Encrypt existing database
sqlcipher data/self_improvement/learning.db
> ATTACH DATABASE 'encrypted.db' AS encrypted KEY 'your-key';
> SELECT sqlcipher_export('encrypted');
> DETACH DATABASE encrypted;
```

### Access Control

```python
# Restrict file permissions
import os
os.chmod('data/self_improvement/learning.db', 0o600)  # Owner read/write only
```

## Scaling

### Horizontal Scaling

For multiple Agent Guru instances:

1. Use shared database (PostgreSQL instead of SQLite)
2. Implement distributed locking
3. Coordinate Git commits

```python
# Example with PostgreSQL
from Agent_Guru.self_improvement import SelfImprovementEngine

engine = SelfImprovementEngine(
    storage_path="postgresql://user:pass@host:5432/learning",
    git_repo_path="."
)
```

### Vertical Scaling

For high-volume deployments:

1. Increase database cache size
2. Use SSD storage
3. Allocate more memory
4. Use connection pooling

## Maintenance

### Regular Tasks

**Daily:**
- Check health status
- Review alerts
- Monitor disk space

**Weekly:**
- Review improvement metrics
- Analyze failure patterns
- Optimize database (VACUUM)

**Monthly:**
- Backup database
- Review and prune old data
- Update dependencies
- Security audit

### Upgrade Procedure

```bash
# 1. Backup current database
cp data/self_improvement/learning.db data/self_improvement/learning.db.backup

# 2. Stop service
docker stop self-improvement

# 3. Update code
git pull origin main

# 4. Run migrations
python -c "
from Agent_Guru.self_improvement.migrations import run_migrations
run_migrations('data/self_improvement/learning.db')
"

# 5. Start service
docker start self-improvement

# 6. Verify health
python -c "
from Agent_Guru.self_improvement.health_check import HealthChecker
checker = HealthChecker('data/self_improvement/learning.db')
health = checker.check_health()
print(f'Status: {health.status.value}')
"
```

## Support

For issues or questions:

1. Check logs: `docker logs self-improvement`
2. Review health status: `python -m Agent_Guru.self_improvement.health_check`
3. Consult documentation: `.kiro/specs/self-improvement-engine/`
4. Open GitHub issue: https://github.com/Surajsharma0804/Agent_Guru/issues

## References

- **Specification:** `.kiro/specs/self-improvement-engine/`
- **Validation Results:** `Agent_Guru/self_improvement/validation/VALIDATION_SUMMARY.md`
- **API Documentation:** `Agent_Guru/self_improvement/README.md`
- **Benchmarks:** `Agent_Guru/self_improvement/benchmarks/`
