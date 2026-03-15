# Agent Guru Reasoning Engine - Deployment Guide

> For the full deployment guide including Terraform infrastructure setup, see [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md).

## Prerequisites

- Docker >= 24.0.0
- kubectl >= 1.27.0
- Helm >= 3.12.0
- Access to a Kubernetes cluster
- Container registry credentials

---

## Quick Deployment

### 1. Build and Push Docker Image

```bash
export REGISTRY=your-registry.example.com
export IMAGE_TAG=v1.0.0

docker build -t ${REGISTRY}/agent-guru-reasoning:${IMAGE_TAG} .
docker push ${REGISTRY}/agent-guru-reasoning:${IMAGE_TAG}
```

### 2. Create Namespace and Secrets

```bash
kubectl create namespace agent-guru-prod

kubectl create secret generic reasoning-engine-secrets \
  --namespace=agent-guru-prod \
  --from-literal=database-url="postgresql://user:pass@host:5432/db" \
  --from-literal=redis-url="redis://host:6379" \
  --from-literal=openai-api-key="sk-..."
```

### 3. Deploy with Helm

```bash
helm upgrade --install reasoning-engine ./helm/reasoning-engine \
  --namespace=agent-guru-prod \
  --values=values-prod.yaml \
  --wait \
  --timeout=10m
```

### 4. Verify Deployment

```bash
kubectl get pods -n agent-guru-prod
curl -f https://api.agent-guru.com/health
```

---

## Helm Values (Production)

```yaml
# values-prod.yaml
image:
  repository: your-registry.example.com/agent-guru-reasoning
  tag: v1.0.0

replicaCount: 3

resources:
  requests:
    cpu: 1000m
    memory: 2Gi
  limits:
    cpu: 2000m
    memory: 4Gi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70

env:
  - name: ENVIRONMENT
    value: production
  - name: LOG_LEVEL
    value: INFO
  - name: LLM_BACKEND
    value: hybrid
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: reasoning-engine-secrets
        key: database-url
  - name: REDIS_URL
    valueFrom:
      secretKeyRef:
        name: reasoning-engine-secrets
        key: redis-url
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: reasoning-engine-secrets
        key: openai-api-key

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: api.agent-guru.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: agent-guru-tls
      hosts:
        - api.agent-guru.com

livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```

---

## Environment Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level |
| `LLM_BACKEND` | `hybrid` | `local`, `cloud`, or `hybrid` |
| `OPENAI_API_KEY` | - | Required for cloud LLM |
| `ANTHROPIC_API_KEY` | - | Optional cloud LLM |
| `MAX_REASONING_STEPS` | `5` | Max multi-step task steps |
| `FAST_PATH_ENABLED` | `true` | Enable rule-based fast router |
| `SENTRY_DSN` | - | Error tracking DSN |

---

## Kubernetes Manifests

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: reasoning-engine
  namespace: agent-guru-prod
spec:
  replicas: 3
  selector:
    matchLabels:
      app: reasoning-engine
  template:
    metadata:
      labels:
        app: reasoning-engine
    spec:
      containers:
        - name: reasoning-engine
          image: your-registry.example.com/agent-guru-reasoning:v1.0.0
          ports:
            - containerPort: 8000
          resources:
            requests:
              cpu: 1000m
              memory: 2Gi
            limits:
              cpu: 2000m
              memory: 4Gi
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 10
          envFrom:
            - secretRef:
                name: reasoning-engine-secrets
```

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: reasoning-engine-hpa
  namespace: agent-guru-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: reasoning-engine
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

---

## Scaling

### Manual Scaling

```bash
# Scale up for anticipated traffic
kubectl scale deployment/reasoning-engine --replicas=10 -n agent-guru-prod

# Scale down during low traffic
kubectl scale deployment/reasoning-engine --replicas=3 -n agent-guru-prod
```

### Check Autoscaler Status

```bash
kubectl get hpa -n agent-guru-prod
kubectl describe hpa reasoning-engine-hpa -n agent-guru-prod
```

---

## Rollback

### Helm Rollback

```bash
# List release history
helm history reasoning-engine -n agent-guru-prod

# Rollback to previous version
helm rollback reasoning-engine -n agent-guru-prod

# Rollback to specific revision
helm rollback reasoning-engine 3 -n agent-guru-prod
```

### Image Rollback

```bash
kubectl set image deployment/reasoning-engine \
  reasoning-engine=your-registry.example.com/agent-guru-reasoning:v0.9.0 \
  -n agent-guru-prod

kubectl rollout status deployment/reasoning-engine -n agent-guru-prod
```

### Emergency Stop

```bash
# Scale to zero immediately
kubectl scale deployment/reasoning-engine --replicas=0 -n agent-guru-prod

# Restore after fix
kubectl scale deployment/reasoning-engine --replicas=3 -n agent-guru-prod
```

---

## Post-Deployment Validation

```bash
# 1. Check pods are running
kubectl get pods -n agent-guru-prod

# 2. Check logs for errors
kubectl logs deployment/reasoning-engine -n agent-guru-prod --tail=50

# 3. Test health endpoint
curl -f https://api.agent-guru.com/health

# 4. Test API endpoint
curl -X POST https://api.agent-guru.com/v1/process \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"text": "set a timer for 1 minute", "user_id": "smoke-test"}'

# 5. Check metrics are flowing
curl https://api.agent-guru.com/metrics | grep reasoning_requests_total
```

---

## Related Documentation

- [Full Deployment Guide](./DEPLOYMENT_GUIDE.md) - Terraform infrastructure setup
- [Operations Runbook](./operations_runbook.md) - Day-to-day operations
- [API Reference](./api_reference.md) - API documentation
