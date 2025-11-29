# =============================================================================
# OUTPUTS - Cloud SQL Database
# =============================================================================

output "instance_name" {
  description = "Cloud SQL instance name"
  value       = google_sql_database_instance.main.name
}

output "instance_connection_name" {
  description = "Cloud SQL connection name for Cloud SQL Proxy"
  value       = google_sql_database_instance.main.connection_name
}

output "private_ip_address" {
  description = "Private IP address of the database"
  value       = google_sql_database_instance.main.private_ip_address
}

output "public_ip_address" {
  description = "Public IP address of the database (if enabled)"
  value       = var.enable_public_ip ? google_sql_database_instance.main.public_ip_address : null
}

output "database_name" {
  description = "Database name"
  value       = google_sql_database.alex.name
}

output "database_user" {
  description = "Database user"
  value       = google_sql_user.app_user.name
}

output "db_password_secret_id" {
  description = "Secret Manager ID for database password"
  value       = google_secret_manager_secret.db_password.secret_id
}

output "db_connection_string_secret_id" {
  description = "Secret Manager ID for database connection string"
  value       = google_secret_manager_secret.db_connection_string.secret_id
}

output "read_replica_ip" {
  description = "Private IP of read replica"
  value       = var.create_read_replica ? google_sql_database_instance.read_replica[0].private_ip_address : null
}

output "vpc_network_id" {
  description = "VPC network ID"
  value       = var.create_vpc ? google_compute_network.main[0].id : var.vpc_network_id
}

output "vpc_subnet_id" {
  description = "VPC subnet ID"
  value       = var.create_vpc ? google_compute_subnetwork.main[0].id : null
}
