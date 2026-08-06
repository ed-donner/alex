# =============================================================================
# OUTPUTS - Pub/Sub Job Queue
# =============================================================================

output "topic_name" {
  description = "Pub/Sub topic name"
  value       = google_pubsub_topic.job_queue.name
}

output "topic_id" {
  description = "Pub/Sub topic ID"
  value       = google_pubsub_topic.job_queue.id
}

output "topic_path" {
  description = "Full Pub/Sub topic path"
  value       = google_pubsub_topic.job_queue.id
}

output "subscription_name" {
  description = "Pub/Sub subscription name"
  value       = google_pubsub_subscription.planner_subscription.name
}

output "subscription_id" {
  description = "Pub/Sub subscription ID"
  value       = google_pubsub_subscription.planner_subscription.id
}

output "subscription_path" {
  description = "Full Pub/Sub subscription path"
  value       = google_pubsub_subscription.planner_subscription.id
}

