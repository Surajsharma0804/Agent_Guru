# Staging Environment Variables

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "agent-guru"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "staging"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.28"
}

variable "node_instance_type" {
  description = "Node instance type"
  type        = string
  default     = "t3.medium"  # Smaller for staging
}

variable "node_count" {
  description = "Initial node count"
  type        = number
  default     = 2
}

variable "min_nodes" {
  description = "Minimum nodes"
  type        = number
  default     = 1
}

variable "max_nodes" {
  description = "Maximum nodes"
  type        = number
  default     = 5
}

variable "enable_autoscaling" {
  description = "Enable autoscaling"
  type        = bool
  default     = true
}

variable "db_instance_class" {
  description = "Database instance class"
  type        = string
  default     = "db.t3.medium"  # Smaller for staging
}

variable "db_allocated_storage" {
  description = "Database storage (GB)"
  type        = number
  default     = 50  # Reduced for staging
}

variable "db_engine_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15.4"
}

variable "redis_node_type" {
  description = "Redis node type"
  type        = string
  default     = "cache.t3.medium"  # Smaller for staging
}

variable "redis_engine_version" {
  description = "Redis version"
  type        = string
  default     = "7.0"
}

variable "redis_parameter_group_family" {
  description = "Redis parameter group family"
  type        = string
  default     = "redis7"
}

variable "enable_monitoring" {
  description = "Enable monitoring stack"
  type        = bool
  default     = true
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Common tags"
  type        = map(string)
  default = {
    Project     = "Agent Guru"
    Component   = "Core Reasoning Engine"
    ManagedBy   = "Terraform"
    Environment = "Staging"
  }
}
