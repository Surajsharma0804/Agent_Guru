# Agent Guru - Infrastructure Deployment Guide

This guide walks you through deploying the Agent Guru Core Reasoning Engine infrastructure using Terraform.

## Prerequisites

Before you begin, ensure you have:

1. **Terraform** installed (>= 1.5.0)
2. **AWS CLI** configured with appropriate credentials
3. **kubectl** installed for Kubernetes management
4. **Helm** installed for Kubernetes package management

## Step-by-Step Deployment

### Step 1: Configure AWS Credentials

```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and default region
```

### Step 2: Choose Environment

Navigate to the appropriate environment directory:

```bash
# For staging
cd terraform/environments/staging

# For production
cd terraform/environments/production
```

### Step 3: Create Configuration File

Copy the example configuration and customize it:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and set:
- `grafana_admin_password`: Strong password for Grafana admin
- `alert_webhook_url`: Slack/PagerDuty webhook URL (production only)
- `alert_emails`: Email addresses for alerts (production only)
- Other values as needed

### Step 4: Initialize Terraform

```bash
terraform init
```

This will:
- Download required provider plugins
- Initialize the backend
- Prepare modules

### Step 5: Review the Plan

```bash
terraform plan
```

Review the resources that will be created. Expected resources:
- **Staging**: ~40-50 resources
- **Production**: ~60-70 resources

### Step 6: Apply the Configuration

```bash
terraform apply
```

Type `yes` when prompted to confirm.

**Deployment Time**:
- Staging: ~15-20 minutes
- Production: ~20-30 minutes

### Step 7: Configure kubectl

After deployment completes, configure kubectl to access the cluster:

```bash
# Get the command from Terraform output
terraform output kubeconfig_command

# Run the command (example)
aws eks update-kubeconfig --region us-east-1 --name agent-guru-staging
```

Verify cluster access:

```bash
kubectl get nodes
kubectl get pods --all-namespaces
```

### Step 8: Verify Monitoring Stack

Check that monitoring components are running:

```bash
kubectl get pods -n monitoring
```

Expected pods:
- prometheus-*
- grafana-*
- jaeger-*
- alertmanager-* (production only)

### Step 9: Access Grafana

Get the Grafana external IP:

```bash
kubectl get svc -n monitoring grafana
```

Access Grafana:
- URL: `http://<EXTERNAL-IP>`
- Username: `admin`
- Password: (from terraform.tfvars)

### Step 10: Get Connection Strings

Retrieve database and Redis connection strings:

```bash
# Database connection string
terraform output -raw db_connection_string

# Redis connection string
terraform output -raw redis_connection_string
```

**Important**: Store these securely in your secrets management system.

## Post-Deployment Configuration

### Configure Application Secrets

Create Kubernetes secrets for the application:

```bash
# Database credentials
kubectl create secret generic db-credentials \
  --from-literal=connection-string="$(terraform output -raw db_connection_string)" \
  -n default

# Redis credentials
kubectl create secret generic redis-credentials \
  --from-literal=connection-string="$(terraform output -raw redis_connection_string)" \
  -n default
```

### Deploy Application

Deploy the Agent Guru application using the existing Kubernetes manifests:

```bash
cd ../../../k8s
kubectl apply -f base/
kubectl apply -f staging/  # or production/
```

### Verify Application

Check application pods:

```bash
kubectl get pods -n default
kubectl logs -f <pod-name>
```

### Configure Monitoring

Import Grafana dashboards:

```bash
# Copy dashboard JSON to Grafana
kubectl cp terraform/modules/monitoring/dashboards/reasoning-engine-dashboard.json \
  monitoring/<grafana-pod>:/tmp/

# Import via Grafana UI or API
```

Configure Prometheus alerts:

```bash
kubectl create configmap prometheus-alerts \
  --from-file=terraform/modules/monitoring/alerts/reasoning-engine-alerts.yaml \
  -n monitoring
```

## Environment-Specific Notes

### Staging Environment

**Cost Optimization**:
- Single-AZ deployment
- Smaller instance sizes
- Reduced backup retention (7 days)
- No read replicas
- Optional monitoring stack

**Estimated Monthly Cost**: $200-300

**Use Cases**:
- Development testing
- Integration testing
- Pre-production validation

### Production Environment

**High Availability**:
- Multi-AZ deployment (3 AZs)
- Auto-scaling enabled
- Read replicas for database
- 30-day backup retention
- Full monitoring stack with alerting

**Estimated Monthly Cost**: $800-1200

**Features**:
- 99.9% uptime SLA
- Automatic failover
- Enhanced security
- Comprehensive monitoring

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Latency**:
   - P95 latency per stage
   - End-to-end response time
   - LLM response time

