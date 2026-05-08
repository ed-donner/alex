output "aurora_cluster_arn" {
  description = "ARN of the Aurora cluster"
  value       = aws_rds_cluster.aurora.arn
}

output "aurora_cluster_endpoint" {
  description = "Writer endpoint for the Aurora cluster"
  value       = aws_rds_cluster.aurora.endpoint
}

output "aurora_secret_arn" {
  description = "ARN of the Secrets Manager secret containing database credentials"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "database_name" {
  description = "Name of the database"
  value       = aws_rds_cluster.aurora.database_name
}

output "lambda_role_arn" {
  description = "ARN of the IAM role for Lambda functions to access Aurora"
  value       = aws_iam_role.lambda_aurora_role.arn
}

output "data_api_enabled" {
  description = "Status of Data API"
  value       = aws_rds_cluster.aurora.enable_http_endpoint ? "Enabled" : "Disabled"
}

output "setup_instructions" {
  description = "Instructions for setting up the database"
  value       = <<-EOT
    
    ✅ Aurora Serverless v2 cluster deployed successfully!
    
    Database Details:
    - Cluster: ${aws_rds_cluster.aurora.cluster_identifier}
    - Database: ${aws_rds_cluster.aurora.database_name}
    - Data API: Enabled
    
    Add the following to your .env file:
    AURORA_CLUSTER_ARN=${aws_rds_cluster.aurora.arn}
    AURORA_SECRET_ARN=${aws_secretsmanager_secret.db_credentials.arn}
    
    Test the Data API connection:
    aws rds-data execute-statement \
      --resource-arn ${aws_rds_cluster.aurora.arn} \
      --secret-arn ${aws_secretsmanager_secret.db_credentials.arn} \
      --database alex \
      --sql "SELECT version()"
    
    To set up the database schema:
    cd backend/database
    uv run run_migrations.py
    
    To load sample data:
    uv run reset_db.py --with-test-data
    
    💰 Cost Management:
    - Current scaling: ${var.min_capacity} - ${var.max_capacity} ACUs
    - Estimated cost: ~$43/month minimum
    - To pause: Set min_capacity to 0 (cluster will pause after 5 minutes of inactivity)
  EOT
}