# Quick Frontend Deployment Script
# This script deploys both backend API and frontend

param(
    [string]$ProjectId = "",
    [string]$Region = "us-central1"
)

# Load .env
$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot ".env"
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*)\s*=\s*(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            if ($value -match '^["''](.*)["'']$') {
                $value = $matches[1]
            }
            Set-Item -Path "env:$key" -Value $value
        }
    }
}

# Get project ID
if ([string]::IsNullOrEmpty($ProjectId)) {
    $ProjectId = $env:GCP_PROJECT_ID
    if ([string]::IsNullOrEmpty($ProjectId)) {
        $ProjectId = gcloud config get-value project 2>$null
    }
}

$REGION = $Region
$REPO = "alex-agents"
$ARTIFACT_REGISTRY = "${REGION}-docker.pkg.dev/${ProjectId}/${REPO}"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Frontend Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Project: $ProjectId" -ForegroundColor Gray
Write-Host "Region: $REGION" -ForegroundColor Gray
Write-Host ""

# Step 1: Build and push API
Write-Host "Step 1: Building API Docker image..." -ForegroundColor Yellow
docker build --platform linux/amd64 -f backend/api/Dockerfile -t ${ARTIFACT_REGISTRY}/api:latest backend/ 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: API build failed" -ForegroundColor Red
    exit 1
}

Write-Host "Pushing API image..." -ForegroundColor Yellow
docker push ${ARTIFACT_REGISTRY}/api:latest 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: API push failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ API image pushed" -ForegroundColor Green
Write-Host ""

# Step 2: Create Clerk secrets
Write-Host "Step 2: Creating Clerk secrets..." -ForegroundColor Yellow
$clerkPublishable = $env:NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
$clerkSecret = $env:CLERK_SECRET_KEY

if ([string]::IsNullOrEmpty($clerkPublishable) -or [string]::IsNullOrEmpty($clerkSecret)) {
    Write-Host "WARNING: Clerk keys not found in .env. Creating empty secrets..." -ForegroundColor Yellow
    echo "placeholder" | gcloud secrets create clerk-publishable-key --data-file=- --project=$ProjectId 2>&1 | Out-Null
    echo "placeholder" | gcloud secrets create clerk-secret-key --data-file=- --project=$ProjectId 2>&1 | Out-Null
} else {
    echo $clerkPublishable | gcloud secrets create clerk-publishable-key --data-file=- --project=$ProjectId 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        # Secret might exist, update it
        echo $clerkPublishable | gcloud secrets versions add clerk-publishable-key --data-file=- --project=$ProjectId 2>&1 | Out-Null
    }
    
    echo $clerkSecret | gcloud secrets create clerk-secret-key --data-file=- --project=$ProjectId 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        echo $clerkSecret | gcloud secrets versions add clerk-secret-key --data-file=- --project=$ProjectId 2>&1 | Out-Null
    }
}
Write-Host "✓ Clerk secrets ready" -ForegroundColor Green
Write-Host ""

# Step 3: Deploy API via Terraform
Write-Host "Step 3: Deploying API service..." -ForegroundColor Yellow
Push-Location "$projectRoot/terraform/6_agents"

# Get values from existing tfvars
$tfvarsPath = Join-Path (Get-Location) "terraform.tfvars"
if (-not (Test-Path $tfvarsPath)) {
    Write-Host "ERROR: terraform.tfvars not found. Copy from terraform.tfvars.example" -ForegroundColor Red
    Pop-Location
    exit 1
}

# Add Clerk and CORS variables to tfvars if not present
$tfvarsContent = Get-Content $tfvarsPath -Raw
if ($tfvarsContent -notmatch "clerk_jwks_url") {
    Add-Content $tfvarsPath "`nclerk_jwks_url = `"$($env:CLERK_JWKS_URL)`""
    Add-Content $tfvarsPath "clerk_issuer = `"$($env:CLERK_ISSUER)`""
    Add-Content $tfvarsPath "frontend_url = `"`"  # Will be updated after frontend deployment"
    Add-Content $tfvarsPath "cors_origins = `"`""
}

terraform apply -auto-approve 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Terraform apply failed" -ForegroundColor Red
    Pop-Location
    exit 1
}

# Get API URL
$apiUrl = terraform output -raw api_service_url 2>$null
Write-Host "✓ API deployed: $apiUrl" -ForegroundColor Green
Pop-Location
Write-Host ""

# Step 4: Build and push Frontend
Write-Host "Step 4: Building Frontend Docker image..." -ForegroundColor Yellow
Push-Location "$projectRoot/frontend"

# Set API URL for build
$env:NEXT_PUBLIC_API_URL = $apiUrl

docker build --platform linux/amd64 -t ${ARTIFACT_REGISTRY}/frontend:latest . 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Frontend build failed" -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "Pushing Frontend image..." -ForegroundColor Yellow
docker push ${ARTIFACT_REGISTRY}/frontend:latest 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Frontend push failed" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "✓ Frontend image pushed" -ForegroundColor Green
Pop-Location
Write-Host ""

# Step 5: Deploy Frontend
Write-Host "Step 5: Deploying Frontend..." -ForegroundColor Yellow
Push-Location "$projectRoot/terraform/7_frontend"

# Create tfvars if not exists
$tfvarsPath = Join-Path (Get-Location) "terraform.tfvars"
if (-not (Test-Path $tfvarsPath)) {
    Copy-Item terraform.tfvars.example terraform.tfvars
}

# Update tfvars with API URL
$tfvarsContent = Get-Content $tfvarsPath -Raw
$tfvarsContent = $tfvarsContent -replace 'backend_api_url\s*=\s*"[^"]*"', "backend_api_url = `"$apiUrl`""
Set-Content $tfvarsPath $tfvarsContent

terraform apply -auto-approve 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Frontend terraform apply failed" -ForegroundColor Red
    Pop-Location
    exit 1
}

$frontendUrl = terraform output -raw frontend_service_url 2>$null
Write-Host "✓ Frontend deployed: $frontendUrl" -ForegroundColor Green
Pop-Location
Write-Host ""

# Step 6: Update API CORS with frontend URL
Write-Host "Step 6: Updating API CORS configuration..." -ForegroundColor Yellow
Push-Location "$projectRoot/terraform/6_agents"

# Update tfvars with frontend URL
$tfvarsContent = Get-Content terraform.tfvars -Raw
$tfvarsContent = $tfvarsContent -replace 'frontend_url\s*=\s*"[^"]*"', "frontend_url = `"$frontendUrl`""
Set-Content terraform.tfvars $tfvarsContent

terraform apply -auto-approve 2>&1 | Out-Null
Write-Host "✓ CORS updated" -ForegroundColor Green
Pop-Location

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Frontend URL: $frontendUrl" -ForegroundColor Green
Write-Host "API URL: $apiUrl" -ForegroundColor Green
Write-Host ""
Write-Host "Test the deployment:" -ForegroundColor Yellow
Write-Host "  curl $apiUrl/health" -ForegroundColor Gray
Write-Host "  curl $frontendUrl" -ForegroundColor Gray
Write-Host ""

