# Global Terraform Variables
# These variables are used across all modules

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "agent-guru"
}

variable "environment" {
  description = "Environment name (staging, production)"
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be either 'staging' or 'production'."
  }
}

variable "region" {
  description = "Cloud provider region"
  type        = string
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "Agent Guru"
    Component   = "Core Reasoning Engine"
    ManagedBy   = "Terraform"
  }
}

# Networking Variables
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "enable_nat_gateway" {
  description = "Enable NAT gateway for private subnets"
  type        = bool
  default     = true
}

variable "enable_vpn_gateway" {
  description = "Enable VPN gateway"
  type        = bool
  default     = false
}

# Kubernetes Variables
variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.28"
}

variable "node_instance_type" {
  description = "Instance type for Kubernetes nodes"
  type        = string
}

variable "node_count" {
  description = "Initial number of nodes"
  type        = number
  default     = 3
}

variable "min_nodes" {
  description = "Minimum number of nodes for autoscaling"
  type        = number
  default     = 2
}

variable "max_nodes" {
  description = "Maximum number of nodes for autoscaling"
  type        = number
  default     = 10
}

# Database Variables
variable "db_instance_class" {
  description = "Database instance class"
  type        = string
}

variable "db_allocated_storage" {
  description = "Allocated storage for database (GB)"
  type        = number
  default     = 100
}

variable "db_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "15.4"
}

variable "db_multi_az" {
  description = "Enable multi-AZ deployment for database"
  type        = bool
}

variable "db_backup_retention_days" {
  description = "Number of days to retain database backups"
  type        = number
  default     = 30
}

variable "db_backup_window" {
  description = "Preferred backup window"
  type        = string
  default     = "03:00-04:00"
}

variable "db_maintenance_window" {
  description = "Preferred maintenance window"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

# Redis Variables
variable "redis_node_type" {
  description = "Redis node instance type"
  type        = string
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes in Redis cluster"
  type        = number
  default     = 3
}

variable "redis_engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"
}

variable "redis_parameter_group_family" {
  description = "Redis parameter group family"
  type        = string
  default     = "redis7"
}

variable "redis_snapshot_retention_limit" {
  description = "Number of days to retain Redis snapshots"
  type        = number
  default     = 7
}

# Monitoring Variables
variable "enable_monitoring" {
  description = "Enable monitoring infrastructure (Prometheus, Grafana, Jaeger)"
  type        = bool
  default     = true
}

variable "prometheus_retention_days" {
  description = "Prometheus metrics retention period (days)"
  type        = number
  default     = 15
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true
}

# Security Variables
variable "enable_encryption" {
  description = "Enable encryption at rest for all data stores"
  type        = bool
  default     = true
}

variable "ssl_certificate_arn" {
  description = "ARN of SSL certificate for load balancer"
  type        = string
  default     = ""
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access the infrastructure"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# Cost Optimization Variables
variable "enable_spot_instances" {
  description = "Enable spot instances for Kubernetes nodes (cost optimization)"
  type        = bool
  default     = false
}

variable "enable_autoscaling" {
  description = "Enable autoscaling for Kubernetes cluster"
  type        = bool
  default     = true
}
