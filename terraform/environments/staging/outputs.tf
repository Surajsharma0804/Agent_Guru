# Staging Environment Outputs

output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "cluster_name" {
  description = "Kubernetes cluster name"
  value       = module.kubernetes.cluster_name
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint"
  value       = module.kubernetes.cluster_endpoint
}

output "db_endpoint" {
  description = "Database endpoint"
  value       = module.database.db_endpoint
}

output "db_connection_string" {
  description = "Database connection string"
  value       = module.database.connection_string
  sensitive   = true
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = module.redis.redis_primary_endpoint
}

output "redis_connection_string" {
  description = "Redis connection string"
  value       = module.redis.connection_string
  sensitive   = true
}

output "prometheus_endpoint" {
  description = "Prometheus endpoint"
  value       = var.enable_monitoring ? module.monitoring[0].prometheus_endpoint : null
}

output "grafana_endpoint" {
  description = "Grafana endpoint"
  value       = var.enable_monitoring ? module.monitoring[0].grafana_endpoint : null
}

output "kubeconfig_command" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${module.kubernetes.cluster_name}"
}
