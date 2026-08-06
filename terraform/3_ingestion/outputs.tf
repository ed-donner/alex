output "vector_bucket_name" {
  description = "Name of the S3 Vectors bucket"
  value       = aws_s3_bucket.vectors.id
}

output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = "${aws_api_gateway_stage.api.invoke_url}/ingest"
}

output "api_key_id" {
  description = "API Key ID"
  value       = aws_api_gateway_api_key.api_key.id
}

output "api_key_value" {
  description = "API Key value (sensitive)"
  value       = aws_api_gateway_api_key.api_key.value
  sensitive   = true
}

output "setup_instructions" {
  description = "Instructions for setting up environment variables"
  value = <<-EOT
    
    ✅ Ingestion pipeline deployed successfully!
    
    Add the following to your .env file:
    VECTOR_BUCKET=${aws_s3_bucket.vectors.id}
    ALEX_API_ENDPOINT=${aws_api_gateway_stage.api.invoke_url}/ingest
    
    To get your API key value:
    aws apigateway get-api-key --api-key ${aws_api_gateway_api_key.api_key.id} --include-value --query 'value' --output text
    
    Then add to .env:
    ALEX_API_KEY=<the-api-key-value>
    
    Test the API:
    curl -X POST ${aws_api_gateway_stage.api.invoke_url}/ingest \
      -H "x-api-key: <your-api-key>" \
      -H "Content-Type: application/json" \
      -d '{"content": "Test document", "text":"test text", "metadata": {"source": "test"}}'
  EOT
}
