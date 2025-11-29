# Quick Deployment Script - Deploys API and Frontend
# Run this from the alex-gcp directory

$PROJECT_ID = "alex-multi-agent-saas-479504"
$REGION = "us-central1"
$REPO = "alex-agents"
$ARTIFACT_REGISTRY = "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Quick Frontend Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Build API
Write-Host "Building API..." -ForegroundColor Yellow
docker build --platform linux/amd64 -f backend/api/Dockerfile -t ${ARTIFACT_REGISTRY}/api:latest backend/
docker push ${ARTIFACT_REGISTRY}/api:latest
Write-Host "✓ API built" -ForegroundColor Green

# Step 2: Update Terraform with API
Write-Host "Deploying API..." -ForegroundColor Yellow
cd terraform/6_agents
terraform apply -auto-approve
$API_URL = terraform output -raw api_service_url
cd ../..
Write-Host "✓ API deployed: $API_URL" -ForegroundColor Green

# Step 3: Build Frontend
Write-Host "Building Frontend..." -ForegroundColor Yellow
$env:NEXT_PUBLIC_API_URL = $API_URL
docker build --platform linux/amd64 -f frontend/Dockerfile -t ${ARTIFACT_REGISTRY}/frontend:latest frontend/
docker push ${ARTIFACT_REGISTRY}/frontend:latest
Write-Host "✓ Frontend built" -ForegroundColor Green

# Step 4: Deploy Frontend
Write-Host "Deploying Frontend..." -ForegroundColor Yellow
cd terraform/7_frontend
# Update backend_api_url in tfvars
(Get-Content terraform.tfvars) -replace 'backend_api_url\s*=\s*"[^"]*"', "backend_api_url = `"$API_URL`"" | Set-Content terraform.tfvars
terraform apply -auto-approve
$FRONTEND_URL = terraform output -raw frontend_url
cd ../..

# Step 5: Update API CORS
Write-Host "Updating API CORS..." -ForegroundColor Yellow
cd terraform/6_agents
(Get-Content terraform.tfvars) -replace 'frontend_url\s*=\s*"[^"]*"', "frontend_url = `"$FRONTEND_URL`"" | Set-Content terraform.tfvars
terraform apply -auto-approve
cd ../..

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Frontend: $FRONTEND_URL" -ForegroundColor Green
Write-Host "API: $API_URL" -ForegroundColor Green

