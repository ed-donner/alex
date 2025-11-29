# =============================================================================
# PUB/SUB - Job Queue for Agent Orchestration
# =============================================================================

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Pub/Sub Topic for job queue
resource "google_pubsub_topic" "job_queue" {
  name = "alex-job-queue"

  labels = {
    environment = var.environment
    managed_by = "terraform"
  }
}

# Subscription for Planner agent (push subscription)
# Note: Push endpoint will be set after Cloud Run service is deployed in Phase 3
# For now, we'll create a pull subscription that can be converted to push later
resource "google_pubsub_subscription" "planner_subscription" {
  name  = "alex-planner-subscription"
  topic = google_pubsub_topic.job_queue.name

  # Message retention: 24 hours
  message_retention_duration = "86400s"
  
  # Acknowledge deadline: 60 seconds
  ack_deadline_seconds = 60

  # Enable message ordering (optional, but good for job processing)
  enable_message_ordering = false

  # Retry policy
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Expiration policy: never expire
  expiration_policy {
    ttl = ""
  }

  labels = {
    environment = var.environment
    managed_by = "terraform"
  }
}

# IAM binding: Allow Cloud Run service account to publish messages
resource "google_pubsub_topic_iam_member" "publisher" {
  topic  = google_pubsub_topic.job_queue.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${var.cloud_run_service_account}"
}

# IAM binding: Allow Cloud Run service account to subscribe
resource "google_pubsub_subscription_iam_member" "subscriber" {
  subscription = google_pubsub_subscription.planner_subscription.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${var.cloud_run_service_account}"
}

