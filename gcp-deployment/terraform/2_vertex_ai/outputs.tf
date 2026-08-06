# =============================================================================
# OUTPUTS - Vertex AI
# =============================================================================

output "model_artifacts_bucket" {
  description = "GCS bucket for model artifacts"
  value       = google_storage_bucket.model_artifacts.name
}

output "training_data_bucket" {
  description = "GCS bucket for training data"
  value       = google_storage_bucket.training_data.name
}

output "anthropic_api_key_secret_id" {
  description = "Secret Manager ID for Anthropic API key"
  value       = google_secret_manager_secret.anthropic_api_key.secret_id
}

output "openai_api_key_secret_id" {
  description = "Secret Manager ID for OpenAI API key"
  value       = google_secret_manager_secret.openai_api_key.secret_id
}

output "tensorboard_name" {
  description = "Vertex AI TensorBoard instance name"
  value       = google_vertex_ai_tensorboard.main.name
}

output "workbench_url" {
  description = "Vertex AI Workbench URL"
  value       = var.create_workbench ? google_notebooks_instance.workbench[0].proxy_uri : null
}

output "vpc_network_id" {
  description = "VPC network ID for Vertex AI"
  value       = var.create_private_network ? google_compute_network.vertex_ai_vpc[0].id : null
}

output "feature_store_id" {
  description = "Vertex AI Feature Store ID"
  value       = var.create_feature_store ? google_vertex_ai_featurestore.main[0].id : null
}
