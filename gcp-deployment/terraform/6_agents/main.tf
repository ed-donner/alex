# =============================================================================
# GCP Cloud Run Agents - Equivalent to AWS Lambda
# =============================================================================

terraform {
  required_version = ">= 1.5.0"
  
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

# =============================================================================
# DATA SOURCES
# =============================================================================

data "google_project" "current" {
  project_id = var.project_id
}

# =============================================================================
# ARTIFACT REGISTRY REPOSITORY
# =============================================================================

resource "google_artifact_registry_repository" "agents" {
  location      = var.region
  repository_id = "alex-agents"
  description   = "Container images for Alex agents"
  format        = "DOCKER"
  
  labels = {
    environment = var.environment
    purpose     = "agents"
  }
}

# =============================================================================
# CLOUD RUN SERVICE - PLANNER AGENT
# =============================================================================

resource "google_cloud_run_v2_service" "planner" {
  name     = "alex-planner"
  location = var.region
  
  template {
    service_account = var.cloud_run_service_account
    
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }
    
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agents.repository_id}/planner:${var.image_tag}"
      
      ports {
        container_port = 8000
      }
      
      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
        cpu_idle = true
      }
      
      # Environment variables
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      
      env {
        name  = "INSTANCE_CONNECTION_NAME"
        value = var.db_connection_name
      }
      
      env {
        name  = "DATABASE_NAME"
        value = var.database_name
      }
      
      env {
        name  = "DATABASE_USER"
        value = var.database_user
      }
      
      env {
        name = "DB_PASSWORD_SECRET_ID"
        value = var.db_password_secret_id
      }
      
      env {
        name  = "PUBSUB_TOPIC"
        value = var.pubsub_topic
      }
      
      # Service URLs for other agents (set after deployment)
      env {
        name  = "TAGGER_SERVICE_URL"
        value = google_cloud_run_v2_service.tagger.uri
      }
      
      env {
        name  = "REPORTER_SERVICE_URL"
        value = google_cloud_run_v2_service.reporter.uri
      }
      
      env {
        name  = "CHARTER_SERVICE_URL"
        value = google_cloud_run_v2_service.charter.uri
      }
      
      env {
        name  = "RETIREMENT_SERVICE_URL"
        value = google_cloud_run_v2_service.retirement.uri
      }
      
      # LLM Configuration
      env {
        name  = "VERTEX_AI_MODEL"
        value = var.vertex_ai_model
      }
      
      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }
      
      # Secrets from Secret Manager
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = var.db_password_secret_id
            version = "latest"
          }
        }
      }
      
      # OpenAI API Key (only if secret ID is provided)
      dynamic "env" {
        for_each = var.openai_api_key_secret_id != "" ? [1] : []
        content {
          name = "OPENAI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = var.openai_api_key_secret_id
              version = "latest"
            }
          }
        }
      }
      
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 3
      }
      
      liveness_probe {
        http_get {
          path = "/health"
        }
        period_seconds    = 30
        failure_threshold = 3
      }
    }
    
    timeout = "900s"  # 15 minutes for orchestration
  }
  
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
  
  labels = {
    environment = var.environment
    agent       = "planner"
  }
}

# =============================================================================
# CLOUD RUN SERVICE - TAGGER AGENT
# =============================================================================

resource "google_cloud_run_v2_service" "tagger" {
  name     = "alex-tagger"
  location = var.region
  
  template {
    service_account = var.cloud_run_service_account
    
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }
    
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agents.repository_id}/tagger:${var.image_tag}"
      
      ports {
        container_port = 8000
      }
      
      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
        cpu_idle = true
      }
      
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      
      env {
        name  = "INSTANCE_CONNECTION_NAME"
        value = var.db_connection_name
      }
      
      env {
        name  = "DATABASE_NAME"
        value = var.database_name
      }
      
      env {
        name  = "DATABASE_USER"
        value = var.database_user
      }
      
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = var.db_password_secret_id
            version = "latest"
          }
        }
      }
      
      # LLM Configuration
      env {
        name  = "VERTEX_AI_MODEL"
        value = var.vertex_ai_model
      }
      
      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }
      
      # OpenAI API Key (only if secret ID is provided)
      dynamic "env" {
        for_each = var.openai_api_key_secret_id != "" ? [1] : []
        content {
          name = "OPENAI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = var.openai_api_key_secret_id
              version = "latest"
            }
          }
        }
      }
      
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 3
      }
    }
    
    timeout = "300s"
  }
  
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
  
  labels = {
    environment = var.environment
    agent       = "tagger"
  }
}

