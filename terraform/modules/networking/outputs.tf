# Networking Module Outputs

output "vpc_id" {
  description = "VPC ID"
  value       = var.cloud_provider == "aws" ? aws_vpc.main[0].id : null
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = var.cloud_provider == "aws" ? aws_vpc.main[0].cidr_block : null
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = var.cloud_provider == "aws" ? aws_subnet.public[*].id : null
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = var.cloud_provider == "aws" ? aws_subnet.private[*].id : null
}

output "nat_gateway_ids" {
  description = "List of NAT gateway IDs"
  value       = var.cloud_provider == "aws" && var.enable_nat_gateway ? aws_nat_gateway.main[*].id : null
}

output "internet_gateway_id" {
  description = "Internet gateway ID"
  value       = var.cloud_provider == "aws" ? aws_internet_gateway.main[0].id : null
}

output "public_route_table_id" {
  description = "Public route table ID"
  value       = var.cloud_provider == "aws" ? aws_route_table.public[0].id : null
}

output "private_route_table_ids" {
  description = "List of private route table IDs"
  value       = var.cloud_provider == "aws" ? aws_route_table.private[*].id : null
}
