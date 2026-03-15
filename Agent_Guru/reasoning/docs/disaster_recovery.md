# Disaster Recovery Plan: Core Reasoning Engine

## Overview

This document defines the disaster recovery (DR) procedures for the Agent Guru Core Reasoning Engine.

- **RTO (Recovery Time Objective)**: < 1 hour
- **RPO (Recovery Point Objective)**: < 15 minutes
- **Backup Frequency**: Every 15 minutes (incremental), daily (full)
- **Retention**: 30 days

---

## Required Sections

- [Backup Procedures](#backup-procedures)
- [Restore Procedures](#restore-procedures)
- [Failover Procedures](#failover-procedures)
- [DR Testing Schedule](#dr-testing-schedule)

---

## Backup Procedures

### 1. PostgreSQL Database Backup

**Automated (every 15 minutes via Kubernetes CronJob):**

```bash
# Incremental WAL archiving (continuous)
# Configured in postgresql.conf:
#   archive_mode = on
#   archive_command = 'aws s3 cp %p s3://agent-guru-backups/wal/%f'

# Full backup (daily at 02:00 UTC)
kubectl create job --from=cronjob/pg-backup pg-backup-manual -n agent-guru
```

**Manual full backup:**

```bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
kubectl exec -n agent-guru deploy/postgres -- \
  pg_dump -U agent_guru agent_guru_db | \
  gzip > backup_${TIMESTAMP}.sql.gz

# Upload to S3
aws s3 cp backup_${TIMESTAMP}.sql.gz \
  s3://agent-guru-backups/postgres/${TIMESTAMP}/
```

**Verification:**

```bash
# Confirm backup exists and is non-empty
aws s3 ls s3://agent-guru-backups/postgres/ --recursive | tail -5
```

### 2. Redis Cache Backup

Redis holds ephemeral conversation state (TTL: 1 hour). Loss is acceptable — state rebuilds from PostgreSQL on next request.

**Optional snapshot (for warm cache restore):**

```bash
# Trigger BGSAVE
kubectl exec -n agent-guru deploy/redis -- redis-cli BGSAVE

# Copy dump.rdb
kubectl cp agent-guru/redis-pod:/data/dump.rdb \
  ./redis_backup_$(date +%Y%m%d_%H%M%S).rdb
```

### 3. Configuration Backup

All configuration is stored in Kubernetes Secrets and ConfigMaps, managed via GitOps (ArgoCD). The Git repository is the source of truth.

```bash
# Export current config state
kubectl get configmap,secret -n agent-guru -o yaml > \
  config_backup_$(date +%Y%m%d_%H%M%S).yaml
```

### 4. ML Model Backup

Trained models are stored in S3 and versioned. No additional backup needed beyond S3 versioning.

```
s3://agent-guru-models/
  intent_classifier/v{N}/
  ner_model/v{N}/
```

---

## Restore Procedures

### Full Restore (RTO target: < 1 hour)

**Step 1: Restore PostgreSQL (≈ 20 minutes)**

```bash
# 1. Identify the latest backup
LATEST=$(aws s3 ls s3://agent-guru-backups/postgres/ | \
  sort | tail -1 | awk '{print $4}')

# 2. Download backup
aws s3 cp s3://agent-guru-backups/postgres/${LATEST} ./restore.sql.gz

# 3. Restore to new/existing instance
gunzip -c restore.sql.gz | \
  kubectl exec -i -n agent-guru deploy/postgres -- \
  psql -U agent_guru agent_guru_db

# 4. Apply WAL logs for point-in-time recovery (if needed)
# Set recovery_target_time in recovery.conf, then restart PostgreSQL
```

**Step 2: Restore Redis (≈ 2 minutes)**

Redis state rebuilds automatically from PostgreSQL. For warm restore:

```bash
# Copy dump.rdb to Redis pod and restart
kubectl cp ./redis_backup.rdb agent-guru/redis-pod:/data/dump.rdb
kubectl rollout restart deployment/redis -n agent-guru
```

**Step 3: Restore Configuration (≈ 5 minutes)**

```bash
# Re-apply from Git (GitOps)
argocd app sync agent-guru-reasoning

# Or manually
kubectl apply -f config_backup.yaml
```

**Step 4: Restart Reasoning Engine (≈ 5 minutes)**

```bash
kubectl rollout restart deployment/reasoning-engine -n agent-guru
kubectl rollout status deployment/reasoning-engine -n agent-guru
```

**Step 5: Verify Health**

```bash
# Check all pods are running
kubectl get pods -n agent-guru

# Check health endpoint
curl http://reasoning-engine.agent-guru.svc/health

# Run smoke test
python -m pytest Agent_Guru/reasoning/tests/test_core_user_scenarios.py -x -q
```

### Partial Restore

**Database only (data corruption):**

Follow Step 1 above, then Step 4 (restart engine).

**Redis only (cache corruption):**

```bash
kubectl rollout restart deployment/redis -n agent-guru
# State rebuilds automatically — no data loss
```

---

## Failover Procedures

### Automatic Failover (Kubernetes)

The reasoning engine runs with `replicas: 3` and a `PodDisruptionBudget` of `minAvailable: 2`. Kubernetes automatically routes traffic away from failed pods.

**PostgreSQL HA** uses Patroni with automatic leader election:

```bash
# Check Patroni cluster status
kubectl exec -n agent-guru deploy/postgres -- patronictl list

# Manual failover (if automatic fails)
kubectl exec -n agent-guru deploy/postgres -- \
  patronictl failover agent-guru-postgres --master <current-leader> --force
```

**Redis HA** uses Redis Sentinel:

```bash
# Check sentinel status
kubectl exec -n agent-guru deploy/redis-sentinel -- \
  redis-cli -p 26379 SENTINEL masters

# Manual failover
kubectl exec -n agent-guru deploy/redis-sentinel -- \
  redis-cli -p 26379 SENTINEL failover agent-guru-redis
```

### Manual Failover to Backup Region

```bash
# 1. Update DNS to point to backup region
aws route53 change-resource-record-sets \
  --hosted-zone-id <ZONE_ID> \
  --change-batch file://failover-dns.json

# 2. Scale up backup region
kubectl scale deployment reasoning-engine \
  --replicas=3 -n agent-guru --context=backup-region

# 3. Verify traffic is flowing
kubectl logs -n agent-guru -l app=reasoning-engine --tail=50
```

### Graceful Degradation

The engine degrades gracefully when dependencies fail:

| Failure | Behavior |
|---------|----------|
| PostgreSQL down | Serve from Redis cache; new conversations use in-memory state |
| Redis down | Fall back to direct PostgreSQL reads; higher latency |
| LLM provider down | Fall back to rule-based intent detection |
| All LLMs down | Return rule-based responses for common commands |

---

## DR Testing Schedule

| Test | Frequency | Owner | Last Tested |
|------|-----------|-------|-------------|
| Full restore drill | Quarterly | Platform team | See runbook |
| Failover test (PostgreSQL) | Monthly | Platform team | See runbook |
| Failover test (Redis) | Monthly | Platform team | See runbook |
| Backup verification | Weekly (automated) | CI/CD | Automated |
| Graceful degradation test | Per release | Dev team | CI/CD |

### Quarterly DR Drill Procedure

1. Announce maintenance window (1 hour)
2. Snapshot current production state
3. Spin up isolated DR environment
4. Execute full restore from latest backup
5. Run smoke tests against restored environment
6. Measure actual RTO and RPO achieved
7. Document results and update this plan if needed
8. Tear down DR environment

### Automated Backup Verification (Weekly)

```bash
# Run as Kubernetes CronJob every Sunday 03:00 UTC
python -m pytest Agent_Guru/reasoning/tests/test_disaster_recovery.py \
  -m "unit" -v --tb=short
```

---

## Contacts and Escalation

| Role | Responsibility |
|------|---------------|
| On-call engineer | First responder, execute runbook |
| Platform lead | Escalation for infrastructure issues |
| Database admin | PostgreSQL/Redis recovery |

Incident response procedures are documented in `OPERATIONS_RUNBOOK.md`.
