# Incident Postmortem Template

## Incident Information

| Field | Value |
|-------|-------|
| **Incident ID** | INC-YYYY-XXX |
| **Date** | YYYY-MM-DD |
| **Severity** | P1/P2/P3/P4 |
| **Duration** | X hours Y minutes |
| **Detected By** | [Alert/User/Monitoring/etc.] |
| **Incident Commander** | [Name] |
| **Responders** | [Names] |
| **Status Page** | [Link if published] |

---

## Executive Summary

[2-3 sentence summary of what happened, impact, and resolution]

Example:
> On January 15, 2024, the reasoning engine experienced elevated P95 latency (>5s) for 2 hours, affecting approximately 10,000 users. The root cause was LLM API rate limiting due to unexpected traffic spike. The issue was resolved by scaling LLM infrastructure and implementing better rate limiting.

---

## Impact

### User Impact
- **Users Affected**: [Number or percentage]
- **Duration**: [How long users were affected]
- **Severity**: [How severely were users affected]
- **User-Facing Symptoms**: [What users experienced]

### Business Impact
- **Revenue Impact**: [$X lost or N/A]
- **SLA Impact**: [SLA breached? By how much?]
- **Reputation Impact**: [Customer complaints, social media, etc.]
- **Operational Impact**: [Team time spent, other systems affected]

### Technical Impact
- **Services Affected**: [List of services]
- **Data Loss**: [Any data lost? How much?]
- **Performance Degradation**: [Metrics]

---

## Timeline

All times in [Timezone]

| Time | Event | Action Taken | By Whom |
|------|-------|--------------|---------|
| HH:MM | [Event description] | [Action taken] | [Person] |
| HH:MM | [Event description] | [Action taken] | [Person] |
| HH:MM | [Event description] | [Action taken] | [Person] |

Example:
| Time | Event | Action Taken | By Whom |
|------|-------|--------------|---------|
| 14:00 | Alert fired: HighP95Latency | Acknowledged alert | Engineer 1 |
| 14:05 | Verified latency spike in Grafana | Started investigation | Engineer 1 |
| 14:10 | Identified LLM rate limiting | Contacted LLM provider | Engineer 1 |
| 14:15 | Escalated to secondary on-call | Engaged Engineer 2 | Engineer 1 |
| 14:20 | Implemented degraded mode | Reduced latency to 2s | Engineer 2 |
| 14:30 | Scaled LLM infrastructure | Latency returned to normal | Engineer 2 |
| 14:45 | Verified resolution | Closed incident | Engineer 1 |
| 16:00 | Published postmortem | Shared with team | Engineer 1 |

---

## Root Cause Analysis

### What Happened?
[Detailed explanation of what went wrong]

### Why Did It Happen?
[Root cause analysis - dig deep with "5 Whys"]

Example:
1. **Why did latency spike?** LLM API was rate limiting requests
2. **Why was LLM rate limiting?** Traffic exceeded our quota
3. **Why did traffic exceed quota?** Unexpected viral social media post drove 10x traffic
4. **Why didn't we handle the traffic?** No auto-scaling for LLM quota
5. **Why no auto-scaling?** Not implemented in initial design

### Contributing Factors
- [Factor 1]
- [Factor 2]
- [Factor 3]

### What Went Well?
- [Positive aspect 1]
- [Positive aspect 2]
- [Positive aspect 3]

### What Went Poorly?
- [Negative aspect 1]
- [Negative aspect 2]
- [Negative aspect 3]

---

## Detection and Response

### How Was It Detected?
- [Alert/User report/Monitoring/etc.]
- [Time to detection from start of incident]

### How Was It Diagnosed?
- [Investigation steps taken]
- [Tools used]
- [Time to diagnosis]

### How Was It Resolved?
- [Resolution steps]
- [Time to resolution]

### What Delayed Resolution?
- [Delay factor 1]
- [Delay factor 2]

---