2. **Errors**:
   - Error rate by type
   - Timeout rate
   - Degraded mode usage

3. **Resources**:
   - CPU and memory usage
   - Database connections
   - Redis memory usage

4. **Business Metrics**:
   - Request rate
   - Intent accuracy
   - Active conversations

### Alert Channels

**Staging**:
- Email notifications (optional)

**Production**:
- Slack webhook
- Email notifications
- PagerDuty (optional)

### Alert Severity Levels

- **Critical**: Immediate action required (P95 latency >6s, error rate >10%)
- **Warning**: Investigation needed (P95 latency >3s, error rate >5%)
- **Info**: Informational only

## Backup and Recovery

### Automated Backups

**Database**:
- Staging: Daily backups, 7-day retention
- Production: Daily backups, 30-day retention
- Point-in-time recovery enabled

**Redis**:
- Staging: Snapshots every 6 hours, 3-day retention
- Production: Snapshots every 6 hours, 7-day retention

### Manual Backup

Create a manual database snapshot:

```bash
aws rds create-db-snapshot \
  --db-instance-identifier agent-guru-production \
  --db-snapshot-identifier manual-backup-$(date +%Y%m%d)
```

### Disaster Recovery

**RTO** (Recovery Time Objective): < 1 hour
**RPO** (Recovery Point Objective): < 15 minutes

Recovery steps:
1. Restore database from latest snapshot
2. Recreate cluster from Terraform configuration
3. Redeploy application from CI/CD
4. Verify functionality

## Scaling

### Manual Scaling

Scale Kubernetes nodes:

```bash
# Update terraform.tfvars
node_count = 5

# Apply changes
terraform apply
```

### Auto-Scaling

Auto-scaling is enabled by default in production:
- Minimum nodes: 2
- Maximum nodes: 10
- Scale up: CPU >70% for 5 minutes
- Scale down: CPU <30% for 10 minutes

## Maintenance

### Regular Tasks

**Weekly**:
- Review monitoring dashboards
- Check for security updates
- Review cost reports

**Monthly**:
- Update Terraform modules
- Review and optimize costs
- Test disaster recovery procedures

**Quarterly**:
- Update Kubernetes version
- Update database engine version
- Security audit

### Upgrade Procedures

1. Test in staging first
2. Create backup before production upgrade
3. Apply during maintenance window
4. Monitor for issues
5. Rollback if necessary

## Troubleshooting

### Common Issues

**Issue**: Terraform apply fails with authentication error
```bash
# Solution: Verify AWS credentials
aws sts get-caller-identity
```

**Issue**: Kubernetes nodes not joining cluster
```bash
# Solution: Check security groups
aws ec2 describe-security-groups --group-ids <sg-id>
```

**Issue**: Database connection timeout
```bash
# Solution: Verify security group rules
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- \
  psql "$(terraform output -raw db_connection_string)"
```

**Issue**: Monitoring stack not starting
```bash
# Solution: Check pod logs
kubectl logs -n monitoring <pod-name>
kubectl describe pod -n monitoring <pod-name>
```

### Getting Help

1. Check Terraform documentation: https://www.terraform.io/docs
2. Check AWS documentation: https://docs.aws.amazon.com
3. Check Kubernetes documentation: https://kubernetes.io/docs
4. Contact DevOps team

## Cleanup

To destroy all resources (use with caution):

```bash
terraform destroy
```

**Warning**: This will delete all data. Ensure you have backups before proceeding.

## Security Best Practices

1. **Secrets Management**:
   - Never commit terraform.tfvars to version control
   - Use AWS Secrets Manager for sensitive data
   - Rotate credentials regularly

2. **Network Security**:
   - Use private subnets for databases
   - Restrict security group rules
   - Enable VPC flow logs

3. **Access Control**:
   - Use IAM roles and policies
   - Enable MFA for admin access
   - Follow least privilege principle

4. **Encryption**:
   - Enable encryption at rest (enabled by default)
   - Use TLS 1.3 for data in transit
   - Rotate encryption keys annually

## Cost Optimization

### Staging

- Use spot instances for non-critical workloads
- Stop environment during off-hours
- Use smaller instance sizes
- Reduce backup retention

### Production

- Use reserved instances for predictable workloads
- Enable auto-scaling
- Monitor and optimize resource usage
- Use cost allocation tags

## Support

For issues or questions:
- Email: devops@agent-guru.com
- Slack: #infrastructure
- On-call: PagerDuty

## License

Copyright © 2026 Agent Guru. All rights reserved.
