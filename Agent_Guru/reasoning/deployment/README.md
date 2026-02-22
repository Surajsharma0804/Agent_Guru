# Agent Guru Deployment Automation

This directory contains the deployment automation infrastructure for the Agent Guru Reasoning Engine.

## Overview

The deployment system implements:
- **Blue-Green Deployments**: Zero-downtime deployments with instant rollback capability
- **Automated Rollback**: Automatic rollback on health check failures, error rate spikes, or latency degradation
- **Comprehensive Notifications**: Slack notifications for all deployment events with rich metadata

## Components

### 1. Blue-Green Deployment Pipeline (`.github/workflows/cd.yml`)

Implements blue-green deployment strategy for both staging and production environments.

**Features**:
- Automatic color detection (blue/green)
- Parallel deployment to inactive color
- Comprehensive smoke tests before traffic switch
- Canary testing (production only)
- Instant rollback on failure
- Automatic cleanup of old deployments

**Workflow**:
1. Build Docker image
2. Deploy to inactive color (green if blue is active, vice versa)
3. Run smoke tests on new deployment
4. Switch traffic to new deployment
5. Verify deployment health
6. Scale down old deployment (keep for rollback)

**Triggers**:
- **Staging**: Automatic on push to `main` branch
- **Production**: Automatic on release tags (`v*.*.*`)

### 2. Rollback Monitor (`rollback_monitor.py`)

Continuous monitoring service that automatically triggers rollbacks when issues are detected.

**Monitored Metrics**:
- Health check status (HTTP 200 from `/health`)
- Error rate (from Prometheus)
- P95 latency (from Prometheus)
- P99 latency (from Prometheus)
- Request count

**Rollback Triggers**:
- **Health Check Failure**: 3 consecutive failures
- **Error Rate Spike**: >5% error rate
- **Latency Degradation**: >2x baseline P95 latency

**Configuration** (Environment Variables):
```bash
HEALTH_CHECK_URL=https://agent-guru.example.com/health
PROMETHEUS_URL=http://prometheus:9090
KUBERNETES_NAMESPACE=agent-guru-production
SERVICE_NAME=agent-guru-reasoning
ERROR_RATE_THRESHOLD=5.0
LATENCY_BASELINE_P95=1500.0
LATENCY_DEGRADATION_MULTIPLIER=2.0
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**Deployment**:
```bash
# Apply Kubernetes configuration
kubectl apply -f k8s/rollback-monitor.yaml

# Set Slack webhook (optional)
kubectl create secret generic rollback-monitor-secrets \
  -n agent-guru-production \
  --from-literal=slack-webhook-url=YOUR_WEBHOOK_URL
```

### 3. Notification System (`notifications.py`)

Rich notification system for deployment events.

**Notification Types**:
- Deployment Started
- Deployment Success
- Deployment Failure
- Deployment Rollback

**Notification Channels**:
- Slack (with rich formatting, buttons, and metadata)
- Email (future)
- PagerDuty (future)

**Slack Message Format**:
- Color-coded based on status (blue/green/red/orange)
- Deployment metadata (environment, version, commit, deployer, duration)
- Commit message
- Error details (on failure)
- Action buttons (View Logs, View Metrics, Grafana Dashboard)

## Usage

### Manual Deployment

**Staging**:
```bash
# Push to main branch
git push origin main

# Deployment happens automatically
```

**Production**:
```bash
# Create release tag
git tag v1.0.0
git push origin v1.0.0

# Deployment happens automatically with approval gate
```

### Manual Rollback

**Via kubectl**:
```bash
# Get current active color
CURRENT_COLOR=$(kubectl get service agent-guru-reasoning \
  -n agent-guru-production \
  -o jsonpath='{.spec.selector.color}')

# Determine target color
if [ "$CURRENT_COLOR" == "blue" ]; then
  TARGET_COLOR="green"
else
  TARGET_COLOR="blue"
fi

# Scale up target deployment
kubectl scale deployment/agent-guru-reasoning-$TARGET_COLOR \
  -n agent-guru-production \
  --replicas=3

# Wait for ready
kubectl rollout status deployment/agent-guru-reasoning-$TARGET_COLOR \
  -n agent-guru-production

# Switch traffic
kubectl patch service agent-guru-reasoning \
  -n agent-guru-production \
  -p '{"spec":{"selector":{"color":"'$TARGET_COLOR'"}}}'

# Scale down old deployment
kubectl scale deployment/agent-guru-reasoning-$CURRENT_COLOR \
  -n agent-guru-production \
  --replicas=0
```

**Via Rollback Monitor**:
```bash
# Trigger manual rollback
kubectl exec -n agent-guru-production \
  $(kubectl get pod -n agent-guru-production -l app=rollback-monitor -o jsonpath='{.items[0].metadata.name}') \
  -- python -c "
