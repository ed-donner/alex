output "sqs_queue_url" {
  description = "URL of the SQS queue for job submission"
  value       = aws_sqs_queue.analysis_jobs.url
}

output "sqs_queue_arn" {
  description = "ARN of the SQS queue"
  value       = aws_sqs_queue.analysis_jobs.arn
}

output "lambda_functions" {
  description = "Names of deployed Lambda functions"
  value = {
    planner    = aws_lambda_function.planner.function_name
    tagger     = aws_lambda_function.tagger.function_name
    reporter   = aws_lambda_function.reporter.function_name
    charter    = aws_lambda_function.charter.function_name
    retirement = aws_lambda_function.retirement.function_name
  }
}

output "setup_instructions" {
  description = "Instructions for testing the agents"
  value       = <<-EOT
    
    ✅ Agent infrastructure deployed successfully!
    
    Lambda Functions:
    - Planner (Orchestrator): ${aws_lambda_function.planner.function_name}
    - Tagger: ${aws_lambda_function.tagger.function_name}
    - Reporter: ${aws_lambda_function.reporter.function_name}
    - Charter: ${aws_lambda_function.charter.function_name}
    - Retirement: ${aws_lambda_function.retirement.function_name}
    
    SQS Queue: ${aws_sqs_queue.analysis_jobs.name}
    
    To test the system:
    1. First, package and deploy each agent's code:
       cd backend/planner && uv run package_docker.py --deploy
       cd backend/tagger && uv run package_docker.py --deploy
       cd backend/reporter && uv run package_docker.py --deploy
       cd backend/charter && uv run package_docker.py --deploy
       cd backend/retirement && uv run package_docker.py --deploy
    
    2. Run the full integration test:
       cd backend/planner
       uv run run_full_test.py
    
    3. Monitor progress in CloudWatch Logs:
       - /aws/lambda/alex-planner
       - /aws/lambda/alex-tagger
       - /aws/lambda/alex-reporter
       - /aws/lambda/alex-charter
       - /aws/lambda/alex-retirement
    
    Bedrock Model: ${var.bedrock_model_id}
    Region: ${var.bedrock_region}
  EOT
}