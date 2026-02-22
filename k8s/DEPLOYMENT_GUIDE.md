# Agent Guru Kubernetes Deployment Guide

This guide covers deploying the Agent Guru Core Reasoning Engine to Kubernetes using Docker and Helm.

## Overview

The deployment includes:
- **Docker**: Multi-stage Alpine-based images optimized for size
- **Kubernetes**: Production-ready manifests with high availability
- **Helm**: Templated deployments for multiple environments
- **Autoscaling**: HPA with CPU, memory, and custom metrics
- **Monitoring**: Prometheus metrics and alerting
- **Security**: Non-root containers, TLS, secrets management

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Kubernetes Cluster                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Ingress (TLS)                                        │  │
│  │  - api.agent-guru.ai                                  │  │
│  │  - reasoning.agent-guru.ai                            │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Service (ClusterIP)                                  │  │
│  │  - Load balancing                                     │  │
│  │  - Session affinity                                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Deployment (3-20 replicas)                           │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐     │  │
│  │  │   Pod 1    │  │   Pod 2    │  │   Pod 3    │     │  │
│  │  │  Reasoning │  │  Reasoning │  │  Reasoning │     │  │
│  │  │   Engine   │  │   Engine   │  │   Engine   │     │  │
│  │  └────────────┘  └────────────┘  └────────────┘     │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  HPA (Horizontal Pod Autoscaler)                      │  │
│  │  - CPU: 70% target                                    │  │
│  │  - Memory: 80% target                                 │  │
│  │  - Custom: queue depth, latency                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### Required Tools
- Docker 20.10+
- Kubernetes 1.24+
- Helm 3.8+
- kubectl configured

### Cluster Requirements
- cert-manager (for TLS)
- Prometheus Operator (for custom metrics)
- Ingress controller (nginx recommended)
- Metrics server (for HPA)

## Quick Start

### 1. Build Docker Image

```bash
# Linux/macOS
./scripts/build-docker.sh 1.0.0 ghcr.io/agent-guru

# Windows
.\scripts\build-docker.ps1 -Version 1.0.0 -Registry ghcr.io/agent-guru

# Push to registry
PUSH=true ./scripts/build-docker.sh 1.0.0 ghcr.io/agent-guru
```

### 2. Deploy with Helm

```bash
# Production
./scripts/deploy-helm.sh production agent-guru-production

# Staging
./scripts/deploy-helm.sh staging agent-guru-staging

# Development
./scripts/deploy-helm.sh dev agent-guru-dev
```

### 3. Verify Deployment

```bash
# Check pods
kubectl get pods -n agent-guru-production

# Check services
kubectl get svc -n agent-guru-production

# Check ingress
kubectl get ingress -n agent-guru-production

# View logs
kubectl logs -n agent-guru-production -l app=agent-guru-reasoning --tail=100 -f
```

## Detailed Deployment Steps

### Step 1: Prepare Secrets

Create secrets for API keys and credentials:

```bash
# Create namespace
kubectl create namespace agent-guru-production

# Create secrets
kubectl create secret generic agent-guru-secrets \
  --from-literal=openai-api-key=YOUR_OPENAI_KEY \
  --from-literal=anthropic-api-key=YOUR_ANTHROPIC_KEY \
  --from-literal=sentry-dsn=YOUR_SENTRY_DSN \
  -n agent-guru-production

# Create image pull secret
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_TOKEN \
  -n agent-guru-production
```

### Step 2: Build and Push Image

```bash
# Build image
docker build \
  --build-arg BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
  --build-arg VCS_REF=$(git rev-parse --short HEAD) \
  --build-arg VERSION=1.0.0 \
  --tag ghcr.io/agent-guru/agent-guru:1.0.0 \
  --tag ghcr.io/agent-guru/agent-guru:latest \
  .

# Push to registry
docker push ghcr.io/agent-guru/agent-guru:1.0.0
docker push ghcr.io/agent-guru/agent-guru:latest
```

### Step 3: Deploy with Helm

```bash
# Install
helm install agent-guru ./helm/agent-guru \
  --namespace agent-guru-production \
  --values ./helm/agent-guru/values-prod.yaml \
  --wait \
  --timeout 10m

# Upgrade
helm upgrade agent-guru ./helm/agent-guru \
  --namespace agent-guru-production \
  --values ./helm/agent-guru/values-prod.yaml \
  --wait \
  --timeout 10m
```

### Step 4: Configure DNS

Point your domain to the ingress load balancer:

```bash
# Get ingress IP
kubectl get ingress -n agent-guru-production

# Create DNS A records
api.agent-guru.ai -> INGRESS_IP
reasoning.agent-guru.ai -> INGRESS_IP
```

### Step 5: Verify TLS

```bash
# Check certificate
kubectl get certificate -n agent-guru-production

# Test HTTPS
curl https://api.agent-guru.ai/health
```

## Environment Configuration

### Production
- **Replicas**: 3-20 (autoscaling)
- **Resources**: 2Gi/1CPU requests, 4Gi/2CPU limits
- **Image**: `latest` tag
- **Log Level**: INFO
- **Monitoring**: Full observability stack

### Staging
- **Replicas**: 2-10 (autoscaling)
- **Resources**: 1Gi/500m requests, 2Gi/1CPU limits
- **Image**: `main` tag (auto-deployed)
- **Log Level**: DEBUG
- **Monitoring**: Basic metrics

### Development
- **Replicas**: 1 (no autoscaling)
- **Resources**: 512Mi/250m requests, 1Gi/500m limits
- **Image**: `dev` tag
- **Log Level**: DEBUG
- **Monitoring**: Disabled

