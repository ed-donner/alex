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

variable "scheduler_enabled" {
  description = "Enable automated research scheduler"
  type        = bool
  default     = false
}

variable "researcher_image_uri" {
  description = "Full ECR image URI for the researcher Lambda container"
  type        = string
  default     = ""
}

variable "bedrock_region" {
  description = "AWS region used for Bedrock model inference"
  type        = string
  default     = "us-west-2"
}

variable "researcher_model" {
  description = "Bedrock model identifier used by the researcher"
  type        = string
  default     = "bedrock/global.openai.gpt-oss-120b-1:0"
}

variable "mcp_logging" {
  description = "Set to exact string True to enable researcher MCP logging"
  type        = string
  default     = "False"
}

variable "langfuse_public_key" {
  description = "Langfuse public key for observability (optional)"
  type        = string
  default     = ""
}

variable "langfuse_secret_key" {
  description = "Langfuse secret key for observability (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "langfuse_host" {
  description = "Langfuse host URL (optional)"
  type        = string
  default     = "https://us.cloud.langfuse.com"
}
