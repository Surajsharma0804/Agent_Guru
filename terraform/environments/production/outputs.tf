# Production Environment Outputs

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
  description = "Database primary endpoint"
  value       = module.database.db_endpoint
}

output "db_read_replica_endpoint" {
  description = "Database read replica endpoint"
  value       = module.database.read_replica_endpoint
}

output "db_connection_string" {
  description = "Database connection string"
  value       = module.database.connection_string
  sensitive   = true
}

output "redis_primary_endpoint" {
  description = "Redis primary endpoint"
  value       = module.redis.redis_primary_endpoint
}

output "redis_reader_endpoint" {
  description = "Redis reader endpoint"
  value       = module.redis.redis_reader_endpoint
}

output "redis_connection_string" {
  description = "Redis connection string"
  value       = module.redis.connection_string
  sensitive   = true
}

output "prometheus_endpoint" {
  description = "Prometheus endpoint"
  value       = module.monitoring.prometheus_endpoint
}

output "grafana_endpoint" {
  description = "Grafana endpoint"
  value       = module.monitoring.grafana_endpoint
}

output "jaeger_endpoint" {
  description = "Jaeger endpoint"
  value       = module.monitoring.jaeger_endpoint
}

output "kms_key_id" {
  description = "KMS key ID for encryption"
  value       = aws_kms_key.main.id
}

output "sns_topic_arn" {
  description = "SNS topic ARN for alerts"
  value       = aws_sns_topic.alerts.arn
}

output "kubeconfig_command" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${module.kubernetes.cluster_name}"
}
