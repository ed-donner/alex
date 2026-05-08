output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.researcher.repository_url
}

output "researcher_service_url" {
  description = "URL of the ECS Fargate researcher service"
  value       = local.researcher_url
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.researcher.name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.researcher.name
}

output "scheduler_status" {
  description = "Status of the automated scheduler"
  value       = var.scheduler_enabled ? "Enabled - Running every 2 hours" : "Disabled"
}

output "setup_instructions" {
  description = "Instructions for completing setup"
  value       = <<-EOT
    
    ✅ Researcher service deployed successfully!
    
    Service URL: ${local.researcher_url}
    
    Test the researcher:
    curl ${local.researcher_url}/health
    
    ${var.scheduler_enabled ? "⏰ Automated research is running every 2 hours" : "💡 To enable automated research, set scheduler_enabled = true"}
    
    Note: This deployment uses ECS Fargate because App Runner is not available in this AWS account.
  EOT
}