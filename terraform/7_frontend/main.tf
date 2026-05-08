# Part 7: Frontend & API Infrastructure

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Data sources
data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

# Reference Part 5 Database resources
data "terraform_remote_state" "database" {
  backend = "local"
  config = {
    path = "../5_database/terraform.tfstate"
  }
}

# Reference Part 6 Agents resources
data "terraform_remote_state" "agents" {
  backend = "local"
  config = {
    path = "../6_agents/terraform.tfstate"
  }
}

locals {
  name_prefix = "alex"

  common_tags = {
    Project     = "alex"
    Part        = "7_frontend"
    ManagedBy   = "terraform"
  }
}

# Optional CloudFront (some AWS accounts must be verified first)
locals {
  cloudfront_domain = try(aws_cloudfront_distribution.main[0].domain_name, "")
  cors_origins      = var.enable_cloudfront ? "http://localhost:3000,https://${local.cloudfront_domain}" : "http://localhost:3000,http://${aws_s3_bucket_website_configuration.frontend.website_endpoint}"
}

# S3 bucket for frontend static website
resource "aws_s3_bucket" "frontend" {
  bucket = "${local.name_prefix}-frontend-${data.aws_caller_identity.current.account_id}"
  tags   = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "404.html"
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend.arn}/*"
      },
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.frontend]
}

# IAM role for Lambda API function
resource "aws_iam_role" "api_lambda_role" {
  name = "${local.name_prefix}-api-lambda-role"
  tags = local.common_tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      },
    ]
  })
}

# Attach basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "api_lambda_basic" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.api_lambda_role.name
}

# Policy for Aurora Data API access
resource "aws_iam_role_policy" "api_lambda_aurora" {
  name = "${local.name_prefix}-api-lambda-aurora"
  role = aws_iam_role.api_lambda_role.id

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
        Resource = data.terraform_remote_state.database.outputs.aurora_cluster_arn
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = data.terraform_remote_state.database.outputs.aurora_secret_arn
      }
    ]
  })
}

# Policy for SQS access
resource "aws_iam_role_policy" "api_lambda_sqs" {
  name = "${local.name_prefix}-api-lambda-sqs"
  role = aws_iam_role.api_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = data.terraform_remote_state.agents.outputs.sqs_queue_arn
      }
    ]
  })
}

# Policy for Lambda invoke (for testing agents directly)
resource "aws_iam_role_policy" "api_lambda_invoke" {
  name = "${local.name_prefix}-api-lambda-invoke"
  role = aws_iam_role.api_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "lambda:InvokeFunction"
        Resource = [
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:alex-planner",
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:alex-tagger",
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:alex-reporter",
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:alex-charter",
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:alex-retirement"
        ]
      }
    ]
  })
}

# Lambda function for API
resource "aws_lambda_function" "api" {
  filename         = "${path.module}/../../backend/api/api_lambda.zip"
  function_name    = "${local.name_prefix}-api"
  role             = aws_iam_role.api_lambda_role.arn
  handler          = "lambda_handler.handler"
  source_code_hash = filebase64sha256("${path.module}/../../backend/api/api_lambda.zip")
  runtime          = "python3.12"
  architectures    = ["x86_64"]
  timeout          = 30
  memory_size      = 512
  tags             = local.common_tags

  environment {
    variables = {
      # Database configuration from Part 5
      AURORA_CLUSTER_ARN = data.terraform_remote_state.database.outputs.aurora_cluster_arn
      AURORA_SECRET_ARN  = data.terraform_remote_state.database.outputs.aurora_secret_arn
      AURORA_DATABASE    = data.terraform_remote_state.database.outputs.database_name
      DEFAULT_AWS_REGION = var.aws_region

      # SQS configuration from Part 6
      SQS_QUEUE_URL = data.terraform_remote_state.agents.outputs.sqs_queue_url

      # Clerk configuration for JWT validation
      CLERK_JWKS_URL = var.clerk_jwks_url
      CLERK_ISSUER   = var.clerk_issuer

      # CORS configuration
      CORS_ORIGINS = local.cors_origins
    }
  }

  # Ensure Lambda waits for dependencies including CloudFront
  depends_on = [
    aws_iam_role_policy.api_lambda_aurora,
    aws_iam_role_policy.api_lambda_sqs,
    aws_iam_role_policy.api_lambda_invoke
  ]
}

# API Gateway HTTP API
resource "aws_apigatewayv2_api" "main" {
  name          = "${local.name_prefix}-api-gateway"
  protocol_type = "HTTP"
  tags          = local.common_tags

  cors_configuration {
    allow_credentials = false  # Cannot be true when allow_origins is "*"
    allow_headers     = ["authorization", "content-type", "x-amz-date", "x-api-key", "x-amz-security-token"]
    allow_methods     = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_origins     = ["*"]  # CORS is handled in Lambda via environment variables
    max_age           = 300
  }
}

# No JWT authorizer needed - authentication is handled in Lambda like in the saas reference

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
  tags        = local.common_tags

  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 100
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id           = aws_apigatewayv2_api.main.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.api.invoke_arn
}

# API Gateway Routes - all routes under /api/*
resource "aws_apigatewayv2_route" "api_any" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "ANY /api/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"

  # No authorization at API Gateway level - handled in Lambda
}

# OPTIONS route for CORS preflight (no auth needed)
resource "aws_apigatewayv2_route" "api_options" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "OPTIONS /api/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# CloudFront distribution
resource "aws_cloudfront_distribution" "main" {
  count               = var.enable_cloudfront ? 1 : 0
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  tags                = local.common_tags
  comment             = "Alex Financial Advisor Frontend"

  # S3 origin for frontend
  origin {
    domain_name = aws_s3_bucket_website_configuration.frontend.website_endpoint
    origin_id   = "S3-${aws_s3_bucket.frontend.id}"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # API Gateway origin for /api/* paths
  origin {
    domain_name = replace(aws_apigatewayv2_api.main.api_endpoint, "https://", "")
    origin_id   = "API-Gateway"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # Default behavior for static content (S3)
  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.frontend.id}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  # Behavior for API calls (/api/*)
  ordered_cache_behavior {
    path_pattern     = "/api/*"
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "API-Gateway"

    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Content-Type", "Accept"]
      cookies {
        forward = "all"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0
  }

  # Custom error pages for SPA routing
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

