# Database Module Outputs

output "db_instance_id" {
  description = "Database instance ID"
  value       = var.cloud_provider == "aws" ? aws_db_instance.main[0].id : null
}

output "db_endpoint" {
  description = "Database connection endpoint"
  value       = var.cloud_provider == "aws" ? aws_db_instance.main[0].endpoint : null
}

output "db_address" {
  description = "Database hostname"
  value       = var.cloud_provider == "aws" ? aws_db_instance.main[0].address : null
}

output "db_port" {
  description = "Database port"
  value       = var.cloud_provider == "aws" ? aws_db_instance.main[0].port : null
}

output "db_name" {
  description = "Database name"
  value       = var.db_name
}

output "db_username" {
  description = "Database username"
  value       = var.db_username
  sensitive   = true
}

output "db_password" {
  description = "Database password"
  value       = random_password.db_password.result
  sensitive   = true
}

output "db_security_group_id" {
  description = "Security group ID for database"
  value       = var.cloud_provider == "aws" ? aws_security_group.db[0].id : null
}

output "db_secret_arn" {
  description = "ARN of secret containing database credentials"
  value       = var.cloud_provider == "aws" ? aws_secretsmanager_secret.db_password[0].arn : null
}

output "read_replica_endpoint" {
  description = "Read replica endpoint"
  value       = var.cloud_provider == "aws" && var.create_read_replica ? aws_db_instance.read_replica[0].endpoint : null
}

output "connection_string" {
  description = "Database connection string"
  value       = var.cloud_provider == "aws" ? "postgresql://${var.db_username}:${random_password.db_password.result}@${aws_db_instance.main[0].address}:${aws_db_instance.main[0].port}/${var.db_name}" : null
  sensitive   = true
}
