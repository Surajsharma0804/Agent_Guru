# Incident Response - Agent Guru Reasoning Engine

## Overview

This directory contains all documentation and procedures for incident response, on-call management, and service reliability for the Agent Guru Reasoning Engine.

## Directory Structure

```
incident-response/
├── README.md                    # This file
├── on-call-rotation.md          # On-call schedule and procedures
├── slo-definitions.md           # Service Level Objectives
├── postmortem-template.md       # Template for incident postmortems
├── runbooks/                    # Operational runbooks
│   ├── runbook-template.md      # Template for creating new runbooks
│   ├── high-latency.md          # Runbook for high latency incidents
│   ├── high-error-rate.md       # Runbook for high error rate
│   ├── service-down.md          # Runbook for service outages
│   ├── llm-unavailable.md       # Runbook for LLM backend issues
│   ├── database-issues.md       # Runbook for database problems
│   └── security-incidents.md    # Runbook for security events
└── postmortems/                 # Historical incident postmortems
    └── YYYY-MM-DD-incident-name.md
```

## Quick Start

### For New On-Call Engineers

1. **Read Documentation**
   - [On-Call Rotation](./on-call-rotation.md)
   - [SLO Definitions](./slo-definitions.md)
   - All runbooks in [runbooks/](./runbooks/)

2. **Get Access**
   - PagerDuty account
   - Slack workspace
   - AWS Console (production)
   - Kubernetes cluster
   - Grafana/Prometheus
   - Elasticsearch/Kibana

3. **Test Tools**
   - Verify PagerDuty notifications
   - Test VPN access
   - Verify kubectl access
   - Test AWS CLI

4. **Shadow Current On-Call**
   - Observe for 1-2 weeks
   - Practice incident response
   - Ask questions

### For Responding to Incidents

1. **Acknowledge Alert** (within SLA)
   - P1: 15 minutes
   - P2: 30 minutes
   - P3: 2 hours

2. **Assess Severity**
   - Check impact and scope
   - Determine priority
   - Create incident ticket if P1/P2

3. **Follow Runbook**
   - Find relevant runbook
   - Follow investigation steps
   - Implement resolution

4. **Communicate**
   - Update #incidents channel
   - Update status page if needed
   - Notify stakeholders

5. **Document**
   - Update incident ticket
   - Write postmortem for P1/P2
   - Update runbooks with learnings

## Service Level Objectives (SLOs)

### Core SLOs

| Metric | Target | Error Budget |
|--------|--------|--------------|
| Availability | 99.9% | 43.8 min/month |
| P95 Latency | < 1.5s | 5% of requests |
| Error Rate | < 1% | 1% of requests |
| Degraded Mode | < 5% | 5% of requests |

See [SLO Definitions](./slo-definitions.md) for complete details.

## Alert Severity Levels

### P1 - Critical (15 min response)
- Service completely down
- Major functionality broken
- Critical security breach
- Data loss or corruption

### P2 - High (30 min response)
- Significant degradation
- High error rate (>5%)
- P95 latency >2x target
- LLM backend unavailable

### P3 - Medium (2 hour response)
- Minor degradation
- Elevated error rate (2-5%)
- Single instance issues
- Non-critical component failures

### P4 - Low (Next business day)
- Informational alerts
- Warning alerts
- Capacity planning alerts
- Non-urgent improvements

## Common Incidents

### High Latency
**Symptoms**: Slow responses, timeouts, queue buildup  
**Runbook**: [high-latency.md](./runbooks/high-latency.md)  
**Quick Fix**: Scale up, restart pods, enable degraded mode

### High Error Rate
**Symptoms**: Increased failures, user complaints  
**Runbook**: [high-error-rate.md](./runbooks/high-error-rate.md)  
**Quick Fix**: Rollback deployment, check dependencies

### Service Down
**Symptoms**: No responses, all instances down  
**Runbook**: [service-down.md](./runbooks/service-down.md)  
**Quick Fix**: Restart service, check infrastructure

### LLM Unavailable
**Symptoms**: Degraded mode, LLM errors  
**Runbook**: [llm-unavailable.md](./runbooks/llm-unavailable.md)  
**Quick Fix**: Switch to backup LLM, enable rule-based fallback

### Database Issues
**Symptoms**: Connection errors, slow queries  
**Runbook**: [database-issues.md](./runbooks/database-issues.md)  
**Quick Fix**: Restart connections, kill slow queries

## Escalation Path

```
Primary On-Call
    ↓ (30 min)
Secondary On-Call
    ↓ (1 hour)
Engineering Manager
    ↓ (Major outage)
VP Engineering / CTO
```

## Communication Channels

### Internal
- **#incidents**: Incident coordination
- **#alerts-critical**: Critical alerts
- **#alerts-warnings**: Warning alerts
- **#on-call**: On-call handoffs

