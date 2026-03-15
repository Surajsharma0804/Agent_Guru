# Agent Guru Reasoning Engine - Operations Runbook

> For the full operations runbook including detailed incident response procedures, see [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md).

## Quick Reference

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| P95 Latency | <1.5s | >3s (critical) |
| Error Rate | <1% | >5% (critical) |
| CPU Usage | <70% | >90% (critical) |
| Memory Usage | <80% | >90% (critical) |
| Pod Restarts | 0/hour | >10/hour (critical) |

**Dashboards:** https://grafana.agent-guru.com  
**Alerts:** https://agent-guru.pagerduty.com  
**Status Page:** https://status.agent-guru.com

---

## Monitoring

### Check System Health

```bash
# Pod status
kubectl get pods -n agent-guru-prod

# Health endpoint
curl -f https://api.agent-guru.com/health

# Key metrics
curl -s https://api.agent-guru.com/metrics | grep -E \
  "(reasoning_requests_total|reasoning_latency_seconds|reasoning_errors_total)"
```

### View Logs

```bash
# Recent logs
kubectl logs -f deployment/reasoning-engine -n agent-guru-prod --tail=100

# Filter errors only
kubectl logs deployment/reasoning-engine -n agent-guru-prod | grep ERROR

# Specific pod
kubectl logs <pod-name> -n agent-guru-prod
```

### Resource Utilization

```bash
kubectl top pods -n agent-guru-prod
kubectl top nodes
kubectl get hpa -n agent-guru-prod
```

---

## Common Operational Tasks

### Restart Service (Graceful)

```bash
kubectl rollout restart deployment/reasoning-engine -n agent-guru-prod
kubectl rollout status deployment/reasoning-engine -n agent-guru-prod
```

### Scale Manually

```bash
# Scale up
kubectl scale deployment/reasoning-engine --replicas=10 -n agent-guru-prod

# Scale down
kubectl scale deployment/reasoning-engine --replicas=3 -n agent-guru-prod
```

### Rotate Secrets

```bash
# Update secret in secrets manager, then:
kubectl delete secret reasoning-engine-secrets -n agent-guru-prod
kubectl create secret generic reasoning-engine-secrets \
  --namespace=agent-guru-prod \
  --from-literal=database-url="<new-value>" \
  --from-literal=redis-url="<new-value>" \
  --from-literal=openai-api-key="<new-value>"

kubectl rollout restart deployment/reasoning-engine -n agent-guru-prod
```

### Clear Cache

```bash
# Connect to Redis and flush intent/tool caches
kubectl exec -it deployment/reasoning-engine -n agent-guru-prod -- \
  redis-cli -h <redis-host> --scan --pattern "intent:*" | xargs redis-cli DEL
```

### Update Configuration

```bash
# Edit values and apply
vim values-prod.yaml
helm upgrade reasoning-engine ./helm/reasoning-engine \
  --namespace=agent-guru-prod \
  --values=values-prod.yaml \
  --wait
```

---

## Alerting

### Alert: High Latency (P95 >3s)

**Diagnosis:**

```bash
# Check resource usage
kubectl top pods -n agent-guru-prod

# Check stage latencies in logs
kubectl logs deployment/reasoning-engine -n agent-guru-prod | grep "stage_latency"

# Check external dependencies
curl -s https://api.agent-guru.com/metrics | grep -E "(db_query|redis_latency|llm_latency)"
```

**Resolution:**
1. If CPU/memory high → scale up: `kubectl scale deployment/reasoning-engine --replicas=10 -n agent-guru-prod`
2. If LLM slow → switch to local: update `LLM_BACKEND=local` in config
3. If database slow → check slow query log, scale DB instance

---

### Alert: High Error Rate (>5%)

**Diagnosis:**

```bash
# Check error types
kubectl logs deployment/reasoning-engine -n agent-guru-prod | grep ERROR | \
  awk '{print $NF}' | sort | uniq -c | sort -rn | head -20
```

**Resolution:**
1. If database errors → check DB connectivity, restart pods
2. If LLM API errors → verify API keys, enable fallback
3. If validation errors → check for malformed client requests

---

### Alert: Pod CrashLoopBackOff

**Diagnosis:**

```bash
kubectl describe pod <pod-name> -n agent-guru-prod
kubectl logs <pod-name> -n agent-guru-prod --previous
```

**Resolution:**
1. Check for missing secrets: `kubectl get secrets -n agent-guru-prod`
2. Check for config errors in pod logs
3. If resource limits too low: `kubectl set resources deployment/reasoning-engine --limits=memory=8Gi -n agent-guru-prod`

---

### Alert: Memory Leak (Memory growing over time)

**Diagnosis:**

```bash
# Watch memory trend
watch kubectl top pods -n agent-guru-prod

# Check for OOMKilled events
kubectl get events -n agent-guru-prod | grep OOMKilled
```

**Immediate mitigation:**

```bash
# Restart pods to reclaim memory
kubectl rollout restart deployment/reasoning-engine -n agent-guru-prod

# Temporarily increase memory limit
kubectl set resources deployment/reasoning-engine --limits=memory=8Gi -n agent-guru-prod
```

---

## Incident Response

### Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| SEV1 | Complete outage, data loss | 15 minutes |
| SEV2 | Partial outage, major degradation | 30 minutes |
| SEV3 | Minor degradation, workaround available | 4 hours |
| SEV4 | Cosmetic issues, no user impact | Next sprint |

### SEV1 Response Steps

1. **Page on-call** (PagerDuty auto-pages on critical alerts)

2. **Assess impact:**
   ```bash
   kubectl get pods -n agent-guru-prod
   curl https://api.agent-guru.com/health
   ```

3. **Check recent changes:**
   ```bash
   helm history reasoning-engine -n agent-guru-prod
   ```

4. **Rollback if recent deployment caused issue:**
   ```bash
   helm rollback reasoning-engine -n agent-guru-prod
   ```

5. **Update status page:** https://status.agent-guru.com

6. **Communicate** in #incidents Slack channel every 30 minutes

7. **Post-incident review** within 48 hours

---

## Maintenance

### Scheduled Maintenance Window

- **When:** First Sunday of each month, 2:00–4:00 AM UTC
- **Notification:** 7 days advance notice to users

**Pre-maintenance checklist:**
- [ ] Notify users via status page
- [ ] Take database backup
- [ ] Test rollback procedure
- [ ] Prepare maintenance tasks list

**Post-maintenance checklist:**
- [ ] Verify all pods healthy
- [ ] Run smoke tests
- [ ] Update status page (maintenance complete)
- [ ] Document any issues

---

## Escalation Path

1. **On-call engineer** → PagerDuty (15 min SLA)
2. **Senior engineer** → Slack DM (30 min SLA)
3. **Engineering manager** → Phone (1 hour SLA)
4. **CTO** → Phone (2 hour SLA, SEV1 only)

**Contacts:**
- On-call: https://agent-guru.pagerduty.com
- Slack: #incidents
- Email: oncall@agent-guru.com

---

## Related Documentation

- [Full Operations Runbook](./OPERATIONS_RUNBOOK.md) - Detailed procedures
- [Deployment Guide](./deployment_guide.md) - Deployment procedures
- [API Reference](./api_reference.md) - API documentation
