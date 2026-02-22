# PostgreSQL Database Module
# Creates a managed PostgreSQL database (RDS/Cloud SQL/Azure Database)

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

# Generate random password for database
resource "random_password" "db_password" {
  length  = 32
  special = true
}

# AWS RDS PostgreSQL Instance
resource "aws_db_instance" "main" {
  count = var.cloud_provider == "aws" ? 1 : 0

  identifier     = var.db_name
  engine         = "postgres"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = var.enable_encryption
  kms_key_id            = var.kms_key_arn

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db_password.result
  port     = 5432

  multi_az               = var.multi_az
  db_subnet_group_name   = aws_db_subnet_group.main[0].name
  vpc_security_group_ids = [aws_security_group.db[0].id]
  publicly_accessible    = false

  backup_retention_period = var.backup_retention_days
  backup_window           = var.backup_window
  maintenance_window      = var.maintenance_window

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  monitoring_interval             = 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring[0].arn

  performance_insights_enabled    = true
  performance_insights_kms_key_id = var.kms_key_arn
  performance_insights_retention_period = 7

  deletion_protection = var.environment == "production" ? true : false
  skip_final_snapshot = var.environment == "production" ? false : true
  final_snapshot_identifier = var.environment == "production" ? "${var.db_name}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}" : null

  auto_minor_version_upgrade = true
  apply_immediately          = var.environment == "production" ? false : true

  tags = merge(
    var.tags,
    {
      Name = var.db_name
    }
  )
}

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  count = var.cloud_provider == "aws" ? 1 : 0

  name       = "${var.db_name}-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(
    var.tags,
    {
      Name = "${var.db_name}-subnet-group"
    }
  )
}

# DB Security Group
resource "aws_security_group" "db" {
  count = var.cloud_provider == "aws" ? 1 : 0

  name        = "${var.db_name}-sg"
  description = "Security group for PostgreSQL database"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from Kubernetes"
    from_port       = 5432
    to_port         = 5432
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
      Name = "${var.db_name}-sg"
    }
  )
}

# RDS Monitoring IAM Role
resource "aws_iam_role" "rds_monitoring" {
  count = var.cloud_provider == "aws" ? 1 : 0

  name = "${var.db_name}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "monitoring.rds.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  count = var.cloud_provider == "aws" ? 1 : 0

  role       = aws_iam_role.rds_monitoring[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# Read Replica (for production)
resource "aws_db_instance" "read_replica" {
  count = var.cloud_provider == "aws" && var.create_read_replica ? 1 : 0

  identifier     = "${var.db_name}-read-replica"
  replicate_source_db = aws_db_instance.main[0].identifier
  instance_class = var.db_instance_class

  storage_encrypted = var.enable_encryption
  kms_key_id        = var.kms_key_arn

  multi_az               = false
  vpc_security_group_ids = [aws_security_group.db[0].id]
  publicly_accessible    = false

  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring[0].arn

  performance_insights_enabled          = true
  performance_insights_kms_key_id       = var.kms_key_arn
  performance_insights_retention_period = 7

  auto_minor_version_upgrade = true
  apply_immediately          = false

  tags = merge(
    var.tags,
    {
      Name = "${var.db_name}-read-replica"
    }
  )
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "db_cpu" {
  count = var.cloud_provider == "aws" ? 1 : 0

  alarm_name          = "${var.db_name}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors RDS CPU utilization"
  alarm_actions       = var.alarm_actions

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main[0].id
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "db_connections" {
  count = var.cloud_provider == "aws" ? 1 : 0

  alarm_name          = "${var.db_name}-high-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors RDS database connections"
  alarm_actions       = var.alarm_actions

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main[0].id
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "db_storage" {
  count = var.cloud_provider == "aws" ? 1 : 0

  alarm_name          = "${var.db_name}-low-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "10737418240"  # 10 GB in bytes
  alarm_description   = "This metric monitors RDS free storage space"
  alarm_actions       = var.alarm_actions

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main[0].id
  }

  tags = var.tags
}

# Store password in AWS Secrets Manager
resource "aws_secretsmanager_secret" "db_password" {
  count = var.cloud_provider == "aws" ? 1 : 0

  name        = "${var.db_name}-password"
  description = "PostgreSQL database password"

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "db_password" {
  count = var.cloud_provider == "aws" ? 1 : 0

  secret_id = aws_secretsmanager_secret.db_password[0].id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db_password.result
    engine   = "postgres"
    host     = aws_db_instance.main[0].address
    port     = aws_db_instance.main[0].port
    dbname   = var.db_name
  })
}
