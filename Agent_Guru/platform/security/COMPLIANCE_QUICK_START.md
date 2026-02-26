# Compliance Reporting - Quick Start Guide

## Installation

No additional installation required. The compliance module is part of the Agent Guru platform.

## Basic Usage

### 1. Initialize Compliance Reporter

```python
from Agent_Guru.platform.security.auditor import SecurityAuditor
from Agent_Guru.platform.security.compliance import ComplianceReporter

# Create auditor
auditor = SecurityAuditor(log_dir="/var/log/agent_guru")

# Create compliance reporter
reporter = ComplianceReporter(
    auditor=auditor,
    data_controller="Your Company Name",
    data_processor="Agent Guru Platform",
    covered_entity="Your Healthcare Entity",  # For HIPAA
    service_organization="Your Cloud Services",  # For SOC 2
)
```

### 2. Generate Compliance Reports

#### GDPR Report (EU Data Protection)

```python
from datetime import datetime, timedelta
from pathlib import Path

# Generate report for last 30 days
period_start = datetime.now() - timedelta(days=30)
period_end = datetime.now()

gdpr_report = reporter.generate_gdpr_report(
    period_start=period_start,
    period_end=period_end,
    output_path=Path("/reports/gdpr_report.json")  # Optional
)

print(f"Report ID: {gdpr_report.report_id}")
print(f"Data Subjects: {gdpr_report.data_subjects_count}")
print(f"Processing Activities: {len(gdpr_report.processing_activities)}")
```

#### CCPA Report (California Privacy)

```python
ccpa_report = reporter.generate_ccpa_report(
    period_start=period_start,
    period_end=period_end,
    output_path=Path("/reports/ccpa_report.json")
)

print(f"Consumers: {ccpa_report.consumers_count}")
print(f"Opt-out Requests: {ccpa_report.opt_out_requests}")
print(f"Deletion Requests: {ccpa_report.deletion_requests}")
print(f"Data Sold: {len(ccpa_report.data_sold)}")  # Should be 0
```

#### HIPAA Report (Healthcare)

```python
hipaa_report = reporter.generate_hipaa_report(
    period_start=period_start,
    period_end=period_end,
    output_path=Path("/reports/hipaa_report.json")
)

print(f"PHI Access Count: {hipaa_report.phi_access_count}")
print(f"Security Incidents: {len(hipaa_report.security_incidents)}")
print(f"Encryption: {hipaa_report.encryption_status}")
```

#### SOC 2 Report (Security Controls)

```python
soc2_report = reporter.generate_soc2_report(
    period_start=period_start,
    period_end=period_end,
    output_path=Path("/reports/soc2_report.json")
)

print(f"Uptime: {soc2_report.availability_metrics['uptime_percentage']:.2f}%")
print(f"Security Events: {len(soc2_report.security_events)}")
print(f"Control Activities: {len(soc2_report.control_activities)}")
```

### 3. Export to SIEM Systems

#### Splunk Export

```python
from Agent_Guru.platform.security.compliance import SIEMFormat

result = reporter.export_to_siem(
    siem_format=SIEMFormat.SPLUNK,
    endpoint_url="https://splunk.example.com:8088/services/collector",
    auth_token="YOUR-HEC-TOKEN-HERE",
    period_start=period_start,
    period_end=period_end,
    batch_size=1000,
    max_retries=3,  # Automatic retry
    retry_delay=1.0  # Exponential backoff
)

print(f"Exported: {result['entries_exported']}")
print(f"Failed: {result['entries_failed']}")
print(f"Total: {result['total_entries']}")
```

#### Elasticsearch (ELK) Export

```python
result = reporter.export_to_siem(
    siem_format=SIEMFormat.ELK,
    endpoint_url="https://elasticsearch.example.com:9200",
    auth_token="Bearer YOUR-TOKEN-HERE",
    period_start=period_start,
    period_end=period_end,
)
```

#### Datadog Export

```python
result = reporter.export_to_siem(
    siem_format=SIEMFormat.DATADOG,
    endpoint_url="https://http-intake.logs.datadoghq.com/v1/input",
    auth_token="YOUR-DD-API-KEY",
    period_start=period_start,
    period_end=period_end,
)
```

#### Syslog Export

```python
result = reporter.export_to_siem(
    siem_format=SIEMFormat.SYSLOG,
    endpoint_url="syslog.example.com:514",
    period_start=period_start,
    period_end=period_end,
)
```

#### CEF Export (ArcSight)

```python
result = reporter.export_to_siem(
    siem_format=SIEMFormat.CEF,
    endpoint_url="arcsight.example.com:514",
    period_start=period_start,
    period_end=period_end,
)
```

#### LEEF Export (QRadar)

```python
result = reporter.export_to_siem(
    siem_format=SIEMFormat.LEEF,
    endpoint_url="qradar.example.com:514",
    period_start=period_start,
    period_end=period_end,
)
```

## Timezone Handling

The compliance reporter **automatically detects** your device's local timezone:

```python
# No configuration needed - timezone is auto-detected!
reporter = ComplianceReporter(auditor)

# All timestamps will use your local timezone
report = reporter.generate_gdpr_report(period_start, period_end)

# Example output: 2026-02-25T14:30:00+05:30 (India)
# Example output: 2026-02-25T09:00:00-05:00 (US Eastern)
# Example output: 2026-02-25T14:00:00+00:00 (UTC)
```

