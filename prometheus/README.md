# Prometheus Monitoring Setup for Agent Guru Reasoning Engine

This directory contains Prometheus configuration for monitoring the Agent Guru Reasoning Engine in production.

## Files

- `prometheus.yml` - Main Prometheus configuration
- `alerts.yml` - Alerting rules for the reasoning engine
- `alertmanager.yml` - Alertmanager configuration for alert routing
- `docker-compose.yml` - Docker Compose setup for local testing

## Alert Categories

### 1. Latency Alerts
- **HighP95Latency**: P95 latency >3s (2x target) - CRITICAL
- **HighP99Latency**: P99 latency >5s - WARNING

### 2. Error Rate Alerts
- **HighErrorRate**: Error rate >5% - CRITICAL
- **ElevatedErrorRate**: Error rate >2% - WARNING
- **HighTimeoutRate**: Timeout rate >3% - WARNING

### 3. Degraded Mode Alerts
- **HighDegradedModeRate**: >10% requests in degraded mode - CRITICAL
- **ElevatedDegradedModeRate**: >5% requests in degraded mode - WARNING

### 4. Availability Alerts
- **ServiceDown**: Service not responding - CRITICAL
- **ServiceFlapping**: Service restarting frequently - WARNING
- **LowUptime**: Uptime <99.9% - WARNING

### 5. Resource Alerts
- **HighCPUUsage**: CPU >90% - CRITICAL
- **ElevatedCPUUsage**: CPU >75% - WARNING
- **HighMemoryUsage**: Memory >90% - CRITICAL
- **ElevatedMemoryUsage**: Memory >75% - WARNING
- **HighDiskUsage**: Disk <10% free - CRITICAL
- **HighQueueDepth**: Queue depth >1000 - WARNING

### 6. Dependency Alerts
- **LLMUnavailable**: LLM backend unavailable - CRITICAL
- **DatabaseConnectionFailure**: DB connection failures - CRITICAL
- **RedisConnectionFailure**: Redis connection failures - WARNING

### 7. Business Metrics Alerts
- **LowRequestRate**: Request rate <1 req/s - WARNING
- **HighIntentDetectionFailureRate**: >10% intent detection failures - WARNING
- **HighToolSelectionFailureRate**: >5% tool selection failures - WARNING

## Alert Routing

