output "aurora_cluster_arn" {
  description = "ARN of the Aurora Express cluster (set by bootstrap/setup_aurora_express.py)"
  value       = var.aurora_cluster_arn
}

output "aurora_secret_arn" {
  description = "ARN of the Secrets Manager secret containing database credentials"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "lambda_role_arn" {
  description = "ARN of the IAM role for Lambda functions to access Aurora"
  value       = aws_iam_role.lambda_aurora_role.arn
}

output "database_name" {
  description = "Application database name"
  value       = var.database_name
}
