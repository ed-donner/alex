terraform {
  required_version = ">= 1.5"
  
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
  
  # Using local backend - state will be stored in terraform.tfstate in this directory
  # This is automatically gitignored for security
}

provider "aws" {
  region = var.aws_region
}

# Data source for current caller identity
data "aws_caller_identity" "current" {}

# ========================================
# Aurora Serverless v2 PostgreSQL Cluster
# ========================================

# Random password for database
resource "random_password" "db_password" {
  length  = 32
  special = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Secrets Manager secret for database credentials
resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "alex-aurora-credentials-${random_id.suffix.hex}"
  recovery_window_in_days = 0  # For development - immediate deletion
  
  tags = {
    Project = "alex"
    Part    = "5"
  }
}

resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = "alexadmin"
    password = random_password.db_password.result
  })
}

# DB Subnet Group (using default VPC)
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_db_subnet_group" "aurora" {
  name       = "alex-aurora-subnet-group"
  subnet_ids = data.aws_subnets.default.ids
  
  tags = {
    Project = "alex"
    Part    = "5"
  }
}

# Security group for Aurora
resource "aws_security_group" "aurora" {
  name        = "alex-aurora-sg"
  description = "Security group for Alex Aurora cluster"
  vpc_id      = data.aws_vpc.default.id
  
  # Allow PostgreSQL access from within VPC
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Project = "alex"
    Part    = "5"
  }
}

# Aurora Serverless v2 Cluster
resource "aws_rds_cluster" "aurora" {
  cluster_identifier     = "alex-aurora-cluster"
  engine                 = "aurora-postgresql"
  engine_mode            = "provisioned"
  engine_version         = "15.12"
  database_name          = "alex"
  master_username        = "alexadmin"
  master_password        = random_password.db_password.result
  
  # Serverless v2 scaling configuration
  serverlessv2_scaling_configuration {
    min_capacity = var.min_capacity
    max_capacity = var.max_capacity
  }
  
  # Enable Data API
  enable_http_endpoint = true
  
  # Networking
  db_subnet_group_name   = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [aws_security_group.aurora.id]
  
  # Backup and maintenance
  backup_retention_period   = 7
  preferred_backup_window   = "03:00-04:00"
  preferred_maintenance_window = "sun:04:00-sun:05:00"
  
  # Development settings
  skip_final_snapshot = true
  apply_immediately   = true
  
  tags = {
    Project = "alex"
    Part    = "5"
  }
}

# Aurora Serverless v2 Instance
resource "aws_rds_cluster_instance" "aurora" {
  identifier          = "alex-aurora-instance-1"
  cluster_identifier  = aws_rds_cluster.aurora.id
  instance_class      = "db.serverless"
  engine              = aws_rds_cluster.aurora.engine
  engine_version      = aws_rds_cluster.aurora.engine_version
  
  performance_insights_enabled = false  # Save costs in development
  
  tags = {
    Project = "alex"
    Part    = "5"
  }
}

# IAM role for Lambda to access Aurora Data API
resource "aws_iam_role" "lambda_aurora_role" {
  name = "alex-lambda-aurora-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  
  tags = {
    Project = "alex"
    Part    = "5"
  }
}

# IAM policy for Data API access
resource "aws_iam_role_policy" "lambda_aurora_policy" {
  name = "alex-lambda-aurora-policy"
  role = aws_iam_role.lambda_aurora_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds-data:ExecuteStatement",
          "rds-data:BatchExecuteStatement",
          "rds-data:BeginTransaction",
          "rds-data:CommitTransaction",
          "rds-data:RollbackTransaction"
        ]
        Resource = aws_rds_cluster.aurora.arn
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.db_credentials.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      }
    ]
  })
}

# Attach basic Lambda execution role
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_aurora_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
