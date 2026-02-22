# Runbook Template

## Alert Name: [Alert Name]

### Severity: [P1/P2/P3/P4]

### Description
[Brief description of what this alert means]

### Impact
- **User Impact**: [How does this affect users?]
- **Business Impact**: [How does this affect the business?]
- **Scope**: [How many users/requests affected?]

### Symptoms
- [Observable symptom 1]
- [Observable symptom 2]
- [Observable symptom 3]

### Possible Causes
1. [Most common cause]
2. [Second most common cause]
3. [Other possible causes]

---

## Investigation Steps

### Step 1: Verify the Alert
```bash
# Check if alert is still firing
curl http://prometheus:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.alertname=="[AlertName]")'

# Check current metric value
# [Prometheus query]
```

**Expected Result**: [What you should see]

**If Different**: [What to do if result is unexpected]

### Step 2: Check System Health
```bash
# Check service status
kubectl get pods -n reasoning-engine

# Check recent logs
kubectl logs -n reasoning-engine deployment/reasoning-engine --tail=100

# Check metrics
# [Grafana dashboard link]
```

**Expected Result**: [What you should see]

**If Different**: [What to do if result is unexpected]

### Step 3: Identify Root Cause
```bash
# [Commands to identify root cause]
```

**Common Root Causes**:
1. [Root cause 1] - [How to identify]
2. [Root cause 2] - [How to identify]
3. [Root cause 3] - [How to identify]

---

## Resolution Steps

### Quick Fix (Immediate Mitigation)
```bash
# [Commands for quick fix]
```

**Expected Outcome**: [What should happen]

**Verification**:
```bash
# [Commands to verify fix]
```

### Permanent Fix
```bash
# [Commands for permanent fix]
```

**Expected Outcome**: [What should happen]

**Verification**:
```bash
# [Commands to verify fix]
```

---

## Escalation

### When to Escalate
- [Condition 1]
- [Condition 2]
- [Condition 3]

### Escalation Path
1. **Level 1**: Secondary On-Call Engineer
2. **Level 2**: Engineering Manager
3. **Level 3**: VP Engineering

### Escalation Contact
- **Secondary On-Call**: [Contact info]
- **Engineering Manager**: [Contact info]
- **VP Engineering**: [Contact info]

---

## Communication

### Internal Communication
- **Slack Channel**: #incidents
- **Update Frequency**: Every 15 minutes for P1, every 30 minutes for P2
- **Template**:
  ```
  [Timestamp] - [Status Update]
  - Current Status: [Status]
  - Impact: [Impact]
  - ETA: [ETA]
  - Next Steps: [Next Steps]
  ```

### External Communication
- **Status Page**: [URL]
- **Customer Email**: [When to send]
- **Template**: [Link to template]

---

## Prevention

### Short-Term Prevention
- [Action 1]
- [Action 2]

### Long-Term Prevention
- [Action 1]
- [Action 2]

### Monitoring Improvements
- [Improvement 1]
- [Improvement 2]

---

## Related Information

### Related Alerts
- [Related Alert 1]
- [Related Alert 2]

### Related Runbooks
- [Related Runbook 1]
- [Related Runbook 2]

### Documentation
- [Architecture Doc]
- [API Doc]
- [Deployment Doc]

### Recent Incidents
- [Incident 1] - [Date] - [Link]
- [Incident 2] - [Date] - [Link]

---

## Postmortem

### Required for P1/P2
- [ ] Incident timeline documented
- [ ] Root cause identified
- [ ] Impact assessed
- [ ] Action items created
- [ ] Postmortem reviewed with team

### Postmortem Template
[Link to postmortem template]

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| YYYY-MM-DD | [Name] | Initial version |
| YYYY-MM-DD | [Name] | [Changes] |
