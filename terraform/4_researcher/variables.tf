variable "aws_region" {
  description = "AWS region for resources"
  type        = string
}

variable "openai_api_key" {
  description = "OpenAI API key for the researcher agent"
  type        = string
  sensitive   = true
}

variable "alex_api_endpoint" {
  description = "Alex API endpoint from Part 3"
  type        = string
}

variable "alex_api_key" {
  description = "Alex API key from Part 3"
  type        = string
  sensitive   = true
}

variable "bedrock_region" {
  description = "AWS region to use for Bedrock model calls"
  type        = string
  default     = "us-west-2"
}

variable "bedrock_model_id" {
  description = "Bedrock model ID used by the researcher agent"
  type        = string
  default     = "us.amazon.nova-pro-v1:0"
}

variable "model_provider" {
  description = "Model provider for the researcher agent: bedrock or openai"
  type        = string
  default     = "openai"
}

variable "openai_model_id" {
  description = "OpenAI model ID used when model_provider is openai"
  type        = string
  default     = "gpt-4.1-mini"
}

variable "vpc_id" {
  description = "VPC ID for the ECS Fargate service"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for the public load balancer and ECS Fargate service"
  type        = list(string)
}

variable "scheduler_enabled" {
  description = "Enable automated research scheduler"
  type        = bool
  default     = false
}