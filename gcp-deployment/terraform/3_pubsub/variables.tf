# =============================================================================
# VARIABLES - Pub/Sub Job Queue
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

variable "cloud_run_service_account" {
  description = "Cloud Run service account email for Pub/Sub permissions"
  type        = string
}

