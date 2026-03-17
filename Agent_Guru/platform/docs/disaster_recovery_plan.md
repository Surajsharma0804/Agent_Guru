# Disaster Recovery Plan — Agent Guru Platform Integration

## Overview

This document defines backup, recovery, failover, and data retention procedures for the Agent Guru Platform Integration service.

**RTO (Recovery Time Objective)**: <1 hour  
**RPO (Recovery Point Objective)**: <15 minutes  
**Uptime Target**: 99.9% (≤8.7 hours downtime/year)

---

## 1. Backup Procedures

### 1.1 What to Back Up

| Data | Location | Frequency | Retention |
|------|----------|-----------|-----------|
| Audit logs | `/var/log/agent_guru/audit/` | Continuous (append-only) | 90 days |
| Permission config | `/etc/agent_guru/permissions.yaml` | On every change | 30 versions |
| Security config | `/etc/agent_guru/security.yaml` | On every change | 30 versions |
| Compliance reports | `/var/log/agent_guru/compliance/` | Daily | 1 year |
| Application state | `/home/agent_guru/workspace/` | Hourly | 7 days |

### 1.2 Automated Backup Script

```bash
#!/bin/bash
# /opt/agent-guru/scripts/backup.sh
# Run via cron: 0 * * * * /opt/agent-guru/scripts/backup.sh

set -euo pipefail

BACKUP_DIR="/var/backups/agent_guru/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup configs
cp -r /etc/agent_guru/ "$BACKUP_DIR/config/"

# Backup audit logs (compressed)
tar -czf "$BACKUP_DIR/audit_logs.tar.gz" /var/log/agent_guru/audit/

# Backup workspace state
tar -czf "$BACKUP_DIR/workspace.tar.gz" /home/agent_guru/workspace/

# Remove backups older than 7 days
find /var/backups/agent_guru/ -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true

echo "Backup completed: $BACKUP_DIR"
```

### 1.3 Verify Backups

```bash
# Verify backup integrity
tar -tzf /var/backups/agent_guru/latest/audit_logs.tar.gz > /dev/null && echo "OK"
tar -tzf /var/backups/agent_guru/latest/workspace.tar.gz > /dev/null && echo "OK"
```

---

## 2. Recovery Procedures

### 2.1 Service Crash Recovery

The service is configured with `Restart=always` in systemd, so it auto-restarts within 5 seconds.

**Manual recovery**:
```bash
# Check service status
sudo systemctl status agent-guru-platform

# View recent logs
sudo journalctl -u agent-guru-platform -n 100 --no-pager

# Restart service
sudo systemctl restart agent-guru-platform

# Verify health
curl http://localhost:8080/health
```

### 2.2 Configuration Corruption Recovery

```bash
# Restore config from backup
LATEST_BACKUP=$(ls -t /var/backups/agent_guru/ | head -1)
sudo cp /var/backups/agent_guru/$LATEST_BACKUP/config/permissions.yaml \
        /etc/agent_guru/permissions.yaml

# Validate restored config
python3 -c "
import yaml
with open('/etc/agent_guru/permissions.yaml') as f:
    cfg = yaml.safe_load(f)
print('Config valid:', cfg['version'])
"

# Reload service
sudo systemctl reload agent-guru-platform
```

### 2.3 Full System Recovery

```bash
# 1. Stop service
sudo systemctl stop agent-guru-platform

# 2. Restore from backup
BACKUP_DATE="20260316_120000"  # Replace with target backup
BACKUP_DIR="/var/backups/agent_guru/$BACKUP_DATE"

sudo tar -xzf "$BACKUP_DIR/workspace.tar.gz" -C /
sudo cp -r "$BACKUP_DIR/config/" /etc/agent_guru/

# 3. Restore audit logs (if needed)
sudo tar -xzf "$BACKUP_DIR/audit_logs.tar.gz" -C /

# 4. Verify permissions
sudo chown -R agent_guru:agent_guru /home/agent_guru/workspace/
sudo chown -R agent_guru:agent_guru /var/log/agent_guru/

# 5. Start service
sudo systemctl start agent-guru-platform

# 6. Verify health
sleep 5
curl http://localhost:8080/health
```

### 2.4 Data Corruption Recovery