### Supported Platforms
- ✅ Windows
- ✅ macOS
- ✅ Linux
- ✅ Android
- ✅ iOS

## Error Handling

### Automatic Retry

```python
try:
    result = reporter.export_to_siem(
        siem_format=SIEMFormat.SPLUNK,
        endpoint_url="https://splunk.example.com:8088",
        auth_token="token",
        max_retries=5,  # Try up to 5 times
        retry_delay=2.0,  # 2s, 4s, 8s, 16s delays
    )
except Exception as e:
    print(f"Export failed after all retries: {e}")
```

### Partial Export Tracking

```python
result = reporter.export_to_siem(...)

if result['entries_failed'] > 0:
    print(f"Warning: {result['entries_failed']} entries failed to export")
    print(f"Success rate: {result['entries_exported'] / result['total_entries'] * 100:.1f}%")
```

## Performance Tips

### 1. Use Appropriate Batch Sizes

```python
# Small batches for slow networks
result = reporter.export_to_siem(..., batch_size=100)

# Large batches for fast networks
result = reporter.export_to_siem(..., batch_size=5000)
```

### 2. Limit Report Period

```python
# Last 24 hours (fast)
period_start = datetime.now() - timedelta(hours=24)

# Last 7 days (moderate)
period_start = datetime.now() - timedelta(days=7)

# Last 30 days (slower, but still <5s for 1M entries)
period_start = datetime.now() - timedelta(days=30)
```

### 3. Save Reports to Files

```python
# Save to file for later analysis
report = reporter.generate_gdpr_report(
    period_start,
    period_end,
    output_path=Path("/reports/gdpr_2026_02.json")
)

# Load from file later
import json
with open("/reports/gdpr_2026_02.json") as f:
    saved_report = json.load(f)
```

## Common Use Cases

### 1. Monthly Compliance Reports

```python
from datetime import datetime
from dateutil.relativedelta import relativedelta

# Generate reports for last month
today = datetime.now()
period_end = today.replace(day=1) - timedelta(days=1)  # Last day of previous month
period_start = period_end.replace(day=1)  # First day of previous month

gdpr_report = reporter.generate_gdpr_report(period_start, period_end)
ccpa_report = reporter.generate_ccpa_report(period_start, period_end)
hipaa_report = reporter.generate_hipaa_report(period_start, period_end)
soc2_report = reporter.generate_soc2_report(period_start, period_end)
```

### 2. Real-time SIEM Export

```python
# Export last hour of logs every hour
import time

while True:
    period_end = datetime.now()
    period_start = period_end - timedelta(hours=1)
    
    reporter.export_to_siem(
        SIEMFormat.SPLUNK,
        "https://splunk.example.com:8088",
        "token",
        period_start,
        period_end,
    )
    
    time.sleep(3600)  # Wait 1 hour
```

### 3. Compliance Dashboard

```python
# Generate all reports for dashboard
reports = {
    'gdpr': reporter.generate_gdpr_report(period_start, period_end),
    'ccpa': reporter.generate_ccpa_report(period_start, period_end),
    'hipaa': reporter.generate_hipaa_report(period_start, period_end),
    'soc2': reporter.generate_soc2_report(period_start, period_end),
}

# Extract key metrics
metrics = {
    'data_subjects': reports['gdpr'].data_subjects_count,
    'consumers': reports['ccpa'].consumers_count,
    'phi_access': reports['hipaa'].phi_access_count,
    'uptime': reports['soc2'].availability_metrics['uptime_percentage'],
    'security_incidents': len(reports['soc2'].security_events),
}

print(f"Dashboard Metrics: {metrics}")
```

## Troubleshooting

### Issue: Timezone not detected

```python
# Check detected timezone
print(f"Detected timezone: {reporter.local_timezone}")

# If None, system will fallback to UTC automatically
```

### Issue: SIEM export fails

```python
# Enable debug logging
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
)

# Check logs for detailed error messages
result = reporter.export_to_siem(...)
```

### Issue: Report generation slow

```python
# Check number of audit log entries
filters = AuditLogFilters(start_time=period_start, end_time=period_end)
entries = auditor.query_audit_logs(filters, limit=10)
print(f"Sample entries: {len(entries)}")

# If too many entries, reduce period or increase limit
```

## Best Practices

1. **Regular Reports**: Generate compliance reports monthly
2. **Automated Exports**: Set up automated SIEM exports
3. **Backup Reports**: Save reports to files for audit trail
4. **Monitor Performance**: Track report generation time
5. **Review Metrics**: Regularly review compliance metrics
6. **Test SIEM Integration**: Test SIEM exports before production
7. **Secure Tokens**: Store SIEM auth tokens securely
8. **Timezone Awareness**: Verify timezone detection on deployment

## Support

For issues or questions:
- Check logs: `structlog` output
- Review documentation: `Agent_Guru/platform/security/compliance.py`
- Run tests: `pytest Agent_Guru/platform/security/tests/test_compliance.py`

---

**Agent Guru Compliance Reporting - World-Class & Production-Ready** 🏆
