# Core Reasoning Engine - Operations Runbook

## Overview

This runbook provides step-by-step procedures for common operational tasks, troubleshooting, incident response, and scaling operations for the Agent Guru Core Reasoning Engine.

## Table of Contents

1. [Common Operational Tasks](#common-operational-tasks)
2. [Troubleshooting Procedures](#troubleshooting-procedures)
3. [Incident Response Procedures](#incident-response-procedures)
4. [Scaling Procedures](#scaling-procedures)
5. [Maintenance Windows](#maintenance-windows)
6. [Emergency Contacts](#emergency-contacts)

## Common Operational Tasks

### Task 1: Check System Health

**Frequency:** Continuous (automated monitoring)

**Procedure:**

```bash
# Check pod health
kubectl get pods -n agent-guru-prod

# Check service endpoints
kubectl get svc -n agent-guru-prod

# Check ingress status
kubectl get ingress -n agent-guru-prod

# Test health endpoint
curl -f https://api.agent-guru.com/v1/reasoning/health

# Check metrics
curl https://api.agent-guru.com/metrics | grep -E "(reasoning_latency|reasoning_requests_total|reasoning_errors_total)"
```

**Expected Results:**
- All pods in `Running` state
- Health endpoint returns 200 OK
- P95 latency <1.5s
- Error rate <1%

### Task 2: View Application Logs

**Frequency:** As needed

**Procedure:**

```bash
# View recent logs
kubectl logs -f deployment/reasoning-engine -n agent-guru-prod --tail=100

# View logs for specific pod
kubectl logs <pod-name> -n agent-guru-prod

# View logs with timestamp
kubectl logs deployment/reasoning-engine -n agent-guru-prod --timestamps=true

# Search for errors
kubectl logs deployment/reasoning-engine -n agent-guru-prod | grep ERROR

# Export logs to file
kubectl logs deployment/reasoning-engine -n agent-guru-prod > logs.txt
```

**Log Levels:**
- `DEBUG` - Detailed debugging information
- `INFO` - General informational messages
- `WARNING` - Warning messages (potential issues)
- `ERROR` - Error messages (failures)
- `CRITICAL` - Critical errors (system failures)

### Task 3: Restart Services

**Frequency:** As needed

**Procedure:**

```bash
# Graceful restart (rolling update)
kubectl rollout restart deployment/reasoning-engine -n agent-guru-prod

# Monitor restart progress
kubectl rollout status deployment/reasoning-engine -n agent-guru-prod

# Verify pods are healthy
kubectl get pods -n agent-guru-prod
kubectl logs deployment/reasoning-engine -n agent-guru-prod --tail=50
```

**When to Restart:**
- After configuration changes
- After secrets rotation
- Memory leaks detected
- Degraded performance
- Stuck connections

### Task 4: Update Configuration

**Frequency:** As needed

**Procedure:**

```bash
# Edit Helm values
vim values-prod.yaml

# Preview changes
helm diff upgrade reasoning-engine agent-guru/reasoning-engine \
  --namespace=agent-guru-prod \
  --values=values-prod.yaml

# Apply changes
helm upgrade reasoning-engine agent-guru/reasoning-engine \
  --namespace=agent-guru-prod \
  --values=values-prod.yaml \
  --wait

# Verify deployment
kubectl rollout status deployment/reasoning-engine -n agent-guru-prod
```

**Configuration Changes Requiring Restart:**
- Environment variables
- Resource limits
- Secrets
- Feature flags

### Task 5: Scale Services Manually

**Frequency:** As needed

**Procedure:**

```bash
# Scale up
kubectl scale deployment/reasoning-engine --replicas=10 -n agent-guru-prod

# Scale down
kubectl scale deployment/reasoning-engine --replicas=3 -n agent-guru-prod

# Verify scaling
kubectl get pods -n agent-guru-prod
kubectl get hpa -n agent-guru-prod
```

**When to Scale Manually:**
- Anticipated traffic spike (product launch, marketing campaign)
- Performance degradation
- Cost optimization during low-traffic periods
- Testing autoscaling behavior

### Task 6: Rotate Secrets

**Frequency:** Every 90 days (automated) or as needed

**Procedure:**

```bash
# Update secret in secrets manager
aws secretsmanager update-secret \
  --secret-id prod/reasoning-engine/openai-api-key \
  --secret-string "new-api-key-value"

# Delete old Kubernetes secret
kubectl delete secret reasoning-engine-secrets -n agent-guru-prod

# Create new Kubernetes secret
kubectl create secret generic reasoning-engine-secrets \
  --namespace=agent-guru-prod \
  --from-literal=database-url="$(aws secretsmanager get-secret-value --secret-id prod/reasoning-engine/database-url --query SecretString --output text)" \
  --from-literal=redis-url="$(aws secretsmanager get-secret-value --secret-id prod/reasoning-engine/redis-url --query SecretString --output text)" \
  --from-literal=openai-api-key="$(aws secretsmanager get-secret-value --secret-id prod/reasoning-engine/openai-api-key --query SecretString --output text)"

# Restart pods to pick up new secrets
kubectl rollout restart deployment/reasoning-engine -n agent-guru-prod

# Verify pods are healthy
kubectl get pods -n agent-guru-prod
```

### Task 7: Database Backup and Restore

**Frequency:** Daily (automated), manual as needed

**Backup Procedure:**

```bash
# Manual backup (AWS RDS example)
aws rds create-db-snapshot \
  --db-instance-identifier agent-guru-prod-db \
  --db-snapshot-identifier agent-guru-prod-manual-$(date +%Y%m%d-%H%M%S)

# Verify backup
aws rds describe-db-snapshots \
  --db-instance-identifier agent-guru-prod-db
```

**Restore Procedure:**

```bash
# List available snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier agent-guru-prod-db

# Restore from snapshot (creates new instance)
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier agent-guru-prod-db-restored \
  --db-snapshot-identifier agent-guru-prod-manual-20260222-120000

# Update connection string in secrets
# Follow Task 6 to update secrets
```

### Task 8: Clear Cache

**Frequency:** As needed

**Procedure:**

```bash
# Connect to Redis
kubectl exec -it deployment/reasoning-engine -n agent-guru-prod -- redis-cli -h <redis-host>

# Clear all caches (use with caution)
FLUSHALL

# Clear specific cache pattern
KEYS "intent:*" | xargs DEL
KEYS "tool:*" | xargs DEL

# Verify cache cleared
DBSIZE
```

**When to Clear Cache:**
- After model updates
- After tool registry changes
- Stale data issues
- Testing cache behavior

## Troubleshooting Procedures

### Issue 1: High Latency (P95 >2s)

**Symptoms:**
- Slow response times
- User complaints
- Latency alerts firing

**Diagnosis:**

```bash
# Check current latency
curl https://api.agent-guru.com/metrics | grep reasoning_latency_seconds

# Check resource utilization
kubectl top pods -n agent-guru-prod
kubectl top nodes

# Check database performance
# - Query slow query log
# - Check connection pool utilization

# Check Redis performance
kubectl exec -it deployment/reasoning-engine -n agent-guru-prod -- redis-cli INFO stats

# Check LLM API latency
# - Review external API monitoring
# - Check rate limiting status
```

**Resolution:**

1. **If CPU/Memory high:**
   ```bash
   # Scale up immediately
   kubectl scale deployment/reasoning-engine --replicas=10 -n agent-guru-prod
   ```

2. **If database slow:**
   ```bash
   # Check slow queries
   # Optimize queries or add indexes
   # Scale database instance if needed
   ```

3. **If LLM API slow:**
   ```bash
   # Switch to faster LLM backend
   # Increase timeout limits
   # Enable more aggressive caching
   ```

4. **If cache miss rate high:**
   ```bash
   # Increase cache TTL
   # Warm up cache with common queries
   ```

### Issue 2: High Error Rate (>5%)

**Symptoms:**
- Increased error responses
- Error rate alerts firing
- Failed requests

**Diagnosis:**

```bash
# Check error logs
kubectl logs deployment/reasoning-engine -n agent-guru-prod | grep ERROR | tail -100

# Check error metrics
curl https://api.agent-guru.com/metrics | grep reasoning_errors_total

# Check error types
kubectl logs deployment/reasoning-engine -n agent-guru-prod | grep ERROR | awk '{print $5}' | sort | uniq -c | sort -rn
```

**Resolution:**

1. **If database connection errors:**
   ```bash
   # Check database status
   aws rds describe-db-instances --db-instance-identifier agent-guru-prod-db
   
   # Verify security groups
   # Check connection pool settings
   # Restart pods if connections stuck
   kubectl rollout restart deployment/reasoning-engine -n agent-guru-prod
   ```

2. **If LLM API errors:**
   ```bash
   # Check API status
   # Verify API keys are valid
   # Enable fallback to alternative LLM
   # Increase retry attempts
   ```

3. **If validation errors:**
   ```bash
   # Review recent input patterns
   # Check for malformed requests
   # Update validation rules if needed
   ```

### Issue 3: Memory Leak

**Symptoms:**
- Increasing memory usage over time
- OOMKilled pods
- Degraded performance

**Diagnosis:**

```bash
# Check memory usage trend
kubectl top pods -n agent-guru-prod --sort-by=memory

# Check pod restarts
kubectl get pods -n agent-guru-prod

# Check OOMKilled events
kubectl get events -n agent-guru-prod | grep OOMKilled

# Profile memory usage
kubectl exec -it deployment/reasoning-engine -n agent-guru-prod -- python -m memory_profiler app.py
```

**Resolution:**

1. **Immediate mitigation:**
   ```bash
   # Restart pods
   kubectl rollout restart deployment/reasoning-engine -n agent-guru-prod
   
   # Increase memory limits temporarily
   kubectl set resources deployment/reasoning-engine --limits=memory=8Gi -n agent-guru-prod
   ```

2. **Long-term fix:**
   - Profile application to identify leak
   - Fix memory leak in code
   - Deploy patched version
   - Restore original memory limits

### Issue 4: Database Connection Pool Exhausted

**Symptoms:**
- "Connection pool exhausted" errors
- Slow database queries
- Timeouts

**Diagnosis:**

```bash
# Check connection pool metrics
curl https://api.agent-guru.com/metrics | grep db_pool

# Check active connections
kubectl exec -it deployment/reasoning-engine -n agent-guru-prod -- \
  psql ${DATABASE_URL} -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
```

**Resolution:**

```bash
# Increase connection pool size
# Edit values-prod.yaml:
# env:
#   - name: DB_POOL_SIZE
#     value: "40"  # Increase from 20

# Apply changes
helm upgrade reasoning-engine agent-guru/reasoning-engine \
  --namespace=agent-guru-prod \
  --values=values-prod.yaml

# Or scale database instance to support more connections
```

### Issue 5: Pods Stuck in CrashLoopBackOff

**Symptoms:**
- Pods repeatedly restarting
- CrashLoopBackOff status
- Application not starting

**Diagnosis:**

```bash
# Check pod status
kubectl get pods -n agent-guru-prod

# Check pod logs
kubectl logs <pod-name> -n agent-guru-prod --previous

# Check pod events
kubectl describe pod <pod-name> -n agent-guru-prod
```

**Resolution:**

1. **If configuration error:**
   ```bash
   # Fix configuration
   # Update Helm values
   # Redeploy
   ```

2. **If missing secrets:**
   ```bash
   # Verify secrets exist
   kubectl get secrets -n agent-guru-prod
   
   # Recreate secrets if missing
   # Follow Task 6
   ```

3. **If resource limits too low:**
   ```bash
   # Increase resource limits
   kubectl set resources deployment/reasoning-engine \
     --limits=cpu=4000m,memory=8Gi \
     -n agent-guru-prod
   ```

## Incident Response Procedures

### Severity Levels

- **SEV1 (Critical):** Complete service outage, data loss
- **SEV2 (High):** Partial outage, major degradation
- **SEV3 (Medium):** Minor degradation, workaround available
- **SEV4 (Low):** Cosmetic issues, no user impact

### Incident Response Workflow

1. **Detection** - Alert fires or user report
2. **Triage** - Assess severity and impact
3. **Escalation** - Page on-call engineer for SEV1/SEV2
4. **Investigation** - Diagnose root cause
5. **Mitigation** - Implement fix or workaround
6. **Resolution** - Verify issue resolved
7. **Postmortem** - Document incident and improvements

### SEV1: Complete Service Outage

**Immediate Actions:**

1. **Page on-call engineer**
   ```bash
   # PagerDuty will auto-page based on alerts
   # Or manually trigger incident
   ```

2. **Check system status**
   ```bash
   kubectl get pods -n agent-guru-prod
   kubectl get nodes
   kubectl get svc -n agent-guru-prod
   ```

3. **Check recent changes**
   ```bash
   # Check recent deployments
   helm history reasoning-engine -n agent-guru-prod
   
   # Check recent commits
   git log --oneline -10
   ```

4. **Rollback if recent deployment**
   ```bash
   helm rollback reasoning-engine -n agent-guru-prod
   ```

5. **Scale up if capacity issue**
   ```bash
   kubectl scale deployment/reasoning-engine --replicas=20 -n agent-guru-prod
   ```

6. **Enable degraded mode if needed**
   ```bash
   # Disable non-critical features
   # Route to backup systems
   # Enable maintenance page
   ```

**Communication:**

- Post incident in #incidents Slack channel
- Update status page: https://status.agent-guru.com
- Notify stakeholders every 30 minutes

### SEV2: Partial Outage or Major Degradation

**Immediate Actions:**

1. **Assess impact**
   - What percentage of requests affected?
   - Which features impacted?
   - Which users affected?

2. **Implement workaround**
   - Enable fallback systems
   - Disable problematic features
   - Route traffic to healthy instances

3. **Investigate root cause**
   - Review logs and metrics
   - Check external dependencies
   - Profile performance

4. **Deploy fix**
   - Implement and test fix
   - Deploy to staging first
   - Deploy to production with monitoring

**Communication:**

- Post incident in #incidents Slack channel
- Update status page if user-facing
- Notify stakeholders every hour

### SEV3: Minor Degradation

**Actions:**

1. **Document issue**
2. **Create ticket for fix**
3. **Implement workaround if available**
4. **Schedule fix in next sprint**

**Communication:**

- Post in #engineering Slack channel
- No status page update needed

## Scaling Procedures

### Horizontal Scaling (Add/Remove Pods)

**Manual Scaling:**

```bash
# Scale up
kubectl scale deployment/reasoning-engine --replicas=15 -n agent-guru-prod

# Scale down
kubectl scale deployment/reasoning-engine --replicas=5 -n agent-guru-prod
```

**Autoscaling Configuration:**

```yaml
# HPA configuration in values-prod.yaml
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80
  
  # Custom metrics (optional)
  metrics:
    - type: Pods
      pods:
        metric:
          name: reasoning_queue_depth
        target:
          type: AverageValue
          averageValue: "100"
```

**Monitor Autoscaling:**

```bash
# Check HPA status
kubectl get hpa -n agent-guru-prod

# Watch HPA events
kubectl describe hpa reasoning-engine-hpa -n agent-guru-prod
```

### Vertical Scaling (Increase Resources)

**Increase CPU/Memory:**

```bash
# Update resource limits
kubectl set resources deployment/reasoning-engine \
  --requests=cpu=2000m,memory=4Gi \
  --limits=cpu=4000m,memory=8Gi \
  -n agent-guru-prod

# Or update Helm values and redeploy
```

**When to Vertical Scale:**
- Consistent high CPU/memory usage
- Pods hitting resource limits
- Performance degradation under load

### Database Scaling

**Vertical Scaling (AWS RDS example):**

```bash
# Modify instance class
aws rds modify-db-instance \
  --db-instance-identifier agent-guru-prod-db \
  --db-instance-class db.r5.2xlarge \
  --apply-immediately

# Monitor modification
aws rds describe-db-instances \
  --db-instance-identifier agent-guru-prod-db \
  --query 'DBInstances[0].DBInstanceStatus'
```

**Read Replicas:**

```bash
# Create read replica
aws rds create-db-instance-read-replica \
  --db-instance-identifier agent-guru-prod-db-replica \
  --source-db-instance-identifier agent-guru-prod-db

# Update application to use read replica for queries
```

### Redis Scaling

**Vertical Scaling (AWS ElastiCache example):**

```bash
# Modify cache cluster
aws elasticache modify-cache-cluster \
  --cache-cluster-id agent-guru-prod-redis \
  --cache-node-type cache.r5.xlarge \
  --apply-immediately
```

**Add Shards (Cluster Mode):**

```bash
# Increase shard count
aws elasticache modify-replication-group \
  --replication-group-id agent-guru-prod-redis \
  --node-group-count 3 \
  --apply-immediately
```

## Maintenance Windows

### Scheduled Maintenance

**Frequency:** Monthly (first Sunday, 2:00 AM - 4:00 AM UTC)

**Pre-Maintenance Checklist:**

- [ ] Notify users 7 days in advance
- [ ] Update status page with maintenance window
- [ ] Backup database
- [ ] Test rollback procedures
- [ ] Prepare runbook for maintenance tasks

**Maintenance Tasks:**

1. Database maintenance (vacuum, reindex)
2. Security patches
3. Dependency updates
4. Infrastructure updates
5. Performance optimizations

**Post-Maintenance Checklist:**

- [ ] Verify all services healthy
- [ ] Run smoke tests
- [ ] Check monitoring dashboards
- [ ] Update status page (maintenance complete)
- [ ] Document any issues encountered

### Emergency Maintenance

**Trigger Conditions:**

- Critical security vulnerability
- Data corruption
- Infrastructure failure

**Procedure:**

1. Assess urgency and impact
2. Notify stakeholders immediately
3. Update status page
4. Execute maintenance with minimal downtime
5. Verify resolution
6. Post incident report

## Emergency Contacts

### On-Call Rotation

- **Primary On-Call:** Check PagerDuty schedule
- **Secondary On-Call:** Check PagerDuty schedule
- **Escalation:** Engineering Manager

### Contact Methods

- **PagerDuty:** https://agent-guru.pagerduty.com
- **Slack:** #incidents channel
- **Email:** oncall@agent-guru.com
- **Phone:** +1-555-ONCALL (emergency only)

### Escalation Path

1. **Level 1:** On-call engineer (responds within 15 minutes)
2. **Level 2:** Senior engineer (responds within 30 minutes)
3. **Level 3:** Engineering manager (responds within 1 hour)
4. **Level 4:** CTO (responds within 2 hours)

### External Vendors

- **AWS Support:** Enterprise support, 24/7
- **OpenAI Support:** support@openai.com
- **Database Vendor:** Check support portal

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Latency**
   - P50, P95, P99 response time
   - Target: P95 <1.5s

2. **Error Rate**
   - Percentage of failed requests
   - Target: <1%

3. **Throughput**
   - Requests per second
   - Target: Handle 100 RPS sustained

4. **Resource Utilization**
   - CPU, memory, disk, network
   - Target: <80% average

5. **External Dependencies**
   - Database query time
   - Redis latency
   - LLM API latency

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| P95 Latency | >2s | >3s |
| Error Rate | >2% | >5% |
| CPU Usage | >80% | >90% |
| Memory Usage | >80% | >90% |
| Disk Usage | >80% | >90% |
| Pod Restarts | >5/hour | >10/hour |

### Dashboards

- **Executive Dashboard:** High-level KPIs
- **Operations Dashboard:** Detailed metrics
- **Capacity Planning:** Resource trends
- **Business Metrics:** Usage patterns

Access: https://grafana.agent-guru.com

## References

- [Deployment Guide](./DEPLOYMENT_GUIDE.md)
- [API Documentation](./API_DOCUMENTATION.md)
- [Architecture Overview](../design.md)
- [Incident Response Playbook](https://wiki.agent-guru.com/incident-response)
- [PagerDuty Runbook](https://agent-guru.pagerduty.com/runbooks)
