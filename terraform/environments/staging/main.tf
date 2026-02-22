# Staging Environment Configuration
# Optimized for cost with reduced redundancy

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

# Networking
module "networking" {
  source = "../../modules/networking"

  cloud_provider     = "aws"
  project_name       = var.project_name
  cluster_name       = "${var.project_name}-${var.environment}"
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  enable_nat_gateway = true
  enable_flow_logs   = false  # Disabled for cost savings in staging

  tags = merge(
    var.tags,
    {
      Environment = var.environment
    }
  )
}

# Kubernetes Cluster
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
  enable_autoscaling   = var.enable_autoscaling
  enable_public_access = true

  tags = merge(
    var.tags,
    {
      Environment = var.environment
    }
  )

  depends_on = [module.networking]
}

# PostgreSQL Database
module "database" {
  source = "../../modules/database"

  cloud_provider          = "aws"
  environment             = var.environment
  db_name                 = "${replace(var.project_name, "-", "")}${var.environment}"
  db_instance_class       = var.db_instance_class
  db_allocated_storage    = var.db_allocated_storage
  db_engine_version       = var.db_engine_version
  multi_az                = false  # Single-AZ for staging
  backup_retention_days   = 7      # Reduced retention for staging
  enable_encryption       = true
  vpc_id                  = module.networking.vpc_id
  subnet_ids              = module.networking.private_subnet_ids
  allowed_security_groups = [module.kubernetes.cluster_security_group_id]
  create_read_replica     = false  # No read replica in staging

  tags = merge(
    var.tags,
    {
      Environment = var.environment
    }
  )

  depends_on = [module.networking, module.kubernetes]
}

# Redis Cluster
module "redis" {
  source = "../../modules/redis"

  cloud_provider          = "aws"
  environment             = var.environment
  cluster_id              = "${var.project_name}-${var.environment}-redis"
  redis_node_type         = var.redis_node_type
  num_cache_nodes         = 2  # Reduced for staging
  redis_engine_version    = var.redis_engine_version
  parameter_group_family  = var.redis_parameter_group_family
  multi_az                = false  # Single-AZ for staging
  snapshot_retention_limit = 3     # Reduced retention for staging
  enable_encryption       = true
  vpc_id                  = module.networking.vpc_id
  subnet_ids              = module.networking.private_subnet_ids
  allowed_security_groups = [module.kubernetes.cluster_security_group_id]

  tags = merge(
    var.tags,
    {
      Environment = var.environment
    }
  )

  depends_on = [module.networking, module.kubernetes]
}

# Monitoring (optional for staging)
module "monitoring" {
  count = var.enable_monitoring ? 1 : 0

  source = "../../modules/monitoring"

  namespace                = "monitoring"
  prometheus_retention_days = 7  # Reduced retention for staging
  prometheus_storage_size  = "20Gi"  # Reduced storage for staging
  grafana_admin_password   = var.grafana_admin_password
  enable_alertmanager      = false  # Disabled for staging

  tags = merge(
    var.tags,
    {
      Environment = var.environment
    }
  )

  depends_on = [module.kubernetes]
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
