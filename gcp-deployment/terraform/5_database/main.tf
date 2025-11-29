# =============================================================================
# GCP Cloud SQL Setup - Equivalent to AWS RDS PostgreSQL
# =============================================================================

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# =============================================================================
# RANDOM PASSWORD GENERATION
# =============================================================================

resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# =============================================================================
# VPC NETWORK (if not using existing)
# =============================================================================

resource "google_compute_network" "main" {
  count                   = var.create_vpc ? 1 : 0
  name                    = "alex-vpc"
  auto_create_subnetworks = false
  project                 = var.project_id
}

resource "google_compute_subnetwork" "main" {
  count         = var.create_vpc ? 1 : 0
  name          = "alex-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.main[0].id
  
  private_ip_google_access = true
}

# =============================================================================
# PRIVATE SERVICE CONNECTION FOR CLOUD SQL
# =============================================================================

resource "google_compute_global_address" "private_ip_address" {
  name          = "alex-db-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = var.create_vpc ? google_compute_network.main[0].id : var.vpc_network_id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = var.create_vpc ? google_compute_network.main[0].id : var.vpc_network_id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]
}

# =============================================================================
# CLOUD SQL POSTGRESQL INSTANCE
# =============================================================================

resource "google_sql_database_instance" "main" {
  name             = "alex-postgres"
  database_version = "POSTGRES_15"
  region           = var.region
  project          = var.project_id
  
  deletion_protection = var.environment == "prod"
  
  depends_on = [google_service_networking_connection.private_vpc_connection]
  
  settings {
    tier              = var.db_tier
    availability_type = var.high_availability ? "REGIONAL" : "ZONAL"
    disk_size         = var.disk_size_gb
    disk_type         = "PD_SSD"
    disk_autoresize   = true
    
    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = var.environment == "prod"
      backup_retention_settings {
        retained_backups = var.environment == "prod" ? 30 : 7
      }
    }
    
    ip_configuration {
      ipv4_enabled    = var.enable_public_ip
      private_network = var.create_vpc ? google_compute_network.main[0].id : var.vpc_network_id
      require_ssl     = true
      
      dynamic "authorized_networks" {
        for_each = var.authorized_networks
        content {
          name  = authorized_networks.value.name
          value = authorized_networks.value.cidr
        }
      }
    }
    
    database_flags {
      name  = "max_connections"
      value = var.max_connections
    }
    
    database_flags {
      name  = "log_min_duration_statement"
      value = "1000"  # Log queries > 1 second
    }
    
    maintenance_window {
      day          = 7  # Sunday
      hour         = 4  # 4 AM
      update_track = "stable"
    }
    
    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = true
    }
    
    user_labels = {
      environment = var.environment
      app         = "alex"
    }
  }
}

# =============================================================================
# DATABASE
# =============================================================================

resource "google_sql_database" "alex" {
  name     = "alex"
  instance = google_sql_database_instance.main.name
  project  = var.project_id
}

# =============================================================================
# DATABASE USER
# =============================================================================

resource "google_sql_user" "app_user" {
  name     = "alex_app"
  instance = google_sql_database_instance.main.name
  password = random_password.db_password.result
  project  = var.project_id
}

# =============================================================================
# READ REPLICA (Optional for production)
# =============================================================================

resource "google_sql_database_instance" "read_replica" {
  count                = var.create_read_replica ? 1 : 0
  name                 = "alex-postgres-replica"
  master_instance_name = google_sql_database_instance.main.name
  database_version     = "POSTGRES_15"
  region               = var.region
  project              = var.project_id
  
  replica_configuration {
    failover_target = false
  }
  
  settings {
    tier            = var.replica_tier
    disk_size       = var.disk_size_gb
    disk_type       = "PD_SSD"
    disk_autoresize = true
    
    ip_configuration {
      ipv4_enabled    = var.enable_public_ip
      private_network = var.create_vpc ? google_compute_network.main[0].id : var.vpc_network_id
      require_ssl     = true
    }
    
    user_labels = {
      environment = var.environment
      app         = "alex"
      role        = "read-replica"
    }
  }
}

# =============================================================================
# SECRET MANAGER FOR DATABASE CREDENTIALS
# =============================================================================

resource "google_secret_manager_secret" "db_password" {
  secret_id = "alex-db-password"
  
  replication {
    auto {}
  }
  
  labels = {
    environment = var.environment
    service     = "database"
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

resource "google_secret_manager_secret" "db_connection_string" {
  secret_id = "alex-db-connection-string"
  
  replication {
    auto {}
  }
  
  labels = {
    environment = var.environment
    service     = "database"
  }
}

resource "google_secret_manager_secret_version" "db_connection_string" {
  secret      = google_secret_manager_secret.db_connection_string.id
  secret_data = "postgresql://alex_app:${random_password.db_password.result}@/${google_sql_database.alex.name}?host=/cloudsql/${google_sql_database_instance.main.connection_name}"
}

# =============================================================================
# IAM FOR SECRET ACCESS
# =============================================================================

resource "google_secret_manager_secret_iam_member" "db_password_accessor" {
  secret_id = google_secret_manager_secret.db_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.cloud_run_service_account}"
}

resource "google_secret_manager_secret_iam_member" "db_connection_accessor" {
  secret_id = google_secret_manager_secret.db_connection_string.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.cloud_run_service_account}"
}
