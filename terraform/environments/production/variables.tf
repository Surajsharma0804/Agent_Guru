# Production Environment Variables

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "agent-guru"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "availability_zones" {
  description = "Availability zones (Multi-AZ for production)"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
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
  description = "Node instance type (production-grade)"
  type        = string
  default     = "t3.xlarge"
}

variable "node_count" {
  description = "Initial node count"
  type        = number
  default     = 3
}

variable "min_nodes" {
  description = "Minimum nodes for autoscaling"
  type        = number
  default     = 2
}

variable "max_nodes" {
  description = "Maximum nodes for autoscaling"
  type        = number
  default     = 10
}

variable "db_instance_class" {
  description = "Database instance class (production-grade)"
  type        = string
  default     = "db.r6g.xlarge"
}

variable "db_allocated_storage" {
  description = "Database storage (GB)"
  type        = number
  default     = 100
}

variable "db_engine_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15.4"
}

variable "redis_node_type" {
  description = "Redis node type (production-grade)"
  type        = string
  default     = "cache.r6g.xlarge"
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

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true
}

variable "alert_webhook_url" {
  description = "Webhook URL for alerts (Slack, PagerDuty, etc.)"
  type        = string
  default     = ""
}

variable "alert_emails" {
  description = "Email addresses for alerts"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Common tags"
  type        = map(string)
  default = {
    Project     = "Agent Guru"
    Component   = "Core Reasoning Engine"
    ManagedBy   = "Terraform"
    Environment = "Production"
  }
}