### External
- **Status Page**: https://status.agent-guru.com
- **Customer Email**: For major incidents
- **Social Media**: For widespread outages

## Tools and Dashboards

### Monitoring
- **Prometheus**: http://prometheus:9090
- **Grafana**: http://grafana:3000
- **Alertmanager**: http://alertmanager:9093

### Logging
- **Kibana**: http://kibana:5601
- **CloudWatch**: AWS Console

### Incident Management
- **PagerDuty**: https://agent-guru.pagerduty.com
- **Jira**: https://agent-guru.atlassian.net

### Key Dashboards
- [Executive Dashboard](http://grafana:3000/d/executive)
- [Operational Dashboard](http://grafana:3000/d/operational)
- [SLO Dashboard](http://grafana:3000/d/slo)

## Runbook Index

### Infrastructure
- [Service Down](./runbooks/service-down.md)
- [High CPU Usage](./runbooks/high-cpu.md)
- [High Memory Usage](./runbooks/high-memory.md)
- [Disk Space Issues](./runbooks/disk-space.md)

### Performance
- [High Latency](./runbooks/high-latency.md)
- [High Queue Depth](./runbooks/high-queue-depth.md)
- [Timeout Issues](./runbooks/timeout-issues.md)

### Reliability
- [High Error Rate](./runbooks/high-error-rate.md)
- [Degraded Mode](./runbooks/degraded-mode.md)
- [Service Flapping](./runbooks/service-flapping.md)

### Dependencies
- [LLM Unavailable](./runbooks/llm-unavailable.md)
- [Database Issues](./runbooks/database-issues.md)
- [Redis Issues](./runbooks/redis-issues.md)

### Security
- [Security Incidents](./runbooks/security-incidents.md)
- [Unauthorized Access](./runbooks/unauthorized-access.md)
- [Data Breach](./runbooks/data-breach.md)

## Postmortem Process

### When Required
- All P1 incidents
- All P2 incidents
- P3 incidents with interesting learnings

### Timeline
- **Draft**: Within 24 hours
- **Review**: Within 48 hours
- **Final**: Within 72 hours
- **Follow-up**: Weekly until action items complete

### Template
Use [postmortem-template.md](./postmortem-template.md)

### Best Practices
1. Be blameless
2. Be honest
3. Be specific
4. Be actionable
5. Be timely

## On-Call Compensation

- **Weekday On-Call**: $X per day
- **Weekend On-Call**: $Y per day
- **Holiday On-Call**: $Z per day
- **Incident Response**: Time-and-a-half for after-hours

## Training Resources

### Required Reading
- [On-Call Rotation](./on-call-rotation.md)
- [SLO Definitions](./slo-definitions.md)
- All runbooks
- [System Architecture](../docs/architecture.md)

### Recommended Reading
- [Google SRE Book](https://sre.google/sre-book/table-of-contents/)
- [Site Reliability Engineering](https://landing.google.com/sre/)
- [The Phoenix Project](https://itrevolution.com/the-phoenix-project/)

### Training Exercises
- Shadow current on-call (1-2 weeks)
- Practice incident response (simulations)
- Review past incidents
- Update runbooks

## Continuous Improvement

### Weekly
- Review all incidents
- Update runbooks
- Share learnings

### Monthly
- Review SLO compliance
- Analyze trends
- Identify improvements

### Quarterly
- Review SLO targets
- Update procedures
- Train new engineers

## Contact Information

### On-Call
- **Primary**: Check PagerDuty schedule
- **Secondary**: Check PagerDuty schedule

### Management
- **Engineering Manager**: manager@agent-guru.com
- **VP Engineering**: vp-eng@agent-guru.com
- **CTO**: cto@agent-guru.com

### External Support
- **AWS Support**: 1-800-AWS-SUPPORT
- **PagerDuty Support**: support@pagerduty.com

## Contributing

### Adding New Runbooks
1. Copy [runbook-template.md](./runbooks/runbook-template.md)
2. Fill in all sections
3. Test procedures
4. Get review from team
5. Add to index

### Updating Existing Runbooks
1. Make changes
2. Test procedures
3. Update revision history
4. Get review from team
5. Communicate changes

### Writing Postmortems
1. Use [postmortem-template.md](./postmortem-template.md)
2. Complete within 72 hours
3. Review with team
4. Share learnings
5. Track action items

## References

- [Google SRE Book](https://sre.google/sre-book/)
- [Incident Response Guide](https://response.pagerduty.com/)
- [Postmortem Culture](https://sre.google/sre-book/postmortem-culture/)
- [On-Call Best Practices](https://increment.com/on-call/)

---

**Document Version**: 1.0  
**Last Updated**: 2024-01-01  
**Owner**: SRE Team  
**Contact**: sre@agent-guru.com
