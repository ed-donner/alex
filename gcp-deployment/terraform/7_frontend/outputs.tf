# =============================================================================
# OUTPUTS - Frontend
# =============================================================================

output "frontend_url" {
  description = "Frontend Cloud Run URL"
  value       = google_cloud_run_v2_service.frontend.uri
}

output "load_balancer_ip" {
  description = "Load balancer IP address"
  value       = var.enable_load_balancer ? google_compute_global_address.frontend[0].address : null
}

output "custom_domain_url" {
  description = "Custom domain URL"
  value       = var.custom_domain != "" ? "https://${var.custom_domain}" : null
}

output "clerk_publishable_key_secret_id" {
  description = "Secret Manager ID for Clerk publishable key"
  value       = "clerk-publishable-key"
}

output "clerk_secret_key_secret_id" {
  description = "Secret Manager ID for Clerk secret key"
  value       = "clerk-secret-key"
}

output "dns_nameservers" {
  description = "DNS nameservers (if zone created)"
  value       = var.create_dns_zone ? google_dns_managed_zone.main[0].name_servers : null
}
