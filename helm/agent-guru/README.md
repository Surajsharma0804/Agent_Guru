# Agent Guru Reasoning Engine Helm Chart

This Helm chart deploys the Agent Guru Core Reasoning Engine to Kubernetes.

## Prerequisites

- Kubernetes 1.24+
- Helm 3.8+
- kubectl configured to access your cluster
- cert-manager (for TLS certificates)
- Prometheus Operator (for custom metrics)

## Installation

### Quick Start

```bash
# Install to production
helm install agent-guru ./helm/agent-guru \
  --namespace agent-guru-production \
  --create-namespace \
  --values ./helm/agent-guru/values-prod.yaml

# Install to staging
helm install agent-guru ./helm/agent-guru \
  --namespace agent-guru-staging \
  --create-namespace \
  --values ./helm/agent-guru/values-staging.yaml

# Install to development
helm install agent-guru ./helm/agent-guru \
  --namespace agent-guru-dev \
  --create-namespace \
  --values ./helm/agent-guru/values-dev.yaml
```

### Using Deployment Scripts

```bash
# Linux/macOS
./scripts/deploy-helm.sh production agent-guru-production

# Windows
.\scripts\deploy-helm.ps1 -Environment production -Namespace agent-guru-production
```

## Configuration

### Key Configuration Values

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `3` |
| `image.repository` | Image repository | `ghcr.io/agent-guru/agent-guru` |
| `image.tag` | Image tag | `latest` |
| `resources.requests.cpu` | CPU request | `1000m` |
| `resources.requests.memory` | Memory request | `2Gi` |
| `resources.limits.cpu` | CPU limit | `2000m` |
| `resources.limits.memory` | Memory limit | `4Gi` |
| `autoscaling.enabled` | Enable HPA | `true` |
| `autoscaling.minReplicas` | Minimum replicas | `3` |
| `autoscaling.maxReplicas` | Maximum replicas | `20` |
| `ingress.enabled` | Enable ingress | `true` |

### Environment-Specific Values

- **Production** (`values-prod.yaml`): 3-20 replicas, 2Gi/1CPU requests, 4Gi/2CPU limits
- **Staging** (`values-staging.yaml`): 2-10 replicas, 1Gi/500m requests, 2Gi/1CPU limits
- **Development** (`values-dev.yaml`): 1 replica, 512Mi/250m requests, 1Gi/500m limits

## Upgrading

```bash
# Upgrade production
helm upgrade agent-guru ./helm/agent-guru \
  --namespace agent-guru-production \
  --values ./helm/agent-guru/values-prod.yaml \
  --wait \
  --timeout 10m

# Upgrade with custom values
helm upgrade agent-guru ./helm/agent-guru \
  --namespace agent-guru-production \
  --set image.tag=v1.2.3 \
  --wait
```

## Rollback

```bash
# List releases
helm history agent-guru -n agent-guru-production

# Rollback to previous version
helm rollback agent-guru -n agent-guru-production

# Rollback to specific revision
helm rollback agent-guru 3 -n agent-guru-production
```

## Uninstallation

```bash
helm uninstall agent-guru -n agent-guru-production
```

## Monitoring

The chart includes:
- Prometheus ServiceMonitor for metrics collection
- PrometheusRule for alerting
- Custom metrics for HPA (request_queue_depth, request_latency_p95)

Access metrics:
```bash
kubectl port-forward -n agent-guru-production svc/agent-guru 9090:9090
curl http://localhost:9090/metrics
```

## Troubleshooting

### Check pod status
```bash
kubectl get pods -n agent-guru-production
kubectl describe pod <pod-name> -n agent-guru-production
```

### View logs
```bash
kubectl logs -n agent-guru-production -l app=agent-guru-reasoning --tail=100 -f
```

### Check HPA status
```bash
kubectl get hpa -n agent-guru-production
kubectl describe hpa agent-guru -n agent-guru-production
```

### Check ingress
```bash
kubectl get ingress -n agent-guru-production
kubectl describe ingress agent-guru -n agent-guru-production
```

## Security

- Runs as non-root user (UID 1000)
- Drops all capabilities
- Read-only root filesystem
- Secrets managed via Kubernetes secrets
- TLS enabled by default

## Support

For issues and questions:
- GitHub: https://github.com/agent-guru/agent-guru
- Email: team@agent-guru.ai