import asyncio
from rollback_monitor import RollbackMonitor, RollbackConfig
config = RollbackConfig()
monitor = RollbackMonitor(config)
asyncio.run(monitor.manual_rollback())
"
```

### Monitoring Deployments

**View Deployment Status**:
```bash
# Check current active color
kubectl get service agent-guru-reasoning \
  -n agent-guru-production \
  -o jsonpath='{.spec.selector.color}'

# Check blue deployment
kubectl get deployment agent-guru-reasoning-blue \
  -n agent-guru-production

# Check green deployment
kubectl get deployment agent-guru-reasoning-green \
  -n agent-guru-production

# Check pods
kubectl get pods -n agent-guru-production -l app=agent-guru-reasoning
```

**View Rollback Monitor Logs**:
```bash
kubectl logs -n agent-guru-production \
  -l app=rollback-monitor \
  --follow
```

**View Metrics**:
- Prometheus: https://prometheus.agent-guru.example.com
- Grafana: https://grafana.agent-guru.example.com

## Configuration

### GitHub Secrets

Required secrets in GitHub repository settings:

```
KUBE_CONFIG_STAGING: Base64-encoded kubeconfig for staging cluster
KUBE_CONFIG_PRODUCTION: Base64-encoded kubeconfig for production cluster
SLACK_WEBHOOK_URL: Slack webhook URL for notifications
```

### Kubernetes Secrets

```bash
# Rollback monitor Slack webhook
kubectl create secret generic rollback-monitor-secrets \
  -n agent-guru-production \
  --from-literal=slack-webhook-url=YOUR_WEBHOOK_URL
```

### Kubernetes ConfigMaps

```bash
# Rollback monitor configuration
kubectl create configmap rollback-monitor-config \
  -n agent-guru-production \
  --from-literal=HEALTH_CHECK_URL=https://agent-guru.example.com/health \
  --from-literal=PROMETHEUS_URL=http://prometheus:9090 \
  --from-literal=ERROR_RATE_THRESHOLD=5.0 \
  --from-literal=LATENCY_BASELINE_P95=1500.0
```

## Performance Targets

- **Deployment Time**: <5 minutes (staging), <10 minutes (production)
- **Rollback Time**: <60 seconds
- **Monitoring Interval**: 30 seconds
- **Rollback Decision**: <5 seconds
- **Zero Downtime**: 100% uptime during deployments

## Troubleshooting

### Deployment Stuck

```bash
# Check deployment status
kubectl rollout status deployment/agent-guru-reasoning-blue -n agent-guru-production
kubectl rollout status deployment/agent-guru-reasoning-green -n agent-guru-production

# Check pod events
kubectl describe pods -n agent-guru-production -l app=agent-guru-reasoning

# Check logs
kubectl logs -n agent-guru-production -l app=agent-guru-reasoning --tail=100
```

### Rollback Monitor Not Working

```bash
# Check rollback monitor status
kubectl get deployment rollback-monitor -n agent-guru-production

# Check logs
kubectl logs -n agent-guru-production -l app=rollback-monitor --tail=100

# Check configuration
kubectl get configmap rollback-monitor-config -n agent-guru-production -o yaml
kubectl get secret rollback-monitor-secrets -n agent-guru-production -o yaml
```

### Notifications Not Sent

```bash
# Check Slack webhook URL is set
kubectl get secret rollback-monitor-secrets -n agent-guru-production -o jsonpath='{.data.slack-webhook-url}' | base64 -d

# Test notification manually
python -c "
import asyncio
from Agent_Guru.reasoning.deployment.notifications import send_deployment_success
asyncio.run(send_deployment_success(
    environment='staging',
    version='test',
    commit_sha='test123',
    commit_message='Test notification',
    deployer='manual',
    duration_seconds=10
))
"
```

## Best Practices

1. **Always test in staging first**: Never deploy directly to production
2. **Monitor after deployment**: Watch metrics for at least 10 minutes after production deployment
3. **Keep old deployment running**: Don't delete old deployment immediately (keep for 24h)
4. **Use release tags**: Always use semantic versioning for production releases
5. **Document changes**: Include clear commit messages for deployment notifications
6. **Test rollback**: Periodically test rollback procedures in staging

## Future Enhancements

- [ ] Gradual traffic shifting (canary deployments with Istio/Linkerd)
- [ ] A/B testing support
- [ ] Multi-region deployments
- [ ] Automated performance testing before traffic switch
- [ ] Integration with incident management (PagerDuty)
- [ ] Email notifications
- [ ] Deployment approval workflows
- [ ] Deployment scheduling (maintenance windows)

## References

- [Blue-Green Deployment Pattern](https://martinfowler.com/bliki/BlueGreenDeployment.html)
- [Kubernetes Deployment Strategies](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Prometheus Monitoring](https://prometheus.io/docs/introduction/overview/)
- [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks)
