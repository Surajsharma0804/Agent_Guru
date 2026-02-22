# Redis Module Outputs

output "redis_cluster_id" {
  description = "Redis cluster ID"
  value       = var.cloud_provider == "aws" ? aws_elasticache_replication_group.main[0].id : null
}

output "redis_primary_endpoint" {
  description = "Redis primary endpoint address"
  value       = var.cloud_provider == "aws" ? aws_elasticache_replication_group.main[0].primary_endpoint_address : null
}

output "redis_reader_endpoint" {
  description = "Redis reader endpoint address"
  value       = var.cloud_provider == "aws" ? aws_elasticache_replication_group.main[0].reader_endpoint_address : null
}

output "redis_port" {
  description = "Redis port"
  value       = 6379
}

output "redis_auth_token" {
  description = "Redis authentication token"
  value       = var.cloud_provider == "aws" && var.enable_encryption ? random_password.redis_auth_token[0].result : null
  sensitive   = true
}

output "redis_security_group_id" {
  description = "Security group ID for Redis"
  value       = var.cloud_provider == "aws" ? aws_security_group.redis[0].id : null
}

output "redis_secret_arn" {
  description = "ARN of secret containing Redis auth token"
  value       = var.cloud_provider == "aws" && var.enable_encryption ? aws_secretsmanager_secret.redis_auth_token[0].arn : null
}

output "connection_string" {
  description = "Redis connection string"
  value = var.cloud_provider == "aws" ? (
    var.enable_encryption ?
    "rediss://:${random_password.redis_auth_token[0].result}@${aws_elasticache_replication_group.main[0].primary_endpoint_address}:6379" :
    "redis://${aws_elasticache_replication_group.main[0].primary_endpoint_address}:6379"
  ) : null
  sensitive = true
}
