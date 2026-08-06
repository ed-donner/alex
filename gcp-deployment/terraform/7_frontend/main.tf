# =============================================================================
# GCP Frontend Deployment - Equivalent to AWS App Runner + CloudFront
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
# CLOUD RUN SERVICE - FRONTEND
# =============================================================================

resource "google_cloud_run_v2_service" "frontend" {
  name     = "frontend"
  location = var.region
  
  template {
    service_account = var.cloud_run_service_account
    
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }
    
    containers {
      image = "${var.artifact_registry_url}/frontend:${var.image_tag}"
      
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
        name  = "NEXT_PUBLIC_API_URL"
        value = var.backend_api_url
      }
      
      env {
        name  = "NODE_ENV"
        value = "production"
      }
      
      # Clerk keys are baked into the build image at build time
      # NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is already in the image
      # CLERK_SECRET_KEY is only needed by backend API, not frontend
      
      startup_probe {
        http_get {
          path = "/"
          port = 8080
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 5
      }
      
      liveness_probe {
        http_get {
          path = "/"
          port = 8080
        }
        period_seconds    = 30
        failure_threshold = 3
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
    component   = "frontend"
  }
}

# =============================================================================
# IAM - Allow Public Access
# =============================================================================

resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# SECRET MANAGER FOR CLERK KEYS
# =============================================================================
# Secrets are created by the deployment script and referenced by name
# IAM bindings are managed via gcloud commands in the deployment script

# =============================================================================
# LOAD BALANCER WITH CLOUD CDN (Optional - for custom domain)
# =============================================================================

resource "google_compute_region_network_endpoint_group" "frontend_neg" {
  count                 = var.enable_load_balancer ? 1 : 0
  name                  = "frontend-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region
  
  cloud_run {
    service = google_cloud_run_v2_service.frontend.name
  }
}

resource "google_compute_backend_service" "frontend" {
  count       = var.enable_load_balancer ? 1 : 0
  name        = "frontend-backend"
  protocol    = "HTTP"
  port_name   = "http"
  timeout_sec = 60
  
  enable_cdn = var.enable_cdn
  
  dynamic "cdn_policy" {
    for_each = var.enable_cdn ? [1] : []
    content {
      cache_mode                   = "CACHE_ALL_STATIC"
      default_ttl                  = 3600
      max_ttl                      = 86400
      client_ttl                   = 3600
      negative_caching             = true
      signed_url_cache_max_age_sec = 0
      
      cache_key_policy {
        include_host          = true
        include_protocol      = true
        include_query_string  = true
      }
    }
  }
  
  backend {
    group = google_compute_region_network_endpoint_group.frontend_neg[0].id
  }
}

resource "google_compute_url_map" "frontend" {
  count           = var.enable_load_balancer ? 1 : 0
  name            = "frontend-url-map"
  default_service = google_compute_backend_service.frontend[0].id
}

# =============================================================================
# SSL CERTIFICATE (for custom domain)
# =============================================================================

resource "google_compute_managed_ssl_certificate" "frontend" {
  count = var.enable_load_balancer && var.custom_domain != "" ? 1 : 0
  name  = "frontend-ssl-cert"
  
  managed {
    domains = [var.custom_domain]
  }
}

resource "google_compute_target_https_proxy" "frontend" {
  count            = var.enable_load_balancer && var.custom_domain != "" ? 1 : 0
  name             = "frontend-https-proxy"
  url_map          = google_compute_url_map.frontend[0].id
  ssl_certificates = [google_compute_managed_ssl_certificate.frontend[0].id]
}

resource "google_compute_global_forwarding_rule" "frontend_https" {
  count                 = var.enable_load_balancer && var.custom_domain != "" ? 1 : 0
  name                  = "frontend-https-forwarding"
  target                = google_compute_target_https_proxy.frontend[0].id
  port_range            = "443"
  ip_address            = google_compute_global_address.frontend[0].address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

resource "google_compute_global_address" "frontend" {
  count = var.enable_load_balancer ? 1 : 0
  name  = "frontend-ip"
}

# HTTP to HTTPS redirect
resource "google_compute_url_map" "frontend_redirect" {
  count = var.enable_load_balancer && var.custom_domain != "" ? 1 : 0
  name  = "frontend-http-redirect"
  
  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "frontend_redirect" {
  count   = var.enable_load_balancer && var.custom_domain != "" ? 1 : 0
  name    = "frontend-http-proxy"
  url_map = google_compute_url_map.frontend_redirect[0].id
}

resource "google_compute_global_forwarding_rule" "frontend_http" {
  count                 = var.enable_load_balancer && var.custom_domain != "" ? 1 : 0
  name                  = "frontend-http-forwarding"
  target                = google_compute_target_http_proxy.frontend_redirect[0].id
  port_range            = "80"
  ip_address            = google_compute_global_address.frontend[0].address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# =============================================================================
# CLOUD DNS (Optional)
# =============================================================================

resource "google_dns_managed_zone" "main" {
  count       = var.create_dns_zone ? 1 : 0
  name        = "alex-zone"
  dns_name    = "${var.custom_domain}."
  description = "DNS zone for Alex frontend"
}

resource "google_dns_record_set" "frontend" {
  count        = var.enable_load_balancer && var.create_dns_zone ? 1 : 0
  name         = "${var.custom_domain}."
  managed_zone = google_dns_managed_zone.main[0].name
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_global_address.frontend[0].address]
}