## Action Items

### Immediate Actions (Complete within 24 hours)
- [ ] [Action 1] - Owner: [Name] - Due: [Date]
- [ ] [Action 2] - Owner: [Name] - Due: [Date]

### Short-Term Actions (Complete within 1 week)
- [ ] [Action 1] - Owner: [Name] - Due: [Date]
- [ ] [Action 2] - Owner: [Name] - Due: [Date]

### Long-Term Actions (Complete within 1 month)
- [ ] [Action 1] - Owner: [Name] - Due: [Date]
- [ ] [Action 2] - Owner: [Name] - Due: [Date]

### Process Improvements
- [ ] [Improvement 1] - Owner: [Name] - Due: [Date]
- [ ] [Improvement 2] - Owner: [Name] - Due: [Date]

### Monitoring Improvements
- [ ] [Improvement 1] - Owner: [Name] - Due: [Date]
- [ ] [Improvement 2] - Owner: [Name] - Due: [Date]

### Documentation Updates
- [ ] [Update 1] - Owner: [Name] - Due: [Date]
- [ ] [Update 2] - Owner: [Name] - Due: [Date]

---

## Lessons Learned

### What Did We Learn?
1. [Lesson 1]
2. [Lesson 2]
3. [Lesson 3]

### What Should We Do Differently?
1. [Change 1]
2. [Change 2]
3. [Change 3]

### What Worked Well?
1. [Success 1]
2. [Success 2]
3. [Success 3]

---

## Supporting Information

### Metrics and Graphs
- [Link to Grafana dashboard]
- [Screenshot of key metrics]

### Logs
- [Link to relevant logs]
- [Key log entries]

### Related Incidents
- [INC-YYYY-XXX] - [Brief description] - [Date]
- [INC-YYYY-XXX] - [Brief description] - [Date]

### External References
- [Link to vendor status page]
- [Link to related documentation]

---

## Review and Approval

### Postmortem Review Meeting
- **Date**: [Date]
- **Attendees**: [Names]
- **Discussion Notes**: [Key points discussed]

### Approvals
- [ ] Incident Commander: [Name] - [Date]
- [ ] Engineering Manager: [Name] - [Date]
- [ ] VP Engineering: [Name] - [Date]

### Distribution
- [ ] Shared with engineering team
- [ ] Shared with leadership
- [ ] Shared with affected customers (if applicable)
- [ ] Published to internal wiki

---

## Follow-Up

### Action Item Tracking
- **Review Frequency**: Weekly
- **Owner**: [Name]
- **Next Review**: [Date]

### Effectiveness Measurement
- **Metrics to Track**: [List metrics]
- **Success Criteria**: [Define success]
- **Review Date**: [Date to review effectiveness]

---

## Appendix

### Detailed Technical Analysis
[Optional: Deep technical details for engineers]

### Communication Log
[Optional: All communications during incident]

### Customer Impact Details
[Optional: Detailed customer impact analysis]

---

## Template Usage Notes

### When to Write a Postmortem
- **Required**: All P1 and P2 incidents
- **Recommended**: P3 incidents with interesting learnings
- **Optional**: P4 incidents

### Timeline for Completion
- **Draft**: Within 24 hours of incident resolution
- **Review**: Within 48 hours
- **Final**: Within 72 hours
- **Follow-up**: Weekly until all action items complete

### Best Practices
1. **Be Blameless**: Focus on systems and processes, not individuals
2. **Be Honest**: Document what really happened, not what should have happened
3. **Be Specific**: Use concrete examples and data
4. **Be Actionable**: Every lesson should have an action item
5. **Be Timely**: Write while details are fresh

### Common Mistakes to Avoid
1. Blaming individuals
2. Vague or generic action items
3. Missing root cause analysis
4. Incomplete timeline
5. No follow-up on action items

---

**Document Version**: 1.0  
**Last Updated**: [Date]  
**Owner**: SRE Team
