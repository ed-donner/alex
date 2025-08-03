terraform {
  required_version = ">= 1.5"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    # Note: We can't use variables in backend config, so we'll handle this differently
    # The bucket name will be provided during terraform init
  }
}

provider "aws" {
  region = var.aws_region
}

# Data source for current caller identity
data "aws_caller_identity" "current" {}

# IAM role for SageMaker
resource "aws_iam_role" "sagemaker_role" {
  name = "alex-sagemaker-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "sagemaker.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "sagemaker_full_access" {
  role       = aws_iam_role.sagemaker_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

# SageMaker Model
resource "aws_sagemaker_model" "embedding_model" {
  name               = "alex-embedding-model"
  execution_role_arn = aws_iam_role.sagemaker_role.arn

  primary_container {
    image = var.sagemaker_image_uri
    environment = {
      HF_MODEL_ID = var.embedding_model_name
      HF_TASK     = "feature-extraction"
    }
  }

  depends_on = [aws_iam_role_policy_attachment.sagemaker_full_access]
}

# Serverless Inference Config
resource "aws_sagemaker_endpoint_configuration" "serverless_config" {
  name = "alex-embedding-serverless-config"

  production_variants {
    model_name = aws_sagemaker_model.embedding_model.name
    
    serverless_config {
      memory_size_in_mb = 3072
      max_concurrency   = 10
    }
  }
}

# SageMaker Endpoint
resource "aws_sagemaker_endpoint" "embedding_endpoint" {
  name                 = "alex-embedding-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.serverless_config.name
  
  depends_on = [
    aws_iam_role_policy_attachment.sagemaker_full_access
  ]
}

# OpenSearch Serverless module
module "opensearch" {
  source = "./modules/opensearch"
  
  collection_name = "alex-portfolio"
  lambda_role_arn = module.lambda.role_arn
  
  tags = {
    Project     = "Alex"
    Environment = var.environment
  }
}

# Lambda function module
module "lambda" {
  source = "./modules/lambda"
  
  function_name           = "alex-ingest"
  deployment_package_path = "${path.module}/../backend/ingest/lambda_function.zip"
  opensearch_endpoint     = module.opensearch.collection_endpoint
  opensearch_collection_arn = module.opensearch.collection_arn
  sagemaker_endpoint_name = aws_sagemaker_endpoint.embedding_endpoint.name
  sagemaker_endpoint_arn  = aws_sagemaker_endpoint.embedding_endpoint.arn
  
  tags = {
    Project     = "Alex"
    Environment = var.environment
  }
}

# API Gateway module
module "api_gateway" {
  source = "./modules/api_gateway"
  
  api_name             = "alex-api"
  stage_name           = var.environment
  lambda_function_name = module.lambda.function_name
  lambda_invoke_arn    = module.lambda.invoke_arn
  
  tags = {
    Project     = "Alex"
    Environment = var.environment
  }
}