### Critical Alerts
- **Destination**: PagerDuty + Slack (#alerts-critical)
- **Group Wait**: 10s
- **Repeat Interval**: 1h
- **Action Required**: Immediate response

### Warning Alerts
- **Destination**: Slack (#alerts-warnings)
- **Group Wait**: 1m
- **Repeat Interval**: 12h
- **Action Required**: Monitor and investigate

### Business Metrics
- **Destination**: Slack (#metrics-business)
- **Group Wait**: 5m
- **Repeat Interval**: 24h
- **Action Required**: Review and optimize

## Setup Instructions

### Local Development

1. **Start Prometheus and Alertmanager**:
   ```bash
   cd prometheus
   docker-compose up -d
   ```

2. **Access UIs**:
   - Prometheus: http://localhost:9090
   - Alertmanager: http://localhost:9093

3. **Test alerts**:
   ```bash
   # Trigger a test alert
   curl -X POST http://localhost:9093/api/v1/alerts -d '[
     {
       "labels": {
         "alertname": "TestAlert",
         "severity": "warning"
       },
       "annotations": {
         "summary": "Test alert",
         "description": "This is a test alert"
       }
     }
   ]'
   ```

### Production Deployment

#### Kubernetes (Recommended)

1. **Install Prometheus Operator**:
   ```bash
   kubectl apply -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/main/bundle.yaml
   ```

2. **Deploy Prometheus**:
   ```bash
   kubectl apply -f k8s/monitoring/prometheus.yaml
   ```

3. **Deploy Alertmanager**:
   ```bash
   kubectl apply -f k8s/monitoring/alertmanager.yaml
   ```

4. **Configure secrets**:
   ```bash
   kubectl create secret generic alertmanager-config \
     --from-literal=slack-webhook-url=$SLACK_WEBHOOK_URL \
     --from-literal=pagerduty-service-key=$PAGERDUTY_SERVICE_KEY \
     --from-literal=smtp-username=$SMTP_USERNAME \
     --from-literal=smtp-password=$SMTP_PASSWORD
   ```

#### Docker Compose

1. **Set environment variables**:
   ```bash
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
   export PAGERDUTY_SERVICE_KEY="your-pagerduty-key"
   export SMTP_USERNAME="alerts@agent-guru.com"
   export SMTP_PASSWORD="your-smtp-password"
   ```

2. **Start services**:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

## Configuration

### Environment Variables

Required environment variables for Alertmanager:

- `SLACK_WEBHOOK_URL`: Slack webhook URL for notifications
- `PAGERDUTY_SERVICE_KEY`: PagerDuty integration key
- `SMTP_USERNAME`: SMTP username for email notifications
- `SMTP_PASSWORD`: SMTP password for email notifications

### Customization

#### Adjust Alert Thresholds

Edit `alerts.yml` to modify thresholds:

```yaml
# Example: Change P95 latency threshold from 3s to 2s
- alert: HighP95Latency
  expr: histogram_quantile(0.95, sum(rate(reasoning_engine_latency_seconds_bucket[5m])) by (le, stage)) > 2.0
```

#### Add New Alerts

Add new alert rules to `alerts.yml`:

```yaml
- alert: YourNewAlert
  expr: your_metric > threshold
  for: 5m
  labels:
    severity: warning
    component: reasoning_engine
  annotations:
    summary: "Alert summary"
    description: "Alert description"
    runbook_url: "https://docs.agent-guru.com/runbooks/your-alert"
```

#### Modify Alert Routing

Edit `alertmanager.yml` to change routing:

```yaml
routes:
  - match:
      your_label: your_value
    receiver: 'your-receiver'
```

## Metrics Exposed

The reasoning engine exposes the following metrics at `/metrics`:

### Latency Metrics
- `reasoning_engine_latency_seconds_bucket`: Histogram of request latency by stage
- `reasoning_engine_latency_seconds_sum`: Total latency
- `reasoning_engine_latency_seconds_count`: Request count

### Error Metrics
- `reasoning_engine_errors_total`: Total error count by error type
- `reasoning_engine_timeouts_total`: Total timeout count
- `reasoning_engine_degraded_mode_total`: Degraded mode count

### Request Metrics
- `reasoning_engine_requests_total`: Total request count
- `reasoning_engine_requests_in_progress`: Current in-progress requests
- `reasoning_engine_queue_depth`: Current queue depth

### Component Metrics
- `reasoning_engine_intent_detection_failures_total`: Intent detection failures
- `reasoning_engine_tool_selection_failures_total`: Tool selection failures
- `reasoning_engine_llm_available`: LLM availability (0 or 1)
- `reasoning_engine_db_connection_errors_total`: Database connection errors
- `reasoning_engine_redis_connection_errors_total`: Redis connection errors

### System Metrics
- `process_cpu_seconds_total`: CPU usage
- `process_resident_memory_bytes`: Memory usage
- `process_open_fds`: Open file descriptors

## Runbooks

Runbooks for each alert are available at:
- https://docs.agent-guru.com/runbooks/

Each runbook includes:
- Alert description
- Impact assessment
- Investigation steps
- Resolution procedures
- Prevention measures

## Testing

### Test Alert Rules

```bash
# Validate alert rules syntax
promtool check rules alerts.yml

# Test alert rule evaluation
promtool test rules test_alerts.yml
```

### Test Alertmanager Config

```bash
# Validate alertmanager config
amtool check-config alertmanager.yml

# Test alert routing
amtool config routes test --config.file=alertmanager.yml
```

### Simulate Alerts

```bash
# Send test alert to Alertmanager
curl -X POST http://localhost:9093/api/v1/alerts -H "Content-Type: application/json" -d '[
  {
    "labels": {
      "alertname": "HighP95Latency",
      "severity": "critical",
      "component": "reasoning_engine",
      "instance": "test-instance"
    },
    "annotations": {
      "summary": "High P95 latency detected (>3s)",
      "description": "P95 latency is 4.5s, which exceeds 2x target (3s).",
      "runbook_url": "https://docs.agent-guru.com/runbooks/high-latency"
    },
    "startsAt": "2024-01-01T00:00:00Z"
  }
]'
```

## Monitoring Best Practices

1. **Set appropriate thresholds**: Based on SLOs and historical data
2. **Avoid alert fatigue**: Only alert on actionable issues
3. **Use inhibition rules**: Suppress redundant alerts
4. **Test regularly**: Verify alerts fire correctly
5. **Keep runbooks updated**: Document resolution procedures
6. **Review alert history**: Identify patterns and improve
7. **Monitor alert response time**: Track MTTA and MTTR

## Troubleshooting

### Prometheus Not Scraping Metrics

1. Check target status: http://localhost:9090/targets
2. Verify service is exposing metrics: `curl http://reasoning-engine:8000/metrics`
3. Check network connectivity
4. Review Prometheus logs: `docker logs prometheus`

### Alerts Not Firing

1. Check alert rules: http://localhost:9090/alerts
2. Verify metrics are being collected
3. Test alert expression in Prometheus UI
4. Check alert evaluation interval

### Alertmanager Not Sending Notifications

1. Check Alertmanager status: http://localhost:9093
2. Verify receiver configuration
3. Check Alertmanager logs: `docker logs alertmanager`
4. Test webhook URLs manually

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Alertmanager Documentation](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [PromQL Guide](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Alert Rule Best Practices](https://prometheus.io/docs/practices/alerting/)