# =============================================================================
# CLOUD RUN SERVICE - REPORTER AGENT
# =============================================================================

resource "google_cloud_run_v2_service" "reporter" {
  name     = "alex-reporter"
  location = var.region
  
  template {
    service_account = var.cloud_run_service_account
    
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }
    
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agents.repository_id}/reporter:${var.image_tag}"
      
      ports {
        container_port = 8000
      }
      
      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
        cpu_idle = true
      }
      
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      
      env {
        name  = "INSTANCE_CONNECTION_NAME"
        value = var.db_connection_name
      }
      
      env {
        name  = "DATABASE_NAME"
        value = var.database_name
      }
      
      env {
        name  = "DATABASE_USER"
        value = var.database_user
      }
      
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = var.db_password_secret_id
            version = "latest"
          }
        }
      }
      
      # LLM Configuration
      env {
        name  = "VERTEX_AI_MODEL"
        value = var.vertex_ai_model
      }
      
      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }
      
      # OpenAI API Key (only if secret ID is provided)
      dynamic "env" {
        for_each = var.openai_api_key_secret_id != "" ? [1] : []
        content {
          name = "OPENAI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = var.openai_api_key_secret_id
              version = "latest"
            }
          }
        }
      }
      
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 3
      }
    }
    
    timeout = "600s"
  }
  
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
  
  labels = {
    environment = var.environment
    agent       = "reporter"
  }
}

# =============================================================================
# CLOUD RUN SERVICE - CHARTER AGENT
# =============================================================================

resource "google_cloud_run_v2_service" "charter" {
  name     = "alex-charter"
  location = var.region
  
  template {
    service_account = var.cloud_run_service_account
    
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }
    
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agents.repository_id}/charter:${var.image_tag}"
      
      ports {
        container_port = 8000
      }
      
      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
        cpu_idle = true
      }
      
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      
      env {
        name  = "INSTANCE_CONNECTION_NAME"
        value = var.db_connection_name
      }
      
      env {
        name  = "DATABASE_NAME"
        value = var.database_name
      }
      
      env {
        name  = "DATABASE_USER"
        value = var.database_user
      }
      
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = var.db_password_secret_id
            version = "latest"
          }
        }
      }
      
      # LLM Configuration
      env {
        name  = "VERTEX_AI_MODEL"
        value = var.vertex_ai_model
      }
      
      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }
      
      # OpenAI API Key (only if secret ID is provided)
      dynamic "env" {
        for_each = var.openai_api_key_secret_id != "" ? [1] : []
        content {
          name = "OPENAI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = var.openai_api_key_secret_id
              version = "latest"
            }
          }
        }
      }
      
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 3
      }
    }
    
    timeout = "600s"
  }
  
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
  
  labels = {
    environment = var.environment
    agent       = "charter"
  }
}

# =============================================================================
# CLOUD RUN SERVICE - RETIREMENT AGENT
# =============================================================================

