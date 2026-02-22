# Redis Module Variables

variable "cloud_provider" {
  description = "Cloud provider (aws, gcp, azure)"
  type        = string
  validation {
    condition     = contains(["aws", "gcp", "azure"], var.cloud_provider)
    error_message = "Cloud provider must be aws, gcp, or azure."
  }
}

variable "environment" {
  description = "Environment name (staging, production)"
  type        = string
}

variable "cluster_id" {
  description = "Redis cluster identifier"
  type        = string
}

variable "redis_node_type" {
  description = "Redis node instance type"
  type        = string
}

variable "num_cache_nodes" {
  description = "Number of cache nodes in cluster"
  type        = number
  default     = 3
}

variable "redis_engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"
}

variable "parameter_group_family" {
  description = "Redis parameter group family"
  type        = string
  default     = "redis7"
}

variable "multi_az" {
  description = "Enable multi-AZ deployment"
  type        = bool
  default     = false
}

variable "snapshot_retention_limit" {
  description = "Number of days to retain snapshots"
  type        = number
  default     = 7
}

variable "snapshot_window" {
  description = "Preferred snapshot window"
  type        = string
  default     = "03:00-05:00"
}

variable "maintenance_window" {
  description = "Preferred maintenance window"
  type        = string
  default     = "sun:05:00-sun:07:00"
}

variable "enable_encryption" {
  description = "Enable encryption at rest and in transit"
  type        = bool
  default     = true
}

variable "kms_key_arn" {
  description = "KMS key ARN for encryption"
  type        = string
  default     = ""
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for Redis cluster"
  type        = list(string)
}

variable "allowed_security_groups" {
  description = "Security groups allowed to access Redis"
  type        = list(string)
}

variable "alarm_actions" {
  description = "SNS topic ARNs for CloudWatch alarms"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
