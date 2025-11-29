# =============================================================================
# OUTPUTS - Cloud Run Agents
# =============================================================================

output "artifact_registry_repository" {
  description = "Artifact Registry repository name"
  value       = google_artifact_registry_repository.agents.repository_id
}

output "artifact_registry_url" {
  description = "Full Artifact Registry URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agents.repository_id}"
}

output "planner_service_url" {
  description = "Planner agent Cloud Run URL"
  value       = google_cloud_run_v2_service.planner.uri
}

output "tagger_service_url" {
  description = "Tagger agent Cloud Run URL"
  value       = google_cloud_run_v2_service.tagger.uri
}

output "reporter_service_url" {
  description = "Reporter agent Cloud Run URL"
  value       = google_cloud_run_v2_service.reporter.uri
}

output "charter_service_url" {
  description = "Charter agent Cloud Run URL"
  value       = google_cloud_run_v2_service.charter.uri
}

output "retirement_service_url" {
  description = "Retirement agent Cloud Run URL"
  value       = google_cloud_run_v2_service.retirement.uri
}

output "api_service_url" {
  description = "Backend API Cloud Run URL"
  value       = google_cloud_run_v2_service.api.uri
}

output "all_service_urls" {
  description = "All agent service URLs"
  value = {
    api       = google_cloud_run_v2_service.api.uri
    planner   = google_cloud_run_v2_service.planner.uri
    tagger    = google_cloud_run_v2_service.tagger.uri
    reporter  = google_cloud_run_v2_service.reporter.uri
    charter   = google_cloud_run_v2_service.charter.uri
    retirement = google_cloud_run_v2_service.retirement.uri
  }
}

output "pubsub_subscription_name" {
  description = "Pub/Sub subscription name for planner"
  value       = data.google_pubsub_subscription.planner_subscription.name
}
