# Kubernetes Module Variables

variable "cloud_provider" {
  description = "Cloud provider (aws, gcp, azure)"
  type        = string
  validation {
    condition     = contains(["aws", "gcp", "azure"], var.cloud_provider)
    error_message = "Cloud provider must be aws, gcp, or azure."
  }
}

variable "cluster_name" {
  description = "Name of the Kubernetes cluster"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.28"
}

variable "vpc_id" {
  description = "VPC ID where cluster will be created"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for the cluster"
  type        = list(string)
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

variable "node_disk_size" {
  description = "Disk size for nodes (GB)"
  type        = number
  default     = 100
}

variable "enable_autoscaling" {
  description = "Enable cluster autoscaling"
  type        = bool
  default     = true
}

variable "enable_public_access" {
  description = "Enable public access to Kubernetes API"
  type        = bool
  default     = true
}

variable "kms_key_arn" {
  description = "KMS key ARN for encryption"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
