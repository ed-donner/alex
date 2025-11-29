# =============================================================================
# VARIABLES - Cloud Run Agents
# =============================================================================

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "image_tag" {
  description = "Container image tag"
  type        = string
  default     = "latest"
}

variable "cloud_run_service_account" {
  description = "Service account email for Cloud Run services"
  type        = string
}

variable "db_connection_name" {
  description = "Cloud SQL instance connection name (from database terraform output)"
  type        = string
}

variable "database_name" {
  description = "Database name"
  type        = string
  default     = "alex"
}

variable "database_user" {
  description = "Database user"
  type        = string
  default     = "alex_app"
}

variable "db_password_secret_id" {
  description = "Secret Manager ID for database password"
  type        = string
  default     = "alex-db-password"
}

variable "pubsub_topic" {
  description = "Pub/Sub topic name for job queue"
  type        = string
  default     = "alex-job-queue"
}

variable "min_instances" {
  description = "Minimum number of instances (0 for scale-to-zero)"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
}

variable "cpu_limit" {
  description = "CPU limit for containers"
  type        = string
  default     = "2"
}

variable "memory_limit" {
  description = "Memory limit for containers"
  type        = string
  default     = "2Gi"
}

variable "vertex_ai_model" {
  description = "Vertex AI model name"
  type        = string
  default     = "vertex_ai/gemini-2.0-flash-exp"
}

variable "llm_provider" {
  description = "LLM provider (vertex_ai or openai)"
  type        = string
  default     = "vertex_ai"
}

variable "openai_api_key_secret_id" {
  description = "Secret Manager ID for OpenAI API key (optional, leave empty if not using OpenAI)"
  type        = string
  default     = ""
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS URL for JWT verification"
  type        = string
  default     = ""
}

variable "clerk_issuer" {
  description = "Clerk issuer URL"
  type        = string
  default     = ""
}

variable "frontend_url" {
  description = "Frontend Cloud Run URL (for CORS)"
  type        = string
  default     = ""
}

variable "cors_origins" {
  description = "Additional CORS origins (comma-separated)"
  type        = string
  default     = ""
}
