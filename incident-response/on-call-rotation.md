# On-Call Rotation - Agent Guru Reasoning Engine

## Overview

This document defines the on-call rotation schedule, responsibilities, and escalation procedures for the Agent Guru Reasoning Engine production support team.

## On-Call Schedule

### Rotation Schedule
- **Primary On-Call**: 1 week rotation
- **Secondary On-Call**: 1 week rotation (backup)
- **Rotation Start**: Monday 9:00 AM local time
- **Rotation End**: Monday 9:00 AM local time (following week)

### Coverage Hours
- **Business Hours**: Monday-Friday, 9:00 AM - 5:00 PM local time
- **After Hours**: Evenings, weekends, and holidays
- **Response Time SLA**:
  - Critical (P1): 15 minutes
  - High (P2): 30 minutes
  - Medium (P3): 2 hours
  - Low (P4): Next business day

### Team Members

| Name | Role | Primary Contact | Secondary Contact | Time Zone |
|------|------|----------------|-------------------|-----------|
| Engineer 1 | Senior SRE | +1-555-0101 | engineer1@agent-guru.com | PST |
| Engineer 2 | SRE | +1-555-0102 | engineer2@agent-guru.com | EST |
| Engineer 3 | Backend Engineer | +1-555-0103 | engineer3@agent-guru.com | PST |
| Engineer 4 | ML Engineer | +1-555-0104 | engineer4@agent-guru.com | EST |

### Current Rotation

| Week | Primary On-Call | Secondary On-Call |
|------|----------------|-------------------|
| Week 1 | Engineer 1 | Engineer 2 |
| Week 2 | Engineer 2 | Engineer 3 |
| Week 3 | Engineer 3 | Engineer 4 |
| Week 4 | Engineer 4 | Engineer 1 |

## On-Call Responsibilities

### Primary On-Call Engineer

1. **Alert Response**
   - Acknowledge all alerts within SLA timeframe
   - Investigate and diagnose issues
   - Implement fixes or workarounds
   - Escalate to secondary if needed

2. **Incident Management**
   - Create incident tickets for all P1/P2 issues
   - Update incident status regularly
   - Communicate with stakeholders
   - Document resolution steps

3. **Monitoring**
   - Review dashboards at start of shift
   - Monitor alert channels (PagerDuty, Slack)
   - Check system health metrics
   - Review recent deployments

4. **Documentation**
   - Update runbooks with new findings
   - Document all incidents in postmortem
   - Share learnings with team
   - Update on-call handoff notes

### Secondary On-Call Engineer

1. **Backup Support**
   - Be available to assist primary
   - Take over if primary is unavailable
   - Provide second opinion on complex issues

2. **Escalation Point**
   - Receive escalations from primary
   - Coordinate with other teams if needed
   - Engage management for critical issues

## Escalation Procedures

### Level 1: Primary On-Call
- Initial alert response
- Basic troubleshooting
- Implementation of known fixes
- **Escalate if**: Issue not resolved in 30 minutes

### Level 2: Secondary On-Call
- Complex troubleshooting
- Cross-team coordination
- Architecture decisions
- **Escalate if**: Issue not resolved in 1 hour

### Level 3: Engineering Manager
- Resource allocation
- External communication
- Business decisions
- **Escalate if**: Major outage or data loss

### Level 4: VP Engineering / CTO
- Executive decisions
- Customer communication
- PR/legal involvement
- **Escalate if**: Company-wide impact

## Alert Severity Levels

### P1 - Critical (15 min response)
- **Definition**: Service completely down or major functionality broken
- **Examples**:
  - All instances down
  - Database unavailable
  - Critical security breach
  - Data loss or corruption
- **Actions**:
  - Immediate response required
  - Create incident ticket
  - Notify stakeholders
  - Engage secondary on-call if needed

### P2 - High (30 min response)
- **Definition**: Significant degradation affecting multiple users
- **Examples**:
  - High error rate (>5%)
  - P95 latency >2x target
  - LLM backend unavailable
  - Partial service degradation
- **Actions**:
  - Prompt response required
  - Create incident ticket
  - Monitor closely
  - Prepare for escalation

### P3 - Medium (2 hour response)
- **Definition**: Minor degradation or isolated issues
- **Examples**:
  - Elevated error rate (2-5%)
  - Single instance issues
  - Non-critical component failures
  - Performance degradation
- **Actions**:
  - Investigate during business hours
  - Document findings
  - Schedule fix if needed

### P4 - Low (Next business day)
- **Definition**: Informational or minor issues
- **Examples**:
  - Warning alerts
  - Capacity planning alerts
  - Non-urgent improvements
- **Actions**:
  - Review during business hours
  - Add to backlog if needed
  - No immediate action required

## Communication Channels

### Alert Channels
- **PagerDuty**: Primary alerting system
- **Slack #alerts-critical**: Critical alerts
- **Slack #alerts-warnings**: Warning alerts
- **Email**: Backup notification

### Incident Communication
- **Slack #incidents**: Incident coordination
- **Slack #engineering**: Team updates
- **Status Page**: Customer communication
- **Email**: Stakeholder updates

