# Redis Cluster Module
# Creates a managed Redis cluster (ElastiCache/Memorystore/Azure Cache)

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# AWS ElastiCache Redis Cluster
resource "aws_elasticache_replication_group" "main" {
  count = var.cloud_provider == "aws" ? 1 : 0

  replication_group_id       = var.cluster_id
  replication_group_description = "Redis cluster for Agent Guru"
  engine                     = "redis"
  engine_version             = var.redis_engine_version
  node_type                  = var.redis_node_type
  port                       = 6379

  num_cache_clusters         = var.num_cache_nodes
  automatic_failover_enabled = var.num_cache_nodes > 1
  multi_az_enabled           = var.multi_az

  subnet_group_name    = aws_elasticache_subnet_group.main[0].name
  security_group_ids   = [aws_security_group.redis[0].id]
  parameter_group_name = aws_elasticache_parameter_group.main[0].name

  at_rest_encryption_enabled = var.enable_encryption
  transit_encryption_enabled = var.enable_encryption
  auth_token_enabled         = var.enable_encryption
  auth_token                 = var.enable_encryption ? random_password.redis_auth_token[0].result : null
  kms_key_id                 = var.kms_key_arn

  snapshot_retention_limit = var.snapshot_retention_limit
  snapshot_window          = var.snapshot_window
  maintenance_window       = var.maintenance_window

  auto_minor_version_upgrade = true
  apply_immediately          = var.environment == "production" ? false : true

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_slow_log[0].name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_engine_log[0].name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "engine-log"
  }

  tags = merge(
    var.tags,
    {
      Name = var.cluster_id
    }
  )
}

# Generate auth token for Redis
resource "random_password" "redis_auth_token" {
  count = var.cloud_provider == "aws" && var.enable_encryption ? 1 : 0

  length  = 32
  special = false
}

# Redis Subnet Group
resource "aws_elasticache_subnet_group" "main" {
  count = var.cloud_provider == "aws" ? 1 : 0

  name       = "${var.cluster_id}-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(
    var.tags,
    {
      Name = "${var.cluster_id}-subnet-group"
    }
  )
}

# Redis Parameter Group
resource "aws_elasticache_parameter_group" "main" {
  count = var.cloud_provider == "aws" ? 1 : 0

  name   = "${var.cluster_id}-params"
  family = var.parameter_group_family

  # Optimize for performance
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "timeout"
    value = "300"
  }

  parameter {
    name  = "tcp-keepalive"
    value = "300"
  }

  parameter {
    name  = "maxmemory-samples"
    value = "10"
  }

  tags = var.tags
}

# Redis Security Group
resource "aws_security_group" "redis" {
  count = var.cloud_provider == "aws" ? 1 : 0

  name        = "${var.cluster_id}-sg"
  description = "Security group for Redis cluster"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Redis from Kubernetes"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = var.allowed_security_groups
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.cluster_id}-sg"
    }
  )
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "redis_slow_log" {
  count = var.cloud_provider == "aws" ? 1 : 0

  name              = "/aws/elasticache/${var.cluster_id}/slow-log"
  retention_in_days = 7

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "redis_engine_log" {
  count = var.cloud_provider == "aws" ? 1 : 0

  name              = "/aws/elasticache/${var.cluster_id}/engine-log"
  retention_in_days = 7

  tags = var.tags
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "redis_cpu" {
  count = var.cloud_provider == "aws" ? 1 : 0

  alarm_name          = "${var.cluster_id}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "75"
  alarm_description   = "This metric monitors Redis CPU utilization"
  alarm_actions       = var.alarm_actions

  dimensions = {
    CacheClusterId = "${var.cluster_id}-001"
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "redis_memory" {
  count = var.cloud_provider == "aws" ? 1 : 0

  alarm_name          = "${var.cluster_id}-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "90"
  alarm_description   = "This metric monitors Redis memory usage"
  alarm_actions       = var.alarm_actions

  dimensions = {
    CacheClusterId = "${var.cluster_id}-001"
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "redis_evictions" {
  count = var.cloud_provider == "aws" ? 1 : 0

  alarm_name          = "${var.cluster_id}-evictions"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Evictions"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1000"
  alarm_description   = "This metric monitors Redis evictions"
  alarm_actions       = var.alarm_actions

  dimensions = {
    CacheClusterId = "${var.cluster_id}-001"
  }

  tags = var.tags
}

# Store auth token in AWS Secrets Manager
resource "aws_secretsmanager_secret" "redis_auth_token" {
  count = var.cloud_provider == "aws" && var.enable_encryption ? 1 : 0

  name        = "${var.cluster_id}-auth-token"
  description = "Redis authentication token"

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "redis_auth_token" {
  count = var.cloud_provider == "aws" && var.enable_encryption ? 1 : 0

  secret_id = aws_secretsmanager_secret.redis_auth_token[0].id
  secret_string = jsonencode({
    auth_token = random_password.redis_auth_token[0].result
    host       = aws_elasticache_replication_group.main[0].primary_endpoint_address
    port       = 6379
  })
}
