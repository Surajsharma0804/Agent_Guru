# Runbook: High P95 Latency

## Alert Name: HighP95Latency

### Severity: P1 (Critical)

### Description
P95 latency has exceeded 3.0 seconds (2x target of 1.5s), indicating significant performance degradation affecting user experience.

### Impact
- **User Impact**: Users experience slow responses, poor user experience, potential timeouts
- **Business Impact**: Reduced user satisfaction, potential churn, negative reviews
- **Scope**: Affects 5% of all requests (P95 threshold)

### Symptoms
- Slow response times in user interface
- Increased timeout errors
- User complaints about performance
- Queue depth increasing
- CPU/memory usage may be elevated

### Possible Causes
1. **LLM Backend Slow** (Most Common)
   - Cloud LLM API slow or rate-limited
   - Local LLM overloaded
   - Network latency to LLM backend

2. **Database Slow**
   - Slow queries
   - Connection pool exhausted
   - Database overloaded

3. **Resource Exhaustion**
   - High CPU usage
   - Memory pressure
   - Disk I/O bottleneck

4. **External Dependencies**
   - Tool execution slow
   - External API slow
   - Network issues

5. **Code Issues**
   - Recent deployment with performance regression
   - Memory leak
   - Inefficient algorithm

---

## Investigation Steps

### Step 1: Verify the Alert
```bash
# Check current P95 latency
curl -s 'http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(reasoning_engine_latency_seconds_bucket[5m]))by(le))' | jq '.data.result[0].value[1]'

# Check if alert is still firing
curl -s http://prometheus:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.alertname=="HighP95Latency")'
```

**Expected Result**: Latency > 3.0s

**If Different**: Alert may have auto-resolved, verify in Grafana

### Step 2: Check Component Latency
```bash
# Check latency by pipeline stage
curl -s 'http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(reasoning_engine_intent_detection_duration_seconds_bucket[5m]))by(le))' | jq

curl -s 'http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(reasoning_engine_reasoning_duration_seconds_bucket[5m]))by(le))' | jq

curl -s 'http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(reasoning_engine_execution_duration_seconds_bucket[5m]))by(le))' | jq
```

**Expected Result**: Identify which component is slow

**If Different**: Multiple components slow indicates systemic issue

### Step 3: Check System Resources
```bash
# Check CPU usage
kubectl top pods -n reasoning-engine

# Check memory usage
kubectl top pods -n reasoning-engine

# Check pod status
kubectl get pods -n reasoning-engine

# Check recent restarts
kubectl get pods -n reasoning-engine -o json | jq '.items[] | {name: .metadata.name, restarts: .status.containerStatuses[0].restartCount}'
```

**Expected Result**: CPU < 80%, Memory < 80%, No recent restarts

**If Different**: Resource exhaustion likely cause

### Step 4: Check LLM Backend
```bash
# Check LLM availability
curl -s 'http://prometheus:9090/api/v1/query?query=reasoning_engine_llm_available' | jq

# Check LLM latency
curl -s 'http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,rate(reasoning_engine_llm_latency_seconds_bucket[5m]))' | jq

# Check LLM error rate
curl -s 'http://prometheus:9090/api/v1/query?query=sum(rate(reasoning_engine_llm_errors_total[5m]))/sum(rate(reasoning_engine_llm_requests_total[5m]))' | jq
```

**Expected Result**: LLM available, latency < 400ms, error rate < 5%

**If Different**: LLM backend is the bottleneck

### Step 5: Check Database
```bash
# Check database connection pool
kubectl logs -n reasoning-engine deployment/reasoning-engine --tail=100 | grep "database"

# Check slow queries
kubectl exec -n reasoning-engine deployment/reasoning-engine -- psql -U postgres -c "SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# Check database connections
kubectl exec -n reasoning-engine deployment/reasoning-engine -- psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
```

**Expected Result**: Connection pool healthy, no slow queries, connections < max

**If Different**: Database is the bottleneck

### Step 6: Check Recent Deployments
```bash
# Check recent deployments
kubectl rollout history deployment/reasoning-engine -n reasoning-engine

# Check deployment time
kubectl get deployment reasoning-engine -n reasoning-engine -o json | jq '.metadata.creationTimestamp'

# Check recent changes
git log --since="2 hours ago" --oneline
```

**Expected Result**: No recent deployments or changes

**If Different**: Recent deployment may have introduced regression

---

## Resolution Steps

### Quick Fix 1: Scale Up (If Resource Exhaustion)
```bash
# Scale up replicas
kubectl scale deployment reasoning-engine -n reasoning-engine --replicas=10

# Verify scaling
kubectl get pods -n reasoning-engine

# Monitor latency
watch -n 5 'curl -s "http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(reasoning_engine_latency_seconds_bucket[5m]))by(le))" | jq ".data.result[0].value[1]"'
```

**Expected Outcome**: Latency decreases within 5 minutes

**Verification**:
```bash
# Check P95 latency
curl -s 'http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(reasoning_engine_latency_seconds_bucket[5m]))by(le))' | jq '.data.result[0].value[1]'
```

### Quick Fix 2: Restart Pods (If Memory Leak)
```bash
# Rolling restart
kubectl rollout restart deployment/reasoning-engine -n reasoning-engine

# Monitor restart
kubectl rollout status deployment/reasoning-engine -n reasoning-engine

# Verify latency
watch -n 5 'curl -s "http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(reasoning_engine_latency_seconds_bucket[5m]))by(le))" | jq ".data.result[0].value[1]"'
```

