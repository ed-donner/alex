# =============================================================================
# VARIABLES - Vertex AI
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

variable "vertex_ai_service_account" {
  description = "Service account email for Vertex AI"
  type        = string
}

variable "create_workbench" {
  description = "Create Vertex AI Workbench instance"
  type        = bool
  default     = false
}

variable "workbench_machine_type" {
  description = "Machine type for Workbench instance"
  type        = string
  default     = "n1-standard-4"
}

variable "workbench_gpu" {
  description = "Install GPU driver on Workbench"
  type        = bool
  default     = false
}

variable "create_private_network" {
  description = "Create private VPC network for Vertex AI"
  type        = bool
  default     = false
}

variable "create_feature_store" {
  description = "Create Vertex AI Feature Store"
  type        = bool
  default     = false
}

variable "enable_model_monitoring" {
  description = "Enable model monitoring scheduler"
  type        = bool
  default     = false
}

variable "monitoring_endpoint_url" {
  description = "URL for model monitoring endpoint"
  type        = string
  default     = ""
}

variable "enable_anthropic_api" {
  description = "Enable Anthropic API key secret (set to false to use Gemini 2.0 Flash instead)"
  type        = bool
  default     = false
}
