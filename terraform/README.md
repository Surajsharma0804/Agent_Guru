# Agent Guru - Terraform Infrastructure

This directory contains Terraform configurations for deploying Agent Guru's Core Reasoning Engine infrastructure.

## Architecture Overview

The infrastructure consists of:
- **Kubernetes Cluster**: EKS (AWS), GKE (Google Cloud), or AKS (Azure)
- **PostgreSQL Database**: Managed database service for conversation state and persistence
- **Redis Cluster**: Managed Redis for caching and session management
- **Load Balancer**: Application load balancer with SSL termination
- **Networking**: VPC, subnets, security groups, and firewall rules
- **Monitoring**: Prometheus, Grafana, and Jaeger for observability

## Directory Structure

```
terraform/
├── modules/              # Reusable Terraform modules
│   ├── kubernetes/       # Kubernetes cluster module
│   ├── database/         # PostgreSQL database module
│   ├── redis/            # Redis cluster module
│   ├── networking/       # VPC and networking module
│   └── monitoring/       # Monitoring infrastructure module
├── environments/         # Environment-specific configurations
│   ├── staging/          # Staging environment
│   └── production/       # Production environment
├── backend.tf            # Terraform backend configuration
├── variables.tf          # Global variables
└── README.md             # This file
```

## Prerequisites

1. **Terraform**: Install Terraform >= 1.5.0
   ```bash
   # macOS
   brew install terraform
   
   # Windows
   choco install terraform
   
   # Linux
   wget https://releases.hashicorp.com/terraform/1.5.0/terraform_1.5.0_linux_amd64.zip
   unzip terraform_1.5.0_linux_amd64.zip
   sudo mv terraform /usr/local/bin/
   ```

2. **Cloud Provider CLI**:
   - AWS: `aws configure`
   - Google Cloud: `gcloud auth login`
   - Azure: `az login`

3. **kubectl**: For Kubernetes management
   ```bash
   # macOS
   brew install kubectl
   
   # Windows
   choco install kubernetes-cli
   
   # Linux
   curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
   sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
   ```

## Quick Start

### 1. Initialize Terraform

```bash
cd terraform/environments/staging
terraform init
```

### 2. Review the Plan

```bash
terraform plan
```

### 3. Apply the Configuration

```bash
terraform apply
```

### 4. Get Outputs

```bash
terraform output
```

## Environment Configuration

### Staging Environment

Located in `environments/staging/`:
- Smaller instance sizes for cost optimization
- Single-AZ deployment
- Reduced redundancy
- Suitable for testing and development

### Production Environment

Located in `environments/production/`:
- Multi-AZ deployment for high availability
- Auto-scaling enabled
- Daily backups with 30-day retention
- Enhanced security and monitoring

## Module Documentation

### Kubernetes Module

Creates a managed Kubernetes cluster with:
- Node pools with auto-scaling
- Network policies
- RBAC configuration
- Cluster autoscaler

**Inputs**:
- `cluster_name`: Name of the Kubernetes cluster
- `node_count`: Initial number of nodes
- `node_instance_type`: Instance type for nodes
- `min_nodes`: Minimum nodes for autoscaling
- `max_nodes`: Maximum nodes for autoscaling

**Outputs**:
- `cluster_endpoint`: Kubernetes API endpoint
- `cluster_ca_certificate`: Cluster CA certificate
- `kubeconfig`: Kubeconfig for cluster access

### Database Module

Creates a managed PostgreSQL database with:
- Multi-AZ deployment (production)
- Automated backups
- Point-in-time recovery
- Encryption at rest

**Inputs**:
- `db_name`: Database name
- `db_instance_class`: Instance class (e.g., db.t3.medium)
- `db_allocated_storage`: Storage size in GB
- `multi_az`: Enable multi-AZ deployment
- `backup_retention_days`: Backup retention period

**Outputs**:
- `db_endpoint`: Database connection endpoint
- `db_port`: Database port
- `db_name`: Database name

### Redis Module

Creates a managed Redis cluster with:
- Cluster mode enabled
- Automatic failover
- Encryption in transit
- Multi-AZ replication

**Inputs**:
- `cluster_id`: Redis cluster identifier
- `node_type`: Node instance type
- `num_cache_nodes`: Number of cache nodes
- `parameter_group_family`: Redis parameter group

