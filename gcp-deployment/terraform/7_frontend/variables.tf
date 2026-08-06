# =============================================================================
# VARIABLES - Frontend
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

variable "artifact_registry_url" {
  description = "Artifact Registry URL"
  type        = string
}

variable "image_tag" {
  description = "Container image tag"
  type        = string
  default     = "latest"
}

variable "cloud_run_service_account" {
  description = "Service account email for Cloud Run"
  type        = string
}

variable "backend_api_url" {
  description = "Backend API URL (orchestrator)"
  type        = string
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
}

variable "cpu_limit" {
  description = "CPU limit"
  type        = string
  default     = "1"
}

variable "memory_limit" {
  description = "Memory limit"
  type        = string
  default     = "1Gi"
}

variable "enable_load_balancer" {
  description = "Enable Cloud Load Balancer"
  type        = bool
  default     = false
}

variable "enable_cdn" {
  description = "Enable Cloud CDN"
  type        = bool
  default     = false
}

variable "custom_domain" {
  description = "Custom domain name"
  type        = string
  default     = ""
}

variable "create_dns_zone" {
  description = "Create Cloud DNS zone"
  type        = bool
  default     = false
}
