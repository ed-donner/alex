output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.researcher.repository_url
}

output "app_runner_service_url" {
  description = "URL of the App Runner service"
  value       = try("https://${aws_apprunner_service.researcher.service_url}", "Not created yet - run 'terraform apply' after deploying Docker image")
}

output "app_runner_service_id" {
  description = "ID of the App Runner service"
  value       = try(aws_apprunner_service.researcher.id, "Not created yet")
}

output "scheduler_status" {
  description = "Status of the automated scheduler"
  value       = var.scheduler_enabled ? "Enabled - Running every 2 hours" : "Disabled"
}

output "setup_instructions" {
  description = "Instructions for completing setup"
  value       = <<-EOT
    
    ✅ Researcher service deployed successfully!
    
    Service URL: https://${aws_apprunner_service.researcher.service_url}
    
    Test the researcher:
    curl https://${aws_apprunner_service.researcher.service_url}/research
    
    ${var.scheduler_enabled ? "⏰ Automated research is running every 2 hours" : "💡 To enable automated research, set scheduler_enabled = true"}
    
    Note: You'll need to deploy your actual researcher code to App Runner.
    Follow the guide for instructions on building and deploying the Docker image.
  EOT
}