resource "google_cloud_run_v2_service" "retirement" {
  name     = "alex-retirement"
  location = var.region
  
  template {
    service_account = var.cloud_run_service_account
    
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }
    
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agents.repository_id}/retirement:${var.image_tag}"
      
      ports {
        container_port = 8000
      }
      
      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
        cpu_idle = true
      }
      
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      
      env {
        name  = "INSTANCE_CONNECTION_NAME"
        value = var.db_connection_name
      }
      
      env {
        name  = "DATABASE_NAME"
        value = var.database_name
      }
      
      env {
        name  = "DATABASE_USER"
        value = var.database_user
      }
      
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = var.db_password_secret_id
            version = "latest"
          }
        }
      }
      
      # LLM Configuration
      env {
        name  = "VERTEX_AI_MODEL"
        value = var.vertex_ai_model
      }
      
      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }
      
      # OpenAI API Key (only if secret ID is provided)
      dynamic "env" {
        for_each = var.openai_api_key_secret_id != "" ? [1] : []
        content {
          name = "OPENAI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = var.openai_api_key_secret_id
              version = "latest"
            }
          }
        }
      }
      
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 3
      }
    }
    
    timeout = "600s"
  }
  
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
  
  labels = {
    environment = var.environment
    agent       = "retirement"
  }
}

# =============================================================================
# IAM - Allow Inter-Service Communication
# =============================================================================

resource "google_cloud_run_v2_service_iam_member" "planner_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.planner.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.cloud_run_service_account}"
}

resource "google_cloud_run_v2_service_iam_member" "tagger_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.tagger.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.cloud_run_service_account}"
}

resource "google_cloud_run_v2_service_iam_member" "reporter_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.reporter.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.cloud_run_service_account}"
}

resource "google_cloud_run_v2_service_iam_member" "charter_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.charter.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.cloud_run_service_account}"
}

resource "google_cloud_run_v2_service_iam_member" "retirement_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.retirement.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.cloud_run_service_account}"
}

# =============================================================================
# CLOUD RUN SERVICE - API (Backend for Frontend)
# =============================================================================

resource "google_cloud_run_v2_service" "api" {
  name     = "alex-api"
  location = var.region
  
  template {
    service_account = var.cloud_run_service_account
    
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }
    
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agents.repository_id}/api:${var.image_tag}"
      
      ports {
        container_port = 8080
      }
      
      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
        cpu_idle = true
      }
      
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      
      env {
        name  = "INSTANCE_CONNECTION_NAME"
        value = var.db_connection_name
      }
      
      env {
        name  = "DATABASE_NAME"
        value = var.database_name
      }
      
      env {
        name  = "DATABASE_USER"
        value = var.database_user
      }
      
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = var.db_password_secret_id
            version = "latest"
          }
        }
      }
      
      env {
        name  = "PUBSUB_TOPIC"
        value = var.pubsub_topic
      }
      
      env {
        name  = "CLERK_JWKS_URL"
        value = var.clerk_jwks_url
      }
      
      env {
        name  = "CLERK_ISSUER"
        value = var.clerk_issuer
      }
      
      env {
        name  = "FRONTEND_URL"
        value = var.frontend_url
      }
      
      env {
        name  = "CORS_ORIGINS"
        value = var.cors_origins
      }
      
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 3
      }
    }
    
    timeout = "60s"
  }
  
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
  
  labels = {
    environment = var.environment
    component   = "api"
  }
}

# IAM - Allow public access to API
resource "google_cloud_run_v2_service_iam_member" "api_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# UPDATE PUB/SUB SUBSCRIPTION TO PUSH TO PLANNER
# =============================================================================
# Note: The subscription is created in terraform/3_pubsub/
# We update it here to add the push endpoint after Cloud Run is deployed
# This requires the subscription to exist first (deploy terraform/3_pubsub first)

data "google_pubsub_subscription" "planner_subscription" {
  name = "alex-planner-subscription"
}

resource "google_pubsub_subscription" "planner_subscription_push" {
  name  = data.google_pubsub_subscription.planner_subscription.name
  topic = var.pubsub_topic
  
  push_config {
    push_endpoint = "${google_cloud_run_v2_service.planner.uri}/pubsub"
    
    oidc_token {
      service_account_email = var.cloud_run_service_account
    }
  }
  
  ack_deadline_seconds = 60
  message_retention_duration = "86400s"
  
  labels = {
    environment = var.environment
    agent       = "planner"
    managed_by  = "terraform"
  }
  
  depends_on = [google_cloud_run_v2_service.planner]
}