## Autoscaling

### HPA Configuration

The HPA scales based on:
1. **CPU**: Target 70% utilization
2. **Memory**: Target 80% utilization
3. **Queue Depth**: Scale up if > 10 requests queued
4. **Latency**: Scale up if P95 > 1.5s

### Scaling Behavior

**Scale Up**:
- Immediate (no stabilization window)
- Max 50% increase or 5 pods per 30s
- Aggressive policy for responsiveness

**Scale Down**:
- 5-minute stabilization window
- Max 10% decrease or 1 pod per 60s
- Conservative policy for stability

### Testing Autoscaling

```bash
# Generate load
kubectl run -it --rm load-generator \
  --image=busybox \
  --restart=Never \
  -- /bin/sh -c "while true; do wget -q -O- http://agent-guru.agent-guru-production/health; done"

# Watch HPA
kubectl get hpa -n agent-guru-production -w

# Watch pods
kubectl get pods -n agent-guru-production -w
```

## Monitoring

### Metrics

Access Prometheus metrics:

```bash
# Port forward
kubectl port-forward -n agent-guru-production svc/agent-guru 9090:9090

# View metrics
curl http://localhost:9090/metrics
```

### Key Metrics

- `request_queue_depth`: Number of queued requests
- `request_latency_p95`: 95th percentile latency
- `request_total`: Total requests
- `request_errors_total`: Total errors
- `reasoning_duration_seconds`: Reasoning time

### Alerts

Configured alerts:
- High queue depth (> 50 for 5 minutes)
- High latency (> 2s for 5 minutes)
- HPA maxed out (at max replicas for 10 minutes)

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n agent-guru-production

# Check events
kubectl get events -n agent-guru-production --sort-by='.lastTimestamp'

# Check logs
kubectl logs <pod-name> -n agent-guru-production
```

### Image Pull Errors

```bash
# Verify secret
kubectl get secret ghcr-secret -n agent-guru-production -o yaml

# Test image pull
docker pull ghcr.io/agent-guru/agent-guru:latest
```

### HPA Not Scaling

```bash
# Check metrics server
kubectl top nodes
kubectl top pods -n agent-guru-production

# Check HPA status
kubectl describe hpa agent-guru -n agent-guru-production

# Check custom metrics
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1
```

### Ingress Not Working

```bash
# Check ingress
kubectl describe ingress agent-guru -n agent-guru-production

# Check ingress controller
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx

# Test service directly
kubectl port-forward -n agent-guru-production svc/agent-guru 8080:80
curl http://localhost:8080/health
```

## Rollback

### Helm Rollback

```bash
# List releases
helm history agent-guru -n agent-guru-production

# Rollback to previous
helm rollback agent-guru -n agent-guru-production

# Rollback to specific revision
helm rollback agent-guru 3 -n agent-guru-production
```

### Manual Rollback

```bash
# Scale down new version
kubectl scale deployment agent-guru -n agent-guru-production --replicas=0

# Deploy previous version
kubectl set image deployment/agent-guru \
  reasoning=ghcr.io/agent-guru/agent-guru:1.0.0 \
  -n agent-guru-production

# Scale up
kubectl scale deployment agent-guru -n agent-guru-production --replicas=3
```

## Maintenance

### Update Image

```bash
# Update to new version
helm upgrade agent-guru ./helm/agent-guru \
  --namespace agent-guru-production \
  --set image.tag=1.1.0 \
  --wait
```

### Update Configuration

```bash
# Edit values
vim ./helm/agent-guru/values-prod.yaml

# Apply changes
helm upgrade agent-guru ./helm/agent-guru \
  --namespace agent-guru-production \
  --values ./helm/agent-guru/values-prod.yaml \
  --wait
```

### Restart Pods

```bash
# Rolling restart
kubectl rollout restart deployment agent-guru -n agent-guru-production

# Watch rollout
kubectl rollout status deployment agent-guru -n agent-guru-production
```

## Security Best Practices

1. **Non-root containers**: All containers run as UID 1000
2. **Read-only filesystem**: Root filesystem is read-only
3. **Dropped capabilities**: All Linux capabilities dropped
4. **TLS everywhere**: HTTPS enforced with cert-manager
5. **Secrets management**: Use Kubernetes secrets or external secrets operator
6. **Network policies**: Restrict pod-to-pod communication
7. **RBAC**: Minimal permissions for service accounts
8. **Image scanning**: Scan images for vulnerabilities

## Performance Tuning

### Resource Optimization

```yaml
# Adjust based on actual usage
resources:
  requests:
    memory: "2Gi"  # Minimum needed
    cpu: "1000m"   # Minimum needed
  limits:
    memory: "4Gi"  # Maximum allowed
    cpu: "2000m"   # Maximum allowed
```

### HPA Tuning

```yaml
# Adjust thresholds
autoscaling:
  targetCPUUtilizationPercentage: 70  # Lower = more aggressive scaling
  targetMemoryUtilizationPercentage: 80
```

### Pod Affinity

```yaml
# Spread pods across nodes
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          topologyKey: kubernetes.io/hostname
```

## Cost Optimization

1. **Right-size resources**: Monitor actual usage and adjust
2. **Use spot instances**: For non-critical workloads
3. **Enable autoscaling**: Scale down during low traffic
4. **Use node affinity**: Place pods on cheaper node types
5. **Optimize images**: Smaller images = faster pulls = lower costs

## Support

For issues and questions:
- GitHub: https://github.com/agent-guru/agent-guru
- Email: team@agent-guru.ai
- Docs: https://docs.agent-guru.ai
