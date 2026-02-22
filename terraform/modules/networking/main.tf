# Networking Module
# Creates VPC, subnets, NAT gateways, and security infrastructure

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# VPC
resource "aws_vpc" "main" {
  count = var.cloud_provider == "aws" ? 1 : 0

  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-vpc"
    }
  )
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  count = var.cloud_provider == "aws" ? 1 : 0

  vpc_id = aws_vpc.main[0].id

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-igw"
    }
  )
}

# Public Subnets
resource "aws_subnet" "public" {
  count = var.cloud_provider == "aws" ? length(var.availability_zones) : 0

  vpc_id                  = aws_vpc.main[0].id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(
    var.tags,
    {
      Name                                           = "${var.project_name}-public-${var.availability_zones[count.index]}"
      "kubernetes.io/role/elb"                       = "1"
      "kubernetes.io/cluster/${var.cluster_name}"    = "shared"
    }
  )
}

# Private Subnets
resource "aws_subnet" "private" {
  count = var.cloud_provider == "aws" ? length(var.availability_zones) : 0

  vpc_id            = aws_vpc.main[0].id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + length(var.availability_zones))
  availability_zone = var.availability_zones[count.index]

  tags = merge(
    var.tags,
    {
      Name                                           = "${var.project_name}-private-${var.availability_zones[count.index]}"
      "kubernetes.io/role/internal-elb"              = "1"
      "kubernetes.io/cluster/${var.cluster_name}"    = "shared"
    }
  )
}

# Elastic IPs for NAT Gateways
resource "aws_eip" "nat" {
  count = var.cloud_provider == "aws" && var.enable_nat_gateway ? length(var.availability_zones) : 0

  domain = "vpc"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-nat-eip-${var.availability_zones[count.index]}"
    }
  )

  depends_on = [aws_internet_gateway.main]
}

# NAT Gateways
resource "aws_nat_gateway" "main" {
  count = var.cloud_provider == "aws" && var.enable_nat_gateway ? length(var.availability_zones) : 0

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-nat-${var.availability_zones[count.index]}"
    }
  )

  depends_on = [aws_internet_gateway.main]
}

# Public Route Table
resource "aws_route_table" "public" {
  count = var.cloud_provider == "aws" ? 1 : 0

  vpc_id = aws_vpc.main[0].id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main[0].id
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-public-rt"
    }
  )
}

# Public Route Table Associations
resource "aws_route_table_association" "public" {
  count = var.cloud_provider == "aws" ? length(var.availability_zones) : 0

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}

# Private Route Tables
resource "aws_route_table" "private" {
  count = var.cloud_provider == "aws" ? length(var.availability_zones) : 0

  vpc_id = aws_vpc.main[0].id

  dynamic "route" {
    for_each = var.enable_nat_gateway ? [1] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = aws_nat_gateway.main[count.index].id
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-private-rt-${var.availability_zones[count.index]}"
    }
  )
}

# Private Route Table Associations
resource "aws_route_table_association" "private" {
  count = var.cloud_provider == "aws" ? length(var.availability_zones) : 0

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# VPC Flow Logs
resource "aws_flow_log" "main" {
  count = var.cloud_provider == "aws" && var.enable_flow_logs ? 1 : 0

  iam_role_arn    = aws_iam_role.flow_logs[0].arn
  log_destination = aws_cloudwatch_log_group.flow_logs[0].arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.main[0].id

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "flow_logs" {
  count = var.cloud_provider == "aws" && var.enable_flow_logs ? 1 : 0

  name              = "/aws/vpc/${var.project_name}-flow-logs"
  retention_in_days = 7

  tags = var.tags
}

resource "aws_iam_role" "flow_logs" {
  count = var.cloud_provider == "aws" && var.enable_flow_logs ? 1 : 0

  name = "${var.project_name}-flow-logs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "vpc-flow-logs.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "flow_logs" {
  count = var.cloud_provider == "aws" && var.enable_flow_logs ? 1 : 0

  name = "${var.project_name}-flow-logs-policy"
  role = aws_iam_role.flow_logs[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

# Network ACLs
resource "aws_network_acl" "main" {
  count = var.cloud_provider == "aws" ? 1 : 0

  vpc_id     = aws_vpc.main[0].id
  subnet_ids = concat(aws_subnet.public[*].id, aws_subnet.private[*].id)

  ingress {
    protocol   = -1
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 0
    to_port    = 0
  }

  egress {
    protocol   = -1
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 0
    to_port    = 0
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-nacl"
    }
  )
}
