# Production Environment Configuration
# Multi-AZ deployment with high availability and auto-scaling

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }
}

provider "aws" {
  region = var.region
}

# Networking with Multi-AZ
module "networking" {
  source = "../../modules/networking"

  cloud_provider     = "aws"
  project_name       = var.project_name
  cluster_name       = "${var.project_name}-${var.environment}"
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  enable_nat_gateway = true
  enable_flow_logs   = true  # Enabled for production security

  tags = merge(
    var.tags,
    {
      Environment = var.environment
    }
  )
}

# Kubernetes Cluster with Auto-scaling
module "kubernetes" {
  source = "../../modules/kubernetes"

  cloud_provider       = "aws"
  cluster_name         = "${var.project_name}-${var.environment}"
  kubernetes_version   = var.kubernetes_version
  vpc_id               = module.networking.vpc_id
  subnet_ids           = module.networking.private_subnet_ids
  node_instance_type   = var.node_instance_type
  node_count           = var.node_count
  min_nodes            = var.min_nodes
  max_nodes            = var.max_nodes
  enable_autoscaling   = true
  enable_public_access = false  # Private API for production

  tags = merge(
    var.tags,
    {
      Environment = var.environment
    }
  )

  depends_on = [module.networking]
}

# PostgreSQL Database with Multi-AZ and Read Replica
module "database" {
  source = "../../modules/database"

  cloud_provider          = "aws"
  environment             = var.environment
  db_name                 = "${replace(var.project_name, "-", "")}${var.environment}"
  db_instance_class       = var.db_instance_class
  db_allocated_storage    = var.db_allocated_storage
  db_engine_version       = var.db_engine_version
  multi_az                = true  # Multi-AZ for production
  backup_retention_days   = 30    # 30-day retention for production
  enable_encryption       = true
  vpc_id                  = module.networking.vpc_id
  subnet_ids              = module.networking.private_subnet_ids
  allowed_security_groups = [module.kubernetes.cluster_security_group_id]
  create_read_replica     = true  # Read replica for production

  tags = merge(
    var.tags,
    {
      Environment = var.environment
    }
  )

  depends_on = [module.networking, module.kubernetes]
}

# Redis Cluster with Multi-AZ
module "redis" {
  source = "../../modules/redis"

  cloud_provider           = "aws"
  environment              = var.environment
  cluster_id               = "${var.project_name}-${var.environment}-redis"
  redis_node_type          = var.redis_node_type
  num_cache_nodes          = 3  # 3 nodes for production
  redis_engine_version     = var.redis_engine_version
  parameter_group_family   = var.redis_parameter_group_family
  multi_az                 = true  # Multi-AZ for production
  snapshot_retention_limit = 7     # 7-day retention for production
  enable_encryption        = true
  vpc_id                   = module.networking.vpc_id
  subnet_ids               = module.networking.private_subnet_ids
  allowed_security_groups  = [module.kubernetes.cluster_security_group_id]

  tags = merge(
    var.tags,
    {
      Environment = var.environment
    }
  )

  depends_on = [module.networking, module.kubernetes]
}

# Monitoring Stack (Required for production)
module "monitoring" {
  source = "../../modules/monitoring"

  namespace                 = "monitoring"
  prometheus_retention_days = 15  # 15-day retention for production
  prometheus_storage_size   = "50Gi"
  grafana_admin_password    = var.grafana_admin_password
  enable_alertmanager       = true
  alert_webhook_url         = var.alert_webhook_url

  tags = merge(
    var.tags,
    {
      Environment = var.environment
    }
  )

  depends_on = [module.kubernetes]
}

# SNS Topic for Alerts
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-${var.environment}-alerts"

  tags = merge(
    var.tags,
    {
      Environment = var.environment
    }
  )
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count = length(var.alert_emails)

  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_emails[count.index]
}

# KMS Key for Encryption
resource "aws_kms_key" "main" {
  description             = "KMS key for ${var.project_name} ${var.environment}"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(
    var.tags,
    {
      Environment = var.environment
    }
  )
}

resource "aws_kms_alias" "main" {
  name          = "alias/${var.project_name}-${var.environment}"
  target_key_id = aws_kms_key.main.key_id
}

# Configure kubectl
provider "kubernetes" {
  host                   = module.kubernetes.cluster_endpoint
  cluster_ca_certificate = module.kubernetes.cluster_ca_certificate
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args = [
      "eks",
      "get-token",
      "--cluster-name",
      module.kubernetes.cluster_name
    ]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.kubernetes.cluster_endpoint
    cluster_ca_certificate = module.kubernetes.cluster_ca_certificate
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args = [
        "eks",
        "get-token",
        "--cluster-name",
        module.kubernetes.cluster_name
      ]
    }
  }
}
