# Log Aggregation Setup for Agent Guru Reasoning Engine

This directory contains configuration for centralized log aggregation and analysis.

## Supported Backends

1. **ELK Stack** (Elasticsearch, Logstash, Kibana) - Recommended for on-premise
2. **AWS CloudWatch** - Recommended for AWS deployments

## Files

- `filebeat.yml` - Filebeat configuration for log shipping
- `elasticsearch-pipeline.json` - Elasticsearch ingest pipeline
- `elasticsearch-index-template.json` - Index template for log storage
- `elasticsearch-ilm-policy.json` - Index lifecycle management policy
- `kibana-alerts.json` - Kibana alerts and saved searches
- `cloudwatch-config.json` - CloudWatch configuration

## Log Retention Policy

| Log Level | Retention Period | Storage |
|-----------|------------------|---------|
| INFO | 30 days | Hot → Warm → Cold → Delete |
| WARNING | 60 days | Hot → Warm → Cold → Delete |
| ERROR | 90 days | Hot → Warm → Cold → Delete |
| CRITICAL | 90 days | Hot → Warm → Cold → Delete |
| AUDIT | 90 days | Hot → Warm → Cold (no delete) |

## Setup Instructions

### ELK Stack Setup

#### 1. Install Elasticsearch

```bash
# Download and install Elasticsearch
wget https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.11.0-linux-x86_64.tar.gz
tar -xzf elasticsearch-8.11.0-linux-x86_64.tar.gz
cd elasticsearch-8.11.0/

# Start Elasticsearch
./bin/elasticsearch
```

#### 2. Create Index Template

```bash
curl -X PUT "localhost:9200/_index_template/reasoning-engine-template" \
  -H 'Content-Type: application/json' \
  -d @elasticsearch-index-template.json
```

#### 3. Create ILM Policy

```bash
curl -X PUT "localhost:9200/_ilm/policy/reasoning-engine-policy" \
  -H 'Content-Type: application/json' \
  -d @elasticsearch-ilm-policy.json
```

#### 4. Create Ingest Pipeline

```bash
curl -X PUT "localhost:9200/_ingest/pipeline/reasoning-engine-pipeline" \
  -H 'Content-Type: application/json' \
  -d @elasticsearch-pipeline.json
```

#### 5. Install and Configure Filebeat

```bash
# Download and install Filebeat
wget https://artifacts.elastic.co/downloads/beats/filebeat/filebeat-8.11.0-linux-x86_64.tar.gz
tar -xzf filebeat-8.11.0-linux-x86_64.tar.gz
cd filebeat-8.11.0-linux-x86_64/

# Copy configuration
cp /path/to/filebeat.yml filebeat.yml

# Set environment variables
export ELASTICSEARCH_HOST="localhost:9200"
export ELASTICSEARCH_USERNAME="elastic"
export ELASTICSEARCH_PASSWORD="your-password"
export ENVIRONMENT="production"

# Start Filebeat
./filebeat -e
```

#### 6. Install Kibana

```bash
# Download and install Kibana
wget https://artifacts.elastic.co/downloads/kibana/kibana-8.11.0-linux-x86_64.tar.gz
tar -xzf kibana-8.11.0-linux-x86_64.tar.gz
cd kibana-8.11.0/

# Start Kibana
./bin/kibana
```

#### 7. Import Kibana Alerts

```bash
# Import alerts and saved searches
curl -X POST "localhost:5601/api/saved_objects/_import" \
  -H "kbn-xsrf: true" \
  --form file=@kibana-alerts.json
```

### CloudWatch Setup

#### 1. Create Log Groups

```bash
# Using AWS CLI
aws logs create-log-group \
  --log-group-name /aws/agent-guru/reasoning-engine/application \
  --kms-key-id ${KMS_KEY_ID} \
  --tags Service=reasoning-engine,Environment=production

aws logs create-log-group \
  --log-group-name /aws/agent-guru/reasoning-engine/error \
  --kms-key-id ${KMS_KEY_ID} \
  --tags Service=reasoning-engine,Environment=production

aws logs create-log-group \
  --log-group-name /aws/agent-guru/reasoning-engine/audit \
  --kms-key-id ${KMS_KEY_ID} \
  --tags Service=reasoning-engine,Environment=production,Sensitive=true
```

#### 2. Set Retention Policies

```bash
aws logs put-retention-policy \
  --log-group-name /aws/agent-guru/reasoning-engine/application \
  --retention-in-days 30

aws logs put-retention-policy \
  --log-group-name /aws/agent-guru/reasoning-engine/error \
  --retention-in-days 90

aws logs put-retention-policy \
  --log-group-name /aws/agent-guru/reasoning-engine/audit \
  --retention-in-days 90
```

#### 3. Create Metric Filters

```bash
# Critical errors metric filter
aws logs put-metric-filter \
  --log-group-name /aws/agent-guru/reasoning-engine/application \
  --filter-name CriticalErrors \
  --filter-pattern '[timestamp, level=CRITICAL || level=FATAL, ...]' \
  --metric-transformations \
    metricName=CriticalErrorCount,metricNamespace=AgentGuru/ReasoningEngine,metricValue=1,defaultValue=0
```

#### 4. Create CloudWatch Alarms

