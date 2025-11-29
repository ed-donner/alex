# =============================================================================
# VARIABLES - GCP Permissions
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

variable "enable_github_workload_identity" {
  description = "Enable Workload Identity Federation for GitHub Actions"
  type        = bool
  default     = false
}

variable "github_repo" {
  description = "GitHub repository in format 'owner/repo' for Workload Identity"
  type        = string
  default     = ""
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}
