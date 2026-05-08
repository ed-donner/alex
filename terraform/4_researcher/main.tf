terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
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
# ECR Repository
# ========================================

# ECR repository for the researcher Docker image
resource "aws_ecr_repository" "researcher" {
  name                 = "alex-researcher"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # Allow deletion even with images

  image_scanning_configuration {
    scan_on_push = false
  }

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

# ========================================
# App Runner Service
# ========================================

# IAM role for App Runner
resource "aws_iam_role" "app_runner_role" {
  name = "alex-app-runner-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
      },
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "tasks.apprunner.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

# Policy for App Runner to access ECR
resource "aws_iam_role_policy_attachment" "app_runner_ecr_access" {
  role       = aws_iam_role.app_runner_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# IAM role for App Runner instance (runtime access to AWS services)
resource "aws_iam_role" "app_runner_instance_role" {
  name = "alex-app-runner-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "tasks.apprunner.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

# Policy for App Runner instance to access Bedrock
resource "aws_iam_role_policy" "app_runner_instance_bedrock_access" {
  name = "alex-app-runner-instance-bedrock-policy"
  role = aws_iam_role.app_runner_instance_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:Converse",
          "bedrock:ConverseStream",
          "bedrock:GetInferenceProfile",
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ListFoundationModels"
        ]
        Resource = "*"
      }
    ]
  })
}

# App Runner service
resource "aws_apprunner_service" "researcher" {
  service_name = "alex-researcher"

  source_configuration {
    auto_deployments_enabled = false

    # Configure authentication for private ECR repository
    authentication_configuration {
      access_role_arn = aws_iam_role.app_runner_role.arn
    }

    image_repository {
      image_identifier = "${aws_ecr_repository.researcher.repository_url}:latest"
      image_configuration {
        port = "8000"
        runtime_environment_variables = {
          OPENAI_API_KEY    = var.openai_api_key
          ALEX_API_ENDPOINT = var.alex_api_endpoint
          ALEX_API_KEY      = var.alex_api_key
          BEDROCK_REGION    = var.bedrock_region
          BEDROCK_MODEL_ID  = var.bedrock_model_id
        }
      }
      image_repository_type = "ECR"
    }
  }

  instance_configuration {
    cpu               = "1 vCPU"
    memory            = "2 GB"
    instance_role_arn = aws_iam_role.app_runner_instance_role.arn
  }

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

# ========================================
# EventBridge Scheduler (Optional)
# ========================================

# IAM role for EventBridge
resource "aws_iam_role" "eventbridge_role" {
  count = var.scheduler_enabled ? 1 : 0
  name  = "alex-eventbridge-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

# Lambda function for invoking researcher
resource "aws_lambda_function" "scheduler_lambda" {
  count         = var.scheduler_enabled ? 1 : 0
  function_name = "alex-researcher-scheduler"
  role          = aws_iam_role.lambda_scheduler_role[0].arn

  # Note: The deployment package will be created by the guide instructions
  filename         = "${path.module}/../../backend/scheduler/lambda_function.zip"
  source_code_hash = fileexists("${path.module}/../../backend/scheduler/lambda_function.zip") ? filebase64sha256("${path.module}/../../backend/scheduler/lambda_function.zip") : null

  handler     = "lambda_function.handler"
  runtime     = "python3.12"
  timeout     = 180 # 3 minutes to handle App Runner response time
  memory_size = 256

  environment {
    variables = {
      APP_RUNNER_URL = aws_apprunner_service.researcher.service_url
    }
  }

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

# IAM role for scheduler Lambda
resource "aws_iam_role" "lambda_scheduler_role" {
  count = var.scheduler_enabled ? 1 : 0
  name  = "alex-scheduler-lambda-role"

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
    Part    = "4"
  }
}

# Lambda basic execution policy
resource "aws_iam_role_policy_attachment" "lambda_scheduler_basic" {
  count      = var.scheduler_enabled ? 1 : 0
  role       = aws_iam_role.lambda_scheduler_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# EventBridge schedule
resource "aws_scheduler_schedule" "research_schedule" {
  count = var.scheduler_enabled ? 1 : 0
  name  = "alex-research-schedule"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "rate(2 hours)"

  target {
    arn      = aws_lambda_function.scheduler_lambda[0].arn
    role_arn = aws_iam_role.eventbridge_role[0].arn
  }
}

# Permission for EventBridge to invoke Lambda
resource "aws_lambda_permission" "allow_eventbridge" {
  count         = var.scheduler_enabled ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scheduler_lambda[0].function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.research_schedule[0].arn
}

# Policy for EventBridge to invoke Lambda
resource "aws_iam_role_policy" "eventbridge_invoke_lambda" {
  count = var.scheduler_enabled ? 1 : 0
  name  = "InvokeLambdaPolicy"
  role  = aws_iam_role.eventbridge_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = aws_lambda_function.scheduler_lambda[0].arn
      }
    ]
  })
}