```bash
# Critical errors alarm
aws cloudwatch put-metric-alarm \
  --alarm-name ReasoningEngine-CriticalErrors \
  --alarm-description "Alert when critical errors exceed threshold" \
  --metric-name CriticalErrorCount \
  --namespace AgentGuru/ReasoningEngine \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions ${SNS_TOPIC_ARN_CRITICAL}
```

#### 5. Configure Filebeat for CloudWatch

```bash
# Update filebeat.yml
export CLOUDWATCH_ENABLED=true
export ELASTICSEARCH_ENABLED=false
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key

# Start Filebeat
./filebeat -e
```

## Log Format

All logs are structured JSON with the following fields:

```json
{
  "@timestamp": "2024-01-01T12:00:00.000Z",
  "log_level": "INFO",
  "logger": "reasoning_engine.intent_detection",
  "message": "Intent detected successfully",
  "service": "reasoning-engine",
  "environment": "production",
  "component": "intent_detection",
  "user_id": "user123",
  "conversation_id": "conv456",
  "turn_id": "turn789",
  "trace_id": "abc123",
  "span_id": "def456",
  "intent_type": "set_timer",
  "duration_ms": 45.2,
  "status": "success"
}
```

## Log-Based Alerts

### Critical Alerts (PagerDuty + Slack)

1. **Critical Errors**: >5 critical/fatal errors in 5 minutes
2. **LLM Unavailable**: >10 LLM failures in 5 minutes
3. **Database Connection Failures**: >10 failures in 5 minutes
4. **Security Events**: Any unauthorized access attempts

### Warning Alerts (Slack)

1. **High Error Rate**: >50 errors in 5 minutes
2. **Unusual Error Pattern**: >100 errors of same type in 1 hour

## Kibana Dashboards

### 1. Error Analysis Dashboard
- Error rate over time
- Error distribution by component
- Top error messages
- Error trends

### 2. Performance Dashboard
- Latency distribution
- Slow requests (>3s)
- Request volume
- Component performance

### 3. Security Dashboard
- Audit log events
- Failed authentication attempts
- Permission denials
- Suspicious activity

### 4. Business Metrics Dashboard
- Request volume by intent type
- User engagement metrics
- Tool usage statistics
- Conversation metrics

## CloudWatch Insights Queries

### Top 10 Error Messages
```
fields @timestamp, @message
| filter level = "ERROR"
| stats count() by @message
| sort count desc
| limit 10
```

### Latency Distribution
```
fields @timestamp, duration_ms
| filter duration_ms > 0
| stats avg(duration_ms), max(duration_ms), pct(duration_ms, 50), pct(duration_ms, 95), pct(duration_ms, 99)
```

### Error Rate by Component
```
fields @timestamp, component
| filter level = "ERROR"
| stats count() by component
| sort count desc
```

### Security Events
```
fields @timestamp, user_id, @message
| filter component = "audit" and (@message like /permission denied/ or @message like /unauthorized/ or @message like /authentication failed/)
```

## PII Redaction

Filebeat automatically redacts PII from logs:

- Email addresses → `[EMAIL_REDACTED]`
- Phone numbers → `[PHONE_REDACTED]`
- Credit card numbers → `[CC_REDACTED]`
- SSN → `[SSN_REDACTED]`

## Troubleshooting

### Filebeat Not Shipping Logs

1. Check Filebeat status:
   ```bash
   curl http://localhost:5066/stats
   ```

2. Check Filebeat logs:
   ```bash
   tail -f /var/log/filebeat/filebeat
   ```

3. Verify Elasticsearch connectivity:
   ```bash
   curl -u elastic:password http://localhost:9200/_cluster/health
   ```

### Logs Not Appearing in Kibana

1. Check index exists:
   ```bash
   curl http://localhost:9200/_cat/indices/reasoning-engine-*
   ```

2. Refresh index pattern in Kibana:
   - Management → Index Patterns → Refresh

3. Check for parsing errors:
   ```bash
   curl http://localhost:9200/reasoning-engine-*/_search?q=error.message:*
   ```

### CloudWatch Logs Not Appearing

1. Check IAM permissions:
   ```bash
   aws iam get-user
   aws logs describe-log-groups
   ```

2. Check log group exists:
   ```bash
   aws logs describe-log-groups --log-group-name-prefix /aws/agent-guru
   ```

3. Check Filebeat CloudWatch output:
   ```bash
   ./filebeat test output
   ```

## Best Practices

1. **Use structured logging**: Always log in JSON format
2. **Include context**: Add trace_id, user_id, conversation_id to all logs
3. **Log at appropriate levels**: DEBUG for development, INFO for production
4. **Avoid logging PII**: Use redaction for sensitive data
5. **Monitor log volume**: Set up alerts for unusual log volume
6. **Regular log analysis**: Review logs weekly for patterns
7. **Test alerts**: Regularly test alert configurations
8. **Document incidents**: Use logs for postmortem analysis

## References

- [Filebeat Documentation](https://www.elastic.co/guide/en/beats/filebeat/current/index.html)
- [Elasticsearch Documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [Kibana Documentation](https://www.elastic.co/guide/en/kibana/current/index.html)
- [CloudWatch Logs Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/WhatIsCloudWatchLogs.html)
