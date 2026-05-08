output "cloudfront_url" {
  description = "CloudFront distribution URL"
  value       = var.enable_cloudfront ? "https://${aws_cloudfront_distribution.main[0].domain_name}" : null
}

output "api_gateway_url" {
  description = "API Gateway URL"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "s3_website_url" {
  description = "S3 website URL (useful if CloudFront is disabled)"
  value       = "http://${aws_s3_bucket_website_configuration.frontend.website_endpoint}"
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for frontend"
  value       = aws_s3_bucket.frontend.id
}

output "lambda_function_name" {
  description = "Name of the API Lambda function"
  value       = aws_lambda_function.api.function_name
}

output "setup_instructions" {
  description = "Instructions for completing the deployment"
  value = <<-EOT

    ✅ Frontend & API infrastructure deployed successfully!

    CloudFront URL: ${var.enable_cloudfront ? "https://${aws_cloudfront_distribution.main[0].domain_name}" : "(disabled)"}
    S3 Website URL: http://${aws_s3_bucket_website_configuration.frontend.website_endpoint}
    API Gateway: ${aws_apigatewayv2_api.main.api_endpoint}
    S3 Bucket: ${aws_s3_bucket.frontend.id}
    Lambda Function: ${aws_lambda_function.api.function_name}

    Next steps:

    1. If you deployed manually (not using scripts/deploy.py):
       a. Build and deploy the frontend:
          cd frontend
          npm run build
          aws s3 sync out/ s3://${aws_s3_bucket.frontend.id}/ --delete

       b. Invalidate CloudFront cache (if enabled):
          aws cloudfront create-invalidation \
            --distribution-id ${try(aws_cloudfront_distribution.main[0].id, "")} \
            --paths "/*"

    2. Test the deployment:
       - Visit: ${var.enable_cloudfront ? "https://${aws_cloudfront_distribution.main[0].domain_name}" : "http://${aws_s3_bucket_website_configuration.frontend.website_endpoint}"}
       - Sign in with Clerk
       - Check API calls in Network tab

    3. Monitor in AWS Console:
       - CloudWatch Logs: /aws/lambda/${aws_lambda_function.api.function_name}
       - API Gateway metrics
       - CloudFront metrics

    To destroy: cd scripts && uv run destroy.py
  EOT
}