### Handoff Communication
- **Slack #on-call**: Shift handoffs
- **Confluence**: Handoff notes
- **PagerDuty**: Shift schedule

## Handoff Procedures

### Start of Shift
1. Review handoff notes from previous on-call
2. Check current system status
3. Review recent incidents and resolutions
4. Check upcoming deployments or maintenance
5. Acknowledge on-call status in Slack

### During Shift
1. Document all incidents and resolutions
2. Update handoff notes with ongoing issues
3. Communicate with team about significant events
4. Keep runbooks updated

### End of Shift
1. Complete handoff notes
2. Brief next on-call engineer
3. Transfer any ongoing incidents
4. Update PagerDuty schedule if needed
5. Post handoff summary in Slack

### Handoff Template
```
## On-Call Handoff - [Date]

### Incidents
- [List any incidents that occurred]
- [Include ticket numbers and status]

### Ongoing Issues
- [List any unresolved issues]
- [Include investigation status]

### System Status
- [Overall health: Green/Yellow/Red]
- [Any degraded components]

### Upcoming Events
- [Scheduled maintenance]
- [Planned deployments]

### Notes
- [Any other relevant information]
```

## Tools and Access

### Required Access
- PagerDuty account with on-call schedule
- Slack workspace access
- AWS Console access (production)
- Kubernetes cluster access
- Grafana/Prometheus access
- Elasticsearch/Kibana access
- GitHub repository access
- Incident management system access

### Required Tools
- Laptop with VPN access
- Mobile phone for PagerDuty
- Slack mobile app
- SSH keys for production access
- AWS CLI configured
- kubectl configured

## On-Call Best Practices

### Before Your Shift
1. Ensure all tools and access are working
2. Review recent incidents and resolutions
3. Check for scheduled maintenance
4. Familiarize yourself with recent changes
5. Test PagerDuty notifications

### During Your Shift
1. Respond to alerts promptly
2. Document everything
3. Communicate proactively
4. Don't hesitate to escalate
5. Take breaks when possible
6. Ask for help when needed

### After Your Shift
1. Complete handoff documentation
2. Update runbooks with learnings
3. File improvement tickets
4. Provide feedback on process
5. Rest and recover

## Incident Response Workflow

```
Alert Received
    ↓
Acknowledge (within SLA)
    ↓
Assess Severity
    ↓
Create Incident Ticket (P1/P2)
    ↓
Investigate & Diagnose
    ↓
Implement Fix/Workaround
    ↓
Verify Resolution
    ↓
Update Stakeholders
    ↓
Close Incident
    ↓
Write Postmortem (P1/P2)
    ↓
Implement Preventive Measures
```

## Compensation and Time Off

### On-Call Compensation
- **Weekday On-Call**: $X per day
- **Weekend On-Call**: $Y per day
- **Holiday On-Call**: $Z per day
- **Incident Response**: Time-and-a-half for after-hours work

### Time Off During On-Call
- Notify team at least 2 weeks in advance
- Find coverage or swap with another engineer
- Update PagerDuty schedule
- Document in team calendar

### Emergency Time Off
- Notify manager immediately
- Secondary on-call takes over
- Update PagerDuty schedule
- Follow up with team when possible

## Training and Onboarding

### New On-Call Engineers

1. **Week 1-2: Shadow**
   - Shadow current on-call engineer
   - Review all runbooks
   - Practice incident response
   - Get all required access

2. **Week 3-4: Reverse Shadow**
   - Take primary role with backup
   - Handle alerts with guidance
   - Document learnings
   - Ask questions

3. **Week 5+: Independent**
   - Take on-call shifts independently
   - Continue learning and improving
   - Mentor new engineers

### Required Training
- Incident response procedures
- System architecture overview
- Runbook familiarization
- Tool training (PagerDuty, Grafana, etc.)
- Communication protocols
- Escalation procedures

## Continuous Improvement

### Weekly Review
- Review all incidents from past week
- Identify patterns and trends
- Update runbooks as needed
- Share learnings with team

### Monthly Metrics
- Alert volume and trends
- Response time compliance
- Incident resolution time
- False positive rate
- On-call engineer feedback

### Quarterly Goals
- Reduce alert noise by X%
- Improve response time by Y%
- Increase automation coverage
- Update all runbooks
- Train new on-call engineers

## Contact Information

### Emergency Contacts
- **Engineering Manager**: +1-555-0200
- **VP Engineering**: +1-555-0300
- **CTO**: +1-555-0400
- **Security Team**: security@agent-guru.com
- **Infrastructure Team**: infra@agent-guru.com

### External Vendors
- **AWS Support**: 1-800-AWS-SUPPORT
- **PagerDuty Support**: support@pagerduty.com
- **Slack Support**: support@slack.com

## References

- [Runbooks](./runbooks/)
- [SLO Definitions](./slo-definitions.md)
- [Incident Postmortems](./postmortems/)
- [System Architecture](../docs/architecture.md)
