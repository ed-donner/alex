# =============================================================================
# VARIABLES - Cloud SQL Database
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

variable "create_vpc" {
  description = "Create new VPC for database"
  type        = bool
  default     = true
}

variable "vpc_network_id" {
  description = "Existing VPC network ID (if create_vpc is false)"
  type        = string
  default     = ""
}

variable "db_tier" {
  description = "Cloud SQL instance tier"
  type        = string
  default     = "db-custom-2-4096"  # 2 vCPU, 4GB RAM
}

variable "disk_size_gb" {
  description = "Database disk size in GB"
  type        = number
  default     = 20
}

variable "max_connections" {
  description = "Maximum database connections"
  type        = string
  default     = "100"
}

variable "high_availability" {
  description = "Enable high availability (multi-zone)"
  type        = bool
  default     = false
}

variable "enable_public_ip" {
  description = "Enable public IP for database"
  type        = bool
  default     = false
}

variable "authorized_networks" {
  description = "List of authorized networks for public access"
  type = list(object({
    name = string
    cidr = string
  }))
  default = []
}

variable "create_read_replica" {
  description = "Create read replica"
  type        = bool
  default     = false
}

variable "replica_tier" {
  description = "Cloud SQL read replica tier"
  type        = string
  default     = "db-custom-1-2048"
}

variable "cloud_run_service_account" {
  description = "Cloud Run service account email for secret access"
  type        = string
}
