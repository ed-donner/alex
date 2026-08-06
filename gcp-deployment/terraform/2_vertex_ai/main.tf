# =============================================================================
# GCP Vertex AI Setup - Equivalent to AWS SageMaker/Bedrock
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
# STORAGE FOR MODEL ARTIFACTS
# =============================================================================

resource "google_storage_bucket" "model_artifacts" {
  name          = "${var.project_id}-model-artifacts"
  location      = var.region
  force_destroy = var.environment != "prod"
  
  uniform_bucket_level_access = true
  
  versioning {
    enabled = true
  }
  
  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
  
  labels = {
    environment = var.environment
    purpose     = "model-artifacts"
  }
}

resource "google_storage_bucket" "training_data" {
  name          = "${var.project_id}-training-data"
  location      = var.region
  force_destroy = var.environment != "prod"
  
  uniform_bucket_level_access = true
  
  labels = {
    environment = var.environment
    purpose     = "training-data"
  }
}

# =============================================================================
# SECRET MANAGER FOR API KEYS
# =============================================================================

# Anthropic API Key (Optional - only needed if using Claude via Anthropic API)
# For cost-effective option, use Gemini 2.0 Flash via Vertex AI instead
resource "google_secret_manager_secret" "anthropic_api_key" {
  count     = var.enable_anthropic_api ? 1 : 0
  secret_id = "anthropic-api-key"
  
  replication {
    auto {}
  }
  
  labels = {
    environment = var.environment
    service     = "vertex-ai"
  }
}

# Note: You'll need to add the secret version manually or via CLI:
# gcloud secrets versions add anthropic-api-key --data-file=./api-key.txt

resource "google_secret_manager_secret" "openai_api_key" {
  secret_id = "openai-api-key"
  
  replication {
    auto {}
  }
  
  labels = {
    environment = var.environment
    service     = "vertex-ai"
  }
}

# =============================================================================
# VERTEX AI WORKBENCH (Optional - for development)
# =============================================================================

resource "google_notebooks_instance" "workbench" {
  count        = var.create_workbench ? 1 : 0
  name         = "alex-workbench"
  location     = "${var.region}-a"
  machine_type = var.workbench_machine_type
  
  vm_image {
    project      = "deeplearning-platform-release"
    image_family = "common-cpu-notebooks"
  }
  
  install_gpu_driver = var.workbench_gpu
  
  service_account = var.vertex_ai_service_account
  
  metadata = {
    proxy-mode = "service_account"
  }
  
  labels = {
    environment = var.environment
  }
}

# =============================================================================
# VERTEX AI TENSORBOARD (for experiment tracking)
# =============================================================================

resource "google_vertex_ai_tensorboard" "main" {
  display_name = "alex-tensorboard"
  description  = "TensorBoard instance for Alex Multi-Agent SaaS"
  region       = var.region
  
  labels = {
    environment = var.environment
  }
}

# =============================================================================
# VPC NETWORK FOR VERTEX AI (Optional - for private endpoints)
# =============================================================================

resource "google_compute_network" "vertex_ai_vpc" {
  count                   = var.create_private_network ? 1 : 0
  name                    = "vertex-ai-vpc"
  auto_create_subnetworks = false
  project                 = var.project_id
}

resource "google_compute_subnetwork" "vertex_ai_subnet" {
  count         = var.create_private_network ? 1 : 0
  name          = "vertex-ai-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vertex_ai_vpc[0].id
  
  private_ip_google_access = true
}

# VPC Peering for Vertex AI
resource "google_compute_global_address" "vertex_ai_peering" {
  count         = var.create_private_network ? 1 : 0
  name          = "vertex-ai-peering-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vertex_ai_vpc[0].id
}

resource "google_service_networking_connection" "vertex_ai_peering" {
  count                   = var.create_private_network ? 1 : 0
  network                 = google_compute_network.vertex_ai_vpc[0].id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.vertex_ai_peering[0].name]
}

# =============================================================================
# VERTEX AI FEATURE STORE (Optional)
# =============================================================================

resource "google_vertex_ai_featurestore" "main" {
  count  = var.create_feature_store ? 1 : 0
  name   = "alex_featurestore"
  region = var.region
  
  online_serving_config {
    fixed_node_count = 1
  }
  
  labels = {
    environment = var.environment
  }
}

# =============================================================================
# IAM FOR SECRETS ACCESS
# =============================================================================

resource "google_secret_manager_secret_iam_member" "anthropic_accessor" {
  count     = var.enable_anthropic_api ? 1 : 0
  secret_id = google_secret_manager_secret.anthropic_api_key[0].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.vertex_ai_service_account}"
}

resource "google_secret_manager_secret_iam_member" "openai_accessor" {
  secret_id = google_secret_manager_secret.openai_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.vertex_ai_service_account}"
}

# =============================================================================
# CLOUD SCHEDULER FOR MODEL MONITORING (Optional)
# =============================================================================

resource "google_cloud_scheduler_job" "model_monitoring" {
  count       = var.enable_model_monitoring ? 1 : 0
  name        = "model-monitoring-job"
  description = "Trigger model monitoring checks"
  schedule    = "0 */6 * * *"  # Every 6 hours
  time_zone   = "UTC"
  region      = var.region
  
  http_target {
    http_method = "POST"
    uri         = var.monitoring_endpoint_url
    
    oidc_token {
      service_account_email = var.vertex_ai_service_account
    }
  }
}