**Outputs**:
- `redis_endpoint`: Redis connection endpoint
- `redis_port`: Redis port
- `redis_configuration_endpoint`: Configuration endpoint

### Networking Module

Creates VPC and networking infrastructure:
- VPC with public and private subnets
- NAT gateways for private subnet internet access
- Security groups and network ACLs
- VPC peering (if needed)

**Inputs**:
- `vpc_cidr`: VPC CIDR block
- `availability_zones`: List of AZs
- `public_subnet_cidrs`: Public subnet CIDR blocks
- `private_subnet_cidrs`: Private subnet CIDR blocks

**Outputs**:
- `vpc_id`: VPC identifier
- `public_subnet_ids`: Public subnet IDs
- `private_subnet_ids`: Private subnet IDs
- `nat_gateway_ids`: NAT gateway IDs

### Monitoring Module

Creates monitoring infrastructure:
- Prometheus for metrics collection
- Grafana for visualization
- Jaeger for distributed tracing
- AlertManager for alerting

**Inputs**:
- `namespace`: Kubernetes namespace for monitoring
- `prometheus_retention`: Metrics retention period
- `grafana_admin_password`: Grafana admin password

**Outputs**:
- `prometheus_endpoint`: Prometheus endpoint
- `grafana_endpoint`: Grafana endpoint
- `jaeger_endpoint`: Jaeger endpoint

## Cost Optimization

### Staging Environment
- Estimated cost: $200-300/month
- Single-AZ deployment
- Smaller instance sizes
- Reduced backup retention

### Production Environment
- Estimated cost: $800-1200/month
- Multi-AZ deployment
- Auto-scaling enabled
- 30-day backup retention
- Enhanced monitoring

## Security Best Practices

1. **Secrets Management**:
   - Use AWS Secrets Manager, Google Secret Manager, or Azure Key Vault
   - Never commit secrets to version control
   - Rotate secrets regularly

2. **Network Security**:
   - Use private subnets for databases and Redis
   - Restrict security group rules to minimum required
   - Enable VPC flow logs

3. **Access Control**:
   - Use IAM roles and service accounts
   - Enable MFA for admin access
   - Implement least privilege principle

4. **Encryption**:
   - Enable encryption at rest for all data stores
   - Use TLS 1.3 for data in transit
   - Rotate encryption keys regularly

## Disaster Recovery

### Backup Strategy
- **Database**: Daily automated backups with 30-day retention
- **Redis**: AOF persistence enabled
- **Kubernetes**: Velero for cluster backups
- **Configuration**: Terraform state in S3/GCS with versioning

### Recovery Procedures
1. **Database Recovery**: Restore from automated backup or point-in-time
2. **Cluster Recovery**: Recreate cluster from Terraform configuration
3. **Application Recovery**: Redeploy from CI/CD pipeline

### RTO and RPO Targets
- **RTO** (Recovery Time Objective): < 1 hour
- **RPO** (Recovery Point Objective): < 15 minutes

## Monitoring and Alerting

### Key Metrics
- Cluster CPU and memory utilization
- Database connections and query performance
- Redis hit rate and memory usage
- Application latency and error rates

### Alerts
- P95 latency > 2x target
- Error rate > 5%
- Database connections > 80% of max
- Redis memory > 90% of max
- Node CPU > 90%

## Maintenance

### Regular Tasks
- **Weekly**: Review monitoring dashboards and alerts
- **Monthly**: Review and optimize costs
- **Quarterly**: Update Terraform modules and providers
- **Annually**: Disaster recovery drill

### Upgrade Procedures
1. Test upgrades in staging environment
2. Create backup before production upgrade
3. Apply upgrades during maintenance window
4. Monitor for issues post-upgrade
5. Rollback if necessary

## Troubleshooting

### Common Issues

**Issue**: Terraform apply fails with authentication error
**Solution**: Verify cloud provider credentials are configured correctly

**Issue**: Kubernetes nodes not joining cluster
**Solution**: Check security group rules allow node-to-control-plane communication

**Issue**: Database connection timeout
**Solution**: Verify security group allows traffic from Kubernetes nodes

**Issue**: Redis connection refused
**Solution**: Check Redis is in same VPC and security groups allow traffic

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Terraform documentation: https://www.terraform.io/docs
3. Check cloud provider documentation
4. Contact DevOps team

## License

Copyright © 2026 Agent Guru. All rights reserved.
