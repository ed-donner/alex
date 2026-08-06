# =============================================================================
# GCP Permissions Setup - Equivalent to AWS IAM
# =============================================================================
# This Terraform configuration sets up service accounts and IAM bindings
# for the Multi-Agent SaaS application on GCP.
# =============================================================================

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  # Uncomment to use GCS backend for state storage
  # backend "gcs" {
  #   bucket = "your-terraform-state-bucket"
  #   prefix = "alex-multiagent/1_permissions"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
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
# SERVICE ACCOUNTS
# =============================================================================

# Vertex AI Service Account (equivalent to SageMaker execution role)
resource "google_service_account" "vertex_ai" {
  account_id   = "vertex-ai-sa"
  display_name = "Vertex AI Service Account"
  description  = "Service account for Vertex AI model training and inference"
  project      = var.project_id
}

# Cloud Run Service Account (equivalent to App Runner/Lambda execution role)
resource "google_service_account" "cloud_run" {
  account_id   = "cloud-run-sa"
  display_name = "Cloud Run Service Account"
  description  = "Service account for Cloud Run services (agents, backend)"
  project      = var.project_id
}

# Cloud Functions Service Account
resource "google_service_account" "cloud_functions" {
  account_id   = "cloud-functions-sa"
  display_name = "Cloud Functions Service Account"
  description  = "Service account for Cloud Functions (ingest, processing)"
  project      = var.project_id
}

# Cloud SQL Proxy Service Account
resource "google_service_account" "cloud_sql" {
  account_id   = "cloud-sql-sa"
  display_name = "Cloud SQL Service Account"
  description  = "Service account for Cloud SQL access"
  project      = var.project_id
}

# Storage Service Account
resource "google_service_account" "storage" {
  account_id   = "storage-sa"
  display_name = "Storage Service Account"
  description  = "Service account for Cloud Storage access"
  project      = var.project_id
}

# Deployment Service Account (for CI/CD)
resource "google_service_account" "deploy" {
  account_id   = "deploy-sa"
  display_name = "Deployment Service Account"
  description  = "Service account for CI/CD deployments (GitHub Actions)"
  project      = var.project_id
}

# =============================================================================
# IAM BINDINGS - Vertex AI Service Account
# =============================================================================

resource "google_project_iam_member" "vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.vertex_ai.email}"
}

resource "google_project_iam_member" "vertex_ai_admin" {
  project = var.project_id
  role    = "roles/aiplatform.admin"
  member  = "serviceAccount:${google_service_account.vertex_ai.email}"
}

resource "google_project_iam_member" "vertex_ai_storage" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.vertex_ai.email}"
}

# =============================================================================
# IAM BINDINGS - Cloud Run Service Account
# =============================================================================

resource "google_project_iam_member" "cloud_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "cloud_run_vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "cloud_run_secretmanager" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "cloud_run_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "cloud_run_storage" {
  project = var.project_id
  role    = "roles/storage.objectUser"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# =============================================================================
# IAM BINDINGS - Cloud Functions Service Account
# =============================================================================

resource "google_project_iam_member" "functions_invoker" {
  project = var.project_id
  role    = "roles/cloudfunctions.invoker"
  member  = "serviceAccount:${google_service_account.cloud_functions.email}"
}

resource "google_project_iam_member" "functions_vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cloud_functions.email}"
}

resource "google_project_iam_member" "functions_storage" {
  project = var.project_id
  role    = "roles/storage.objectUser"
  member  = "serviceAccount:${google_service_account.cloud_functions.email}"
}

resource "google_project_iam_member" "functions_secretmanager" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_functions.email}"
}

# =============================================================================
# IAM BINDINGS - Cloud SQL Service Account
# =============================================================================

resource "google_project_iam_member" "sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_sql.email}"
}

# =============================================================================
# IAM BINDINGS - Storage Service Account
# =============================================================================

resource "google_project_iam_member" "storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.storage.email}"
}

# =============================================================================
# IAM BINDINGS - Deploy Service Account
# =============================================================================

resource "google_project_iam_member" "deploy_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "deploy_functions_admin" {
  project = var.project_id
  role    = "roles/cloudfunctions.admin"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "deploy_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "deploy_artifact_admin" {
  project = var.project_id
  role    = "roles/artifactregistry.admin"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "deploy_cloudbuild" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.builder"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "deploy_service_account_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

# =============================================================================
# WORKLOAD IDENTITY FOR GITHUB ACTIONS (Optional but recommended)
# =============================================================================

resource "google_iam_workload_identity_pool" "github" {
  count                     = var.enable_github_workload_identity ? 1 : 0
  project                   = var.project_id
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Workload Identity Pool for GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count                              = var.enable_github_workload_identity ? 1 : 0
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub Provider"
  
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }
  
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_workload_identity" {
  count              = var.enable_github_workload_identity ? 1 : 0
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.repository/${var.github_repo}"
}

# =============================================================================
# ARTIFACT REGISTRY REPOSITORY
# =============================================================================

resource "google_artifact_registry_repository" "main" {
  location      = var.region
  repository_id = "alex-containers"
  description   = "Docker repository for Alex Multi-Agent SaaS"
  format        = "DOCKER"
  project       = var.project_id
}

# Grant Cloud Run service account access to pull images
resource "google_artifact_registry_repository_iam_member" "cloud_run_reader" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.main.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Grant deploy service account access to push images
resource "google_artifact_registry_repository_iam_member" "deploy_writer" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.main.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deploy.email}"
}
