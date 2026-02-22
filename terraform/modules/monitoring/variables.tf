# Monitoring Module Variables

variable "namespace" {
  description = "Kubernetes namespace for monitoring"
  type        = string
  default     = "monitoring"
}

variable "prometheus_retention_days" {
  description = "Prometheus metrics retention period (days)"
  type        = number
  default     = 15
}

variable "prometheus_storage_size" {
  description = "Prometheus storage size"
  type        = string
  default     = "50Gi"
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true
}

variable "enable_alertmanager" {
  description = "Enable AlertManager"
  type        = bool
  default     = true
}

variable "alert_webhook_url" {
  description = "Webhook URL for alerts (e.g., Slack, PagerDuty)"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
