# Core Reasoning Engine - Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the Agent Guru Core Reasoning Engine to production environments using Terraform for infrastructure provisioning and Kubernetes with Helm for application deployment.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Infrastructure Setup with Terraform](#infrastructure-setup-with-terraform)
3. [Kubernetes Deployment with Helm](#kubernetes-deployment-with-helm)
4. [Configuration Management](#configuration-management)
5. [Rollback Procedures](#rollback-procedures)
6. [Post-Deployment Validation](#post-deployment-validation)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools

- **Terraform** >= 1.5.0
- **kubectl** >= 1.27.0
- **Helm** >= 3.12.0
- **Docker** >= 24.0.0
- **AWS CLI** / **gcloud** / **az** (depending on cloud provider)

### Required Access

- Cloud provider credentials with appropriate permissions
- Container registry access (ECR, GCR, ACR, or Docker Hub)
- Kubernetes cluster admin access
- Secrets management access (AWS Secrets Manager, Vault, etc.)

### Environment Variables

```bash
# Cloud Provider (AWS example)
export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=123456789012

# Container Registry
export CONTAINER_REGISTRY=123456789012.dkr.ecr.us-west-2.amazonaws.com
export IMAGE_TAG=v1.0.0

# Kubernetes
export KUBECONFIG=~/.kube/config
export KUBE_NAMESPACE=agent-guru-prod

# Secrets
export SECRETS_BACKEND=aws-secrets-manager
```

## Infrastructure Setup with Terraform

### Step 1: Initialize Terraform

```bash
cd infrastructure/terraform

# Initialize Terraform with backend configuration
terraform init \
  -backend-config="bucket=agent-guru-terraform-state" \
  -backend-config="key=reasoning-engine/prod/terraform.tfstate" \
  -backend-config="region=us-west-2"
```

### Step 2: Review Infrastructure Plan

```bash
# Create and review execution plan
terraform plan \
  -var-file="environments/prod.tfvars" \
  -out=tfplan

# Review the plan carefully
# Verify:
# - Kubernetes cluster configuration (node count, instance types)
# - Database configuration (PostgreSQL instance size, backup settings)
# - Redis cluster configuration (node count, memory)
# - Network configuration (VPC, subnets, security groups)
# - Monitoring infrastructure (Prometheus, Grafana, Jaeger)
```

### Step 3: Apply Infrastructure Changes

```bash
# Apply the plan
terraform apply tfplan

# Wait for infrastructure provisioning (typically 15-20 minutes)
# Terraform will output important values:
# - Kubernetes cluster endpoint
# - Database connection strings
# - Redis endpoints
# - Load balancer DNS names
```

### Step 4: Configure kubectl

```bash
# AWS EKS example
aws eks update-kubeconfig \
  --region us-west-2 \
  --name agent-guru-prod-cluster

# Verify cluster access
kubectl cluster-info
kubectl get nodes
```

### Infrastructure Components

The Terraform configuration provisions:

1. **Kubernetes Cluster**
   - Multi-AZ deployment for high availability
   - Auto-scaling node groups (min: 3, max: 20)
   - Instance types: c5.2xlarge (8 vCPU, 16GB RAM)

2. **PostgreSQL Database**
   - Managed service (RDS/Cloud SQL/Azure Database)
   - Multi-AZ deployment with automatic failover
   - Daily backups with 30-day retention
   - Instance: db.r5.xlarge (4 vCPU, 32GB RAM)

3. **Redis Cluster**
   - Managed service (ElastiCache/Memorystore/Azure Cache)
   - Multi-AZ replication
   - Instance: cache.r5.large (2 vCPU, 13GB RAM)

4. **Networking**
   - VPC with public and private subnets
   - NAT gateways for outbound traffic
   - Security groups with least-privilege access
   - Application Load Balancer with TLS termination

5. **Monitoring Infrastructure**
   - Prometheus for metrics collection
   - Grafana for visualization
   - Jaeger for distributed tracing
   - CloudWatch/Stackdriver for logs

## Kubernetes Deployment with Helm

### Step 1: Build and Push Docker Images

```bash
# Build Docker image
docker build \
  -t ${CONTAINER_REGISTRY}/agent-guru-reasoning:${IMAGE_TAG} \
  -f Dockerfile \
  .

# Push to container registry
docker push ${CONTAINER_REGISTRY}/agent-guru-reasoning:${IMAGE_TAG}

# Tag as latest (optional)
docker tag \
  ${CONTAINER_REGISTRY}/agent-guru-reasoning:${IMAGE_TAG} \
  ${CONTAINER_REGISTRY}/agent-guru-reasoning:latest
docker push ${CONTAINER_REGISTRY}/agent-guru-reasoning:latest
```

### Step 2: Prepare Helm Values

Create `values-prod.yaml`:

```yaml
# values-prod.yaml
image:
  repository: 123456789012.dkr.ecr.us-west-2.amazonaws.com/agent-guru-reasoning
  tag: v1.0.0
  pullPolicy: IfNotPresent

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
  targetMemoryUtilizationPercentage: 80

service:
  type: ClusterIP
  port: 8000

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: api.agent-guru.com
      paths:
        - path: /v1/reasoning
          pathType: Prefix
  tls:
    - secretName: agent-guru-tls
      hosts:
        - api.agent-guru.com

env:
  - name: ENVIRONMENT
    value: production
  - name: LOG_LEVEL
    value: INFO
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

livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
```

### Step 3: Create Kubernetes Secrets

```bash
# Create namespace
kubectl create namespace ${KUBE_NAMESPACE}

# Create secrets from AWS Secrets Manager (example)
kubectl create secret generic reasoning-engine-secrets \
  --namespace=${KUBE_NAMESPACE} \
  --from-literal=database-url="$(aws secretsmanager get-secret-value --secret-id prod/reasoning-engine/database-url --query SecretString --output text)" \
  --from-literal=redis-url="$(aws secretsmanager get-secret-value --secret-id prod/reasoning-engine/redis-url --query SecretString --output text)" \
  --from-literal=openai-api-key="$(aws secretsmanager get-secret-value --secret-id prod/reasoning-engine/openai-api-key --query SecretString --output text)"
```

### Step 4: Deploy with Helm

```bash
# Add Helm repository (if using custom chart repo)
helm repo add agent-guru https://charts.agent-guru.com
helm repo update

# Install or upgrade the release
helm upgrade --install reasoning-engine agent-guru/reasoning-engine \
  --namespace=${KUBE_NAMESPACE} \
  --values=values-prod.yaml \
  --wait \
  --timeout=10m

# Verify deployment
kubectl get pods -n ${KUBE_NAMESPACE}
kubectl get svc -n ${KUBE_NAMESPACE}
kubectl get ingress -n ${KUBE_NAMESPACE}
```

### Step 5: Run Smoke Tests

```bash
# Get the service endpoint
ENDPOINT=$(kubectl get ingress reasoning-engine -n ${KUBE_NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

# Test health endpoint
curl -f https://${ENDPOINT}/health

# Test API endpoint
curl -X POST https://${ENDPOINT}/v1/reasoning/process \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -d '{
    "input": "set a timer for 5 minutes",
    "user_id": "test-user",
    "source": "text"
  }'
```

## Configuration Management

### Environment-Specific Configuration

Configuration is managed through Helm values files:

- `values-dev.yaml` - Development environment
- `values-staging.yaml` - Staging environment
- `values-prod.yaml` - Production environment

### Configuration Hierarchy

1. **Default values** - `values.yaml` in Helm chart
2. **Environment values** - `values-{env}.yaml`
3. **Secrets** - Kubernetes Secrets from secrets manager
4. **ConfigMaps** - For non-sensitive configuration

### Updating Configuration

```bash
# Update Helm values
vim values-prod.yaml

# Apply configuration changes
helm upgrade reasoning-engine agent-guru/reasoning-engine \
  --namespace=${KUBE_NAMESPACE} \
  --values=values-prod.yaml \
  --reuse-values

# Verify pods are updated
kubectl rollout status deployment/reasoning-engine -n ${KUBE_NAMESPACE}
```

### Secrets Rotation

```bash
# Update secret in secrets manager
aws secretsmanager update-secret \
  --secret-id prod/reasoning-engine/openai-api-key \
  --secret-string "new-api-key"

# Update Kubernetes secret
kubectl delete secret reasoning-engine-secrets -n ${KUBE_NAMESPACE}
kubectl create secret generic reasoning-engine-secrets \
  --namespace=${KUBE_NAMESPACE} \
  --from-literal=openai-api-key="new-api-key" \
  # ... other secrets

# Restart pods to pick up new secrets
kubectl rollout restart deployment/reasoning-engine -n ${KUBE_NAMESPACE}
```

## Rollback Procedures

### Helm Rollback

```bash
# List release history
helm history reasoning-engine -n ${KUBE_NAMESPACE}

# Rollback to previous version
helm rollback reasoning-engine -n ${KUBE_NAMESPACE}

# Rollback to specific revision
helm rollback reasoning-engine 5 -n ${KUBE_NAMESPACE}

# Verify rollback
kubectl rollout status deployment/reasoning-engine -n ${KUBE_NAMESPACE}
```

### Manual Rollback

```bash
# Rollback to previous image
kubectl set image deployment/reasoning-engine \
  reasoning-engine=${CONTAINER_REGISTRY}/agent-guru-reasoning:v0.9.0 \
  -n ${KUBE_NAMESPACE}

# Monitor rollback progress
kubectl rollout status deployment/reasoning-engine -n ${KUBE_NAMESPACE}

# Verify pods are healthy
kubectl get pods -n ${KUBE_NAMESPACE}
```

### Automatic Rollback Triggers

The deployment includes automatic rollback on:

1. **Health check failures** - If >50% of pods fail health checks
2. **Error rate spike** - If error rate >5% for 5 minutes
3. **Latency degradation** - If P95 latency >2x baseline for 5 minutes

Automatic rollback is handled by the CI/CD pipeline and monitoring alerts.

### Emergency Rollback

```bash
# Scale down to zero (emergency stop)
kubectl scale deployment/reasoning-engine --replicas=0 -n ${KUBE_NAMESPACE}

# Rollback to last known good version
helm rollback reasoning-engine -n ${KUBE_NAMESPACE}

# Scale back up
kubectl scale deployment/reasoning-engine --replicas=3 -n ${KUBE_NAMESPACE}
```

## Post-Deployment Validation

### Health Checks

```bash
# Check pod status
kubectl get pods -n ${KUBE_NAMESPACE}

# Check pod logs
kubectl logs -f deployment/reasoning-engine -n ${KUBE_NAMESPACE}

# Check events
kubectl get events -n ${KUBE_NAMESPACE} --sort-by='.lastTimestamp'
```

### Functional Tests

```bash
# Run smoke tests
./scripts/smoke-tests.sh ${ENDPOINT}

# Run integration tests
pytest tests/integration/ --endpoint=${ENDPOINT}
```

### Performance Validation

```bash
# Check latency metrics
curl https://${ENDPOINT}/metrics | grep reasoning_latency

# Run load test (light)
locust -f tests/load/locustfile.py \
  --host=https://${ENDPOINT} \
  --users=10 \
  --spawn-rate=1 \
  --run-time=5m \
  --headless
```

### Monitoring Validation

1. **Grafana Dashboards** - Verify metrics are flowing
   - Navigate to https://grafana.agent-guru.com
   - Check "Reasoning Engine - Production" dashboard
   - Verify latency, throughput, error rate metrics

2. **Prometheus Alerts** - Verify alerting is active
   - Navigate to https://prometheus.agent-guru.com
   - Check alert rules are loaded
   - Verify no firing alerts

3. **Jaeger Tracing** - Verify traces are collected
   - Navigate to https://jaeger.agent-guru.com
   - Search for recent traces
   - Verify end-to-end trace visibility

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n ${KUBE_NAMESPACE}

# Common issues:
# - Image pull errors: Check registry credentials
# - Resource limits: Check node capacity
# - Config errors: Check environment variables and secrets
```

### High Error Rate

```bash
# Check application logs
kubectl logs deployment/reasoning-engine -n ${KUBE_NAMESPACE} | grep ERROR

# Check external dependencies
# - Database connectivity
# - Redis connectivity
# - LLM API availability
```

### Performance Issues

```bash
# Check resource utilization
kubectl top pods -n ${KUBE_NAMESPACE}
kubectl top nodes

# Check HPA status
kubectl get hpa -n ${KUBE_NAMESPACE}

# Scale manually if needed
kubectl scale deployment/reasoning-engine --replicas=10 -n ${KUBE_NAMESPACE}
```

### Database Connection Issues

```bash
# Test database connectivity from pod
kubectl exec -it deployment/reasoning-engine -n ${KUBE_NAMESPACE} -- \
  psql ${DATABASE_URL} -c "SELECT 1"

# Check database status in cloud console
# Verify security group rules allow connections
```

## Support and Escalation

For deployment issues:

1. Check this guide and operations runbook
2. Review monitoring dashboards and logs
3. Contact DevOps team: devops@agent-guru.com
4. Escalate to on-call engineer: PagerDuty

## References

- [Operations Runbook](./OPERATIONS_RUNBOOK.md)
- [API Documentation](./API_DOCUMENTATION.md)
- [Architecture Overview](../design.md)
- [Terraform Documentation](https://www.terraform.io/docs)
- [Helm Documentation](https://helm.sh/docs)
- [Kubernetes Documentation](https://kubernetes.io/docs)
