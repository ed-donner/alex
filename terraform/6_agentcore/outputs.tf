output "sqs_queue_url" {
  description = "URL of the SQS queue for job submission"
  value       = aws_sqs_queue.analysis_jobs.url
}

output "sqs_queue_arn" {
  description = "ARN of the SQS queue"
  value       = aws_sqs_queue.analysis_jobs.arn
}

output "agent_arns" {
  description = "ARNs of deployed AgentCore agents"
  sensitive   = true
  value = {
    for agent in ["planner", "tagger", "reporter", "charter", "retirement"] :
    agent => data.aws_ssm_parameter.agent_arns[agent].value
  }
}

output "agent_iam_role_arn" {
  description = "ARN of the IAM role used by agents"
  value = aws_iam_role.lambda_agents_role.arn
  sensitive   = true
}

output "setup_instructions" {
  description = "Instructions for testing the agents"
  value = <<-EOT
    
    ✅ Agent infrastructure deployed successfully!
    
    AgentCore Agents:
    # - Planner (Orchestrator)
    # - Tagger:
    # - Reporter
    # - Charter
    # - Retirement
    
    SQS Queue: ${aws_sqs_queue.analysis_jobs.name}
    
    To test the system:
    1. The agents are deployed using OpenAI Agents SDK with AWS Bedrock AgentCore
    2. Run the full integration test:
       cd backend
       uv run test_full.py
    
    3. Monitor agent performance in AWS Console:
       - Bedrock AgentCore console for agent status
       - CloudWatch Logs for agent execution logs
       - SSM Parameter Store for agent ARNs
    
    Note: Agents are deployed as AgentCore endpoints, not Lambda functions.
    They can be invoked directly or through the SQS orchestration system.
    
    EOT
}