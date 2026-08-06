# =============================================================================
# OUTPUTS - GCP Permissions
# =============================================================================

output "vertex_ai_service_account_email" {
  description = "Vertex AI Service Account email"
  value       = google_service_account.vertex_ai.email
}

output "cloud_run_service_account_email" {
  description = "Cloud Run Service Account email"
  value       = google_service_account.cloud_run.email
}

output "cloud_functions_service_account_email" {
  description = "Cloud Functions Service Account email"
  value       = google_service_account.cloud_functions.email
}

output "cloud_sql_service_account_email" {
  description = "Cloud SQL Service Account email"
  value       = google_service_account.cloud_sql.email
}

output "storage_service_account_email" {
  description = "Storage Service Account email"
  value       = google_service_account.storage.email
}

output "deploy_service_account_email" {
  description = "Deployment Service Account email"
  value       = google_service_account.deploy.email
}

output "artifact_registry_repository" {
  description = "Artifact Registry repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.name}"
}

output "workload_identity_pool_provider" {
  description = "Workload Identity Pool Provider for GitHub Actions"
  value       = var.enable_github_workload_identity ? google_iam_workload_identity_pool_provider.github[0].name : null
}

output "project_number" {
  description = "GCP Project Number"
  value       = data.google_project.current.number
}
