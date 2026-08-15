output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.researcher.repository_url
}

output "researcher_url" {
  description = "Public HTTPS URL of the researcher Lambda"
  value       = try(aws_lambda_function_url.researcher[0].function_url, "Not created yet - run 'uv run deploy.py'")
}

output "researcher_function_name" {
  description = "Name of the researcher Lambda function"
  value       = try(aws_lambda_function.researcher[0].function_name, "Not created yet")
}

output "scheduler_status" {
  description = "Status of the automated scheduler"
  value = !local.researcher_deployed ? "Disabled - deploy the researcher image first" : (
    var.scheduler_enabled ? "Enabled - Running ${var.schedule_expression}" : "Disabled"
  )
}

output "setup_instructions" {
  description = "Instructions for completing setup"
  value = local.researcher_deployed ? format(
    "✅ Researcher service deployed successfully!\n\nService URL: %s\n\nTest the researcher:\ncurl %s/health\n\n%s",
    aws_lambda_function_url.researcher[0].function_url,
    trimsuffix(aws_lambda_function_url.researcher[0].function_url, "/"),
    var.scheduler_enabled ? "⏰ Automated research is running" : "💡 To enable automated research, set scheduler_enabled = true"
  ) : "Run 'uv run deploy.py' to build, push, and deploy the researcher image."
}