If audit logs are corrupted:
```bash
# Audit logs are append-only JSONL — truncate at last valid line
python3 << 'EOF'
import json

log_file = "/var/log/agent_guru/audit/audit.jsonl"
valid_lines = []

with open(log_file) as f:
    for line in f:
        try:
            json.loads(line.strip())
            valid_lines.append(line)
        except json.JSONDecodeError:
            print(f"Corrupt line found, stopping at {len(valid_lines)} valid entries")
            break

# Write back only valid lines
with open(log_file + ".recovered", "w") as f:
    f.writelines(valid_lines)

print(f"Recovered {len(valid_lines)} valid audit entries")
EOF
```

---

## 3. Failover Procedures

### 3.1 Single-Node Failover (Systemd)

Systemd handles automatic restart. For manual failover to a standby node:

```bash
# On primary (if accessible)
sudo systemctl stop agent-guru-platform

# Sync state to standby
rsync -avz /home/agent_guru/workspace/ standby-host:/home/agent_guru/workspace/
rsync -avz /etc/agent_guru/ standby-host:/etc/agent_guru/

# On standby
ssh standby-host "sudo systemctl start agent-guru-platform"
ssh standby-host "curl http://localhost:8080/health"
```

### 3.2 Kubernetes Failover

Kubernetes handles pod failover automatically. For node failure:

```bash
# Check pod status
kubectl get pods -n agent-guru -l app=agent-guru-platform

# Force reschedule if stuck
kubectl delete pod -n agent-guru -l app=agent-guru-platform

# Scale up replicas temporarily
kubectl scale deployment agent-guru-platform -n agent-guru --replicas=3

# Verify rollout
kubectl rollout status deployment/agent-guru-platform -n agent-guru
```

### 3.3 Emergency Lockdown

If a security incident is detected, activate lockdown mode:

```python
from Agent_Guru.platform.permissions.model_manager import PermissionModelManager

manager = PermissionModelManager(config_path="/etc/agent_guru/permissions.yaml")
manager.load()
manager.enable_lockdown()  # Restricts to read-only critical operations
```

Or via config:
```bash
# Edit config to enable lockdown
sed -i 's/enabled: false/enabled: true/' /etc/agent_guru/permissions.yaml
sudo systemctl reload agent-guru-platform
```

---

## 4. Data Retention Policies

| Data Type | Retention | Deletion Method |
|-----------|-----------|-----------------|
| Audit logs | 90 days | Automatic archival + deletion |
| Compliance reports | 1 year | Manual review before deletion |
| Backup archives | 7 days | Automatic cron deletion |
| Performance metrics | 30 days | Prometheus retention policy |
| Application logs | 30 days | Logrotate |

### Logrotate Configuration

`/etc/logrotate.d/agent-guru`:
```
/var/log/agent_guru/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        systemctl reload agent-guru-platform > /dev/null 2>&1 || true
    endscript
}
```

---

## 5. Disaster Recovery Drills

Run quarterly to verify procedures work:

```bash
# DR Drill Checklist
# 1. Simulate service crash
sudo systemctl stop agent-guru-platform
sleep 10
sudo systemctl start agent-guru-platform
curl http://localhost:8080/health  # Must return healthy

# 2. Simulate config corruption
cp /etc/agent_guru/permissions.yaml /tmp/permissions.yaml.bak
echo "CORRUPTED" > /etc/agent_guru/permissions.yaml
sudo systemctl restart agent-guru-platform  # Should fail gracefully
cp /tmp/permissions.yaml.bak /etc/agent_guru/permissions.yaml
sudo systemctl restart agent-guru-platform
curl http://localhost:8080/health  # Must return healthy

# 3. Verify backup restore
LATEST=$(ls -t /var/backups/agent_guru/ | head -1)
tar -tzf /var/backups/agent_guru/$LATEST/audit_logs.tar.gz > /dev/null
echo "Backup integrity: OK"
```

---

## 6. Incident Response

### Severity Levels

| Level | Description | Response Time | Escalation |
|-------|-------------|---------------|------------|
| P1 Critical | Service down, data loss | <15 min | Immediate |
| P2 High | Degraded performance, security alert | <1 hour | Within 30 min |
| P3 Medium | Non-critical component failure | <4 hours | Next business day |
| P4 Low | Minor issue, no user impact | <24 hours | Weekly review |

### P1 Response Steps

1. **Detect**: Alert fires in Prometheus/Grafana
2. **Assess**: Check `/health` endpoint and recent logs
3. **Contain**: Enable lockdown mode if security incident
4. **Recover**: Follow recovery procedure above
5. **Verify**: Confirm health endpoint returns `"status": "healthy"`
6. **Document**: Write incident report within 24 hours

### Contact

- On-call engineer: Check PagerDuty rotation
- Escalation: Engineering lead
- Security incidents: Security team immediately
