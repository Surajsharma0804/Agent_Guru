# Agent Guru - Infrastructure Summary

## Overview

Complete Terraform infrastructure for Agent Guru Core Reasoning Engine, providing production-ready deployment on AWS with high availability, auto-scaling, and comprehensive monitoring.

## What Was Created

### 1. Terraform Modules (Reusable Components)

#### Kubernetes Module (`modules/kubernetes/`)
- AWS EKS cluster with auto-scaling
- Node groups with launch templates
- IAM roles and policies
- OIDC provider for service accounts
- Security groups
- Cluster autoscaler support

#### Database Module (`modules/database/`)
- AWS RDS PostgreSQL with Multi-AZ support
- Automated backups (7-30 days retention)
- Read replicas for production
- Performance Insights enabled
- CloudWatch alarms (CPU, connections, storage)
- Secrets Manager integration
- Enhanced monitoring

#### Redis Module (`modules/redis/`)
- AWS ElastiCache Redis cluster
- Multi-AZ replication
- Automatic failover
- Encryption at rest and in transit
- CloudWatch alarms (CPU, memory, evictions)
- Snapshot backups
- Secrets Manager integration

#### Networking Module (`modules/networking/`)
- VPC with public and private subnets
- Multi-AZ deployment (2-3 AZs)
- NAT gateways for private subnet internet access
- Internet gateway for public subnets
- Route tables and associations
- VPC flow logs
- Network ACLs

#### Monitoring Module (`modules/monitoring/`)
- Prometheus for metrics collection
- Grafana for visualization
- Jaeger for distributed tracing
- AlertManager for alerting
- Pre-configured dashboards
- ServiceMonitor for application metrics

### 2. Environment Configurations

#### Staging Environment (`environments/staging/`)
**Purpose**: Development and testing
**Configuration**:
- 2 availability zones
- t3.medium nodes (2-5 nodes)
- db.t3.medium database (single-AZ)
- cache.t3.medium Redis (2 nodes)
- 7-day backup retention
- Optional monitoring
- **Estimated Cost**: $200-300/month

#### Production Environment (`environments/production/`)
**Purpose**: Production workloads
**Configuration**:
- 3 availability zones
- t3.xlarge nodes (2-10 nodes with auto-scaling)
- db.r6g.xlarge database (Multi-AZ with read replica)
- cache.r6g.xlarge Redis (3 nodes, Multi-AZ)
- 30-day backup retention
- Full monitoring with alerting
- KMS encryption
- SNS alerts
- **Estimated Cost**: $800-1200/month

### 3. Monitoring and Alerting

#### Grafana Dashboards
- Request rate and throughput
- P95 latency by stage
- Error rates by type
- Intent detection accuracy
- Active conversations
- LLM response times
- Resource utilization

#### Prometheus Alerts
- **Latency Alerts**: P95 >3s (warning), >6s (critical)
- **Error Rate Alerts**: >5% (warning), >10% (critical)
- **Intent Accuracy**: <95% (warning)
- **LLM Performance**: Response time >2s
- **Resource Alerts**: CPU/Memory >90%
- **Database Alerts**: Connection pool >80%
- **Redis Alerts**: Memory >90%, high eviction rate
- **Degraded Mode**: >10% of requests
- **Timeout Rate**: >5% of requests

### 4. Documentation

- **README.md**: Complete infrastructure overview
- **DEPLOYMENT_GUIDE.md**: Step-by-step deployment instructions
- **terraform.tfvars.example**: Configuration templates
- Module-specific documentation in each module

## Key Features

### High Availability
- Multi-AZ deployment for production
- Automatic failover for database and Redis
- Load balancing across availability zones
- No single point of failure

### Auto-Scaling
- Kubernetes cluster autoscaler
- Database storage auto-scaling
- Scales based on CPU/memory metrics
- Min/max node limits configurable

### Security
- Encryption at rest (KMS)
- Encryption in transit (TLS 1.3)
- Private subnets for databases
- Security groups with least privilege
- VPC flow logs for audit
- Secrets Manager for credentials
- IAM roles and policies

### Monitoring
- Prometheus metrics collection
- Grafana visualization
- Jaeger distributed tracing
- CloudWatch logs and alarms
- SNS notifications
- Webhook integration (Slack, PagerDuty)

### Backup and Recovery
- Automated daily backups
- Point-in-time recovery
- 7-30 day retention
- Manual snapshot support
- RTO <1 hour, RPO <15 minutes

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         Internet                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   Internet Gateway    │
              └──────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                  │
        ▼                                  ▼
┌──────────────┐                  ┌──────────────┐
│ Public Subnet│                  │ Public Subnet│
│   (AZ-1)     │                  │   (AZ-2)     │
│              │                  │              │
│ NAT Gateway  │                  │ NAT Gateway  │
└──────┬───────┘                  └──────┬───────┘
       │                                  │
       ▼                                  ▼
┌──────────────┐                  ┌──────────────┐
│Private Subnet│                  │Private Subnet│
│   (AZ-1)     │                  │   (AZ-2)     │
│              │                  │              │
│ EKS Nodes    │                  │ EKS Nodes    │
│ RDS Primary  │                  │ RDS Replica  │
│ Redis Node   │                  │ Redis Node   │
└──────────────┘                  └──────────────┘
```

## Resource Summary

### Staging Environment
- **Compute**: 2-5 Kubernetes nodes (t3.medium)
- **Database**: 1 RDS instance (db.t3.medium, 50GB)
- **Cache**: 2 Redis nodes (cache.t3.medium)
- **Networking**: VPC, 2 AZs, 2 NAT gateways
- **Monitoring**: Prometheus, Grafana, Jaeger
- **Total Resources**: ~40-50 AWS resources

### Production Environment
- **Compute**: 2-10 Kubernetes nodes (t3.xlarge)
- **Database**: 1 RDS primary + 1 read replica (db.r6g.xlarge, 100GB)
- **Cache**: 3 Redis nodes (cache.r6g.xlarge)
- **Networking**: VPC, 3 AZs, 3 NAT gateways
- **Monitoring**: Full stack with AlertManager
- **Security**: KMS keys, SNS topics
- **Total Resources**: ~60-70 AWS resources

## Performance Targets

### Latency
- P95 latency: <1.5s (target), <3s (warning), <6s (critical)
- LLM response: <2s
- Database queries: <100ms
- Redis operations: <10ms

### Throughput
- Requests per second: 1,000+ per instance
- Concurrent users: 10,000+ per cluster
- Database connections: 100+ per instance

### Availability
- Uptime: 99.9% (production)
- RTO: <1 hour
- RPO: <15 minutes

## Next Steps

1. **Deploy Staging**:
   ```bash
   cd terraform/environments/staging
   terraform init
   terraform apply
   ```

2. **Configure Application**:
   - Create Kubernetes secrets
   - Deploy application manifests
   - Configure monitoring

3. **Test and Validate**:
   - Run integration tests
   - Verify monitoring
   - Test failover scenarios

4. **Deploy Production**:
   - Review configuration
   - Apply Terraform
   - Configure alerting
   - Run smoke tests

## Maintenance

### Regular Tasks
- **Weekly**: Review dashboards, check alerts
- **Monthly**: Update modules, optimize costs
- **Quarterly**: Update Kubernetes, security audit

### Upgrades
1. Test in staging
2. Create backups
3. Apply during maintenance window
4. Monitor and verify
5. Rollback if needed

## Support

- Documentation: See README.md and DEPLOYMENT_GUIDE.md
- Issues: Contact DevOps team
- Emergency: PagerDuty on-call

## License

Copyright © 2026 Agent Guru. All rights reserved.