**Expected Outcome**: Latency decreases after restart

**Verification**:
```bash
# Check memory usage after restart
kubectl top pods -n reasoning-engine
```

### Quick Fix 3: Rollback Deployment (If Recent Change)
```bash
# Rollback to previous version
kubectl rollout undo deployment/reasoning-engine -n reasoning-engine

# Monitor rollback
kubectl rollout status deployment/reasoning-engine -n reasoning-engine

# Verify latency
watch -n 5 'curl -s "http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(reasoning_engine_latency_seconds_bucket[5m]))by(le))" | jq ".data.result[0].value[1]"'
```

**Expected Outcome**: Latency returns to normal

**Verification**:
```bash
# Check deployment version
kubectl get deployment reasoning-engine -n reasoning-engine -o json | jq '.spec.template.spec.containers[0].image'
```

### Quick Fix 4: Enable Degraded Mode (If LLM Slow)
```bash
# Force degraded mode (rule-based fallback)
kubectl set env deployment/reasoning-engine -n reasoning-engine FORCE_DEGRADED_MODE=true

# Monitor degraded mode rate
watch -n 5 'curl -s "http://prometheus:9090/api/v1/query?query=sum(rate(reasoning_engine_degraded_mode_total[5m]))/sum(rate(reasoning_engine_requests_total[5m]))" | jq ".data.result[0].value[1]"'
```

**Expected Outcome**: Latency decreases, degraded mode rate increases

**Verification**:
```bash
# Check latency and degraded mode
curl -s 'http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(reasoning_engine_latency_seconds_bucket[5m]))by(le))' | jq
curl -s 'http://prometheus:9090/api/v1/query?query=sum(rate(reasoning_engine_degraded_mode_total[5m]))/sum(rate(reasoning_engine_requests_total[5m]))' | jq
```

### Permanent Fix
Based on root cause:

**If LLM Backend Slow**:
1. Scale LLM infrastructure
2. Optimize LLM prompts
3. Implement better caching
4. Use faster LLM model

**If Database Slow**:
1. Optimize slow queries
2. Add database indexes
3. Scale database
4. Implement query caching

**If Resource Exhaustion**:
1. Increase resource limits
2. Optimize code for efficiency
3. Fix memory leaks
4. Implement auto-scaling

**If Code Issue**:
1. Profile code to find bottleneck
2. Optimize hot paths
3. Fix algorithmic issues
4. Add performance tests to CI/CD

---

## Escalation

### When to Escalate
- Latency not improving after 30 minutes
- Multiple quick fixes attempted without success
- Root cause unclear
- Requires architectural changes

### Escalation Path
1. **Level 1**: Secondary On-Call Engineer (if not resolved in 30 min)
2. **Level 2**: Engineering Manager (if not resolved in 1 hour)
3. **Level 3**: VP Engineering (if major outage)

### Escalation Contact
- **Secondary On-Call**: Check PagerDuty schedule
- **Engineering Manager**: manager@agent-guru.com
- **VP Engineering**: vp-eng@agent-guru.com

---

## Communication

### Internal Communication
- **Slack Channel**: #incidents
- **Update Frequency**: Every 15 minutes
- **Template**:
  ```
  [Timestamp] - High Latency Incident Update
  - Current P95 Latency: [X]s (target: 1.5s)
  - Root Cause: [Identified/Under Investigation]
  - Impact: [X]% of requests affected
  - ETA: [X] minutes
  - Next Steps: [Actions being taken]
  ```

### External Communication
- **Status Page**: https://status.agent-guru.com
- **Customer Email**: If latency > 5s for > 30 minutes
- **Template**: "We are experiencing elevated response times. Our team is actively working on a resolution. ETA: [X] minutes."

---

## Prevention

### Short-Term Prevention
- Increase monitoring sensitivity
- Add latency regression tests
- Implement auto-scaling based on latency
- Set up canary deployments

### Long-Term Prevention
- Optimize critical path performance
- Implement comprehensive caching
- Add performance budgets to CI/CD
- Regular performance testing
- Capacity planning reviews

### Monitoring Improvements
- Add per-component latency alerts
- Add latency trend alerts
- Add predictive latency alerts
- Improve latency dashboards

---

## Related Information

### Related Alerts
- HighP99Latency
- HighQueueDepth
- HighCPUUsage
- HighMemoryUsage

### Related Runbooks
- [High Error Rate](./high-error-rate.md)
- [Service Down](./service-down.md)
- [LLM Unavailable](./llm-unavailable.md)

### Documentation
- [Architecture Overview](../../docs/architecture.md)
- [Performance Optimization Guide](../../docs/performance.md)
- [Deployment Guide](../../docs/deployment.md)

### Recent Incidents
- [INC-2024-001] - High latency due to LLM rate limiting - 2024-01-15
- [INC-2024-005] - High latency due to database slow query - 2024-02-03

---

## Postmortem

### Required for P1
- [x] Incident timeline documented
- [x] Root cause identified
- [x] Impact assessed
- [x] Action items created
- [x] Postmortem reviewed with team

### Postmortem Template
[Link to postmortem template](../postmortem-template.md)

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2024-01-01 | SRE Team | Initial version |
| 2024-02-15 | Engineer 1 | Added LLM backend checks |
| 2024-03-01 | Engineer 2 | Added degraded mode quick fix |
