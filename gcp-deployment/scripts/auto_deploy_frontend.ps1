# Automatic Frontend Deployment
$ErrorActionPreference = "Stop"

# Unset invalid GOOGLE_APPLICATION_CREDENTIALS if pointing to non-existent file
if ($env:GOOGLE_APPLICATION_CREDENTIALS -and -not (Test-Path $env:GOOGLE_APPLICATION_CREDENTIALS)) {
    Remove-Item Env:GOOGLE_APPLICATION_CREDENTIALS
}

# Load .env
$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot ".env"
$envVars = @{}
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*)\s*=\s*(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim() -replace '^["'']|["'']$', ''
            if ($value) {
                $envVars[$key] = $value
            }
        }
    }
}
Write-Host "Loaded $($envVars.Count) environment variables from .env" -ForegroundColor Cyan

$PROJECT_ID = if ($envVars.ContainsKey("GCP_PROJECT_ID")) { $envVars["GCP_PROJECT_ID"] } else { "alex-multi-agent-saas-479504" }
$REGION = if ($envVars.ContainsKey("GCP_REGION")) { $envVars["GCP_REGION"] } else { "us-central1" }
$REPO = "alex-agents"
$ARTIFACT_REGISTRY = "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Automatic Frontend Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Build & Push API
Write-Host "[1/5] Building API image..." -ForegroundColor Yellow
docker build --platform linux/amd64 -f backend/api/Dockerfile -t ${ARTIFACT_REGISTRY}/api:latest backend/
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Build failed" -ForegroundColor Red; exit 1 }
docker push ${ARTIFACT_REGISTRY}/api:latest
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Push failed" -ForegroundColor Red; exit 1 }
Write-Host "✓ API image ready" -ForegroundColor Green

# Step 2: Create/Update Clerk Secrets
Write-Host "[2/5] Setting up Clerk secrets..." -ForegroundColor Yellow
$clerkPub = if ($envVars.ContainsKey("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY") -and $envVars["NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"]) { $envVars["NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"] } else { "" }
$clerkSec = if ($envVars.ContainsKey("CLERK_SECRET_KEY") -and $envVars["CLERK_SECRET_KEY"]) { $envVars["CLERK_SECRET_KEY"] } else { "" }
Write-Host "Clerk Pub Key length: $($clerkPub.Length), Clerk Sec Key length: $($clerkSec.Length)" -ForegroundColor Gray
if ($clerkPub) {
    echo $clerkPub | gcloud secrets create clerk-publishable-key --data-file=- --project=$PROJECT_ID 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        echo $clerkPub | gcloud secrets versions add clerk-publishable-key --data-file=- --project=$PROJECT_ID 2>&1 | Out-Null
    }
}
if ($clerkSec) {
    echo $clerkSec | gcloud secrets create clerk-secret-key --data-file=- --project=$PROJECT_ID 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        echo $clerkSec | gcloud secrets versions add clerk-secret-key --data-file=- --project=$PROJECT_ID 2>&1 | Out-Null
    }
}
Write-Host "✓ Clerk secrets ready" -ForegroundColor Green

# Step 3: Deploy API
Write-Host "[3/5] Deploying API service..." -ForegroundColor Yellow
Push-Location "$projectRoot/terraform/6_agents"
$clerkJwks = if ($envVars.ContainsKey("CLERK_JWKS_URL")) { $envVars["CLERK_JWKS_URL"] } else { "https://modern-sparrow-23.clerk.accounts.dev/.well-known/jwks.json" }
$clerkIssuer = if ($envVars.ContainsKey("CLERK_ISSUER")) { $envVars["CLERK_ISSUER"] } else { "https://modern-sparrow-23.clerk.accounts.dev" }

# Update tfvars using simple string replacement
$tfvarsContent = Get-Content terraform.tfvars
$newTfvars = @()
foreach ($line in $tfvarsContent) {
    if ($line -match '^\s*clerk_jwks_url\s*=') {
        $newTfvars += "clerk_jwks_url              = `"$clerkJwks`""
    } elseif ($line -match '^\s*clerk_issuer\s*=') {
        $newTfvars += "clerk_issuer                = `"$clerkIssuer`""
    } else {
        $newTfvars += $line
    }
}
Set-Content terraform.tfvars $newTfvars

terraform apply -auto-approve
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Terraform apply failed" -ForegroundColor Red; Pop-Location; exit 1 }
$API_URL = terraform output -raw api_service_url
Pop-Location
Write-Host "✓ API deployed: $API_URL" -ForegroundColor Green

# Step 4: Build & Push Frontend
Write-Host "[4/5] Building Frontend image..." -ForegroundColor Yellow
$clerkPubKey = if ($envVars.ContainsKey("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY") -and $envVars["NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"]) { $envVars["NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"] } else { "" }
if (-not $clerkPubKey) {
    Write-Host "WARNING: NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY not found in .env" -ForegroundColor Yellow
}
docker build --platform linux/amd64 `
    --build-arg NEXT_PUBLIC_API_URL=$API_URL `
    --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$clerkPubKey `
    -f frontend/Dockerfile `
    -t ${ARTIFACT_REGISTRY}/frontend:latest `
    frontend/
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Frontend build failed" -ForegroundColor Red; exit 1 }
docker push ${ARTIFACT_REGISTRY}/frontend:latest
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Frontend push failed" -ForegroundColor Red; exit 1 }
Write-Host "✓ Frontend image ready" -ForegroundColor Green

# Step 5: Deploy Frontend
Write-Host "[5/5] Deploying Frontend..." -ForegroundColor Yellow
Push-Location "$projectRoot/terraform/7_frontend"
$tfvarsContent = Get-Content terraform.tfvars
$newTfvars = @()
foreach ($line in $tfvarsContent) {
    if ($line -match '^\s*backend_api_url\s*=') {
        $newTfvars += "backend_api_url             = `"$API_URL`""
    } else {
        $newTfvars += $line
    }
}
Set-Content terraform.tfvars $newTfvars

# Initialize Terraform if needed
Write-Host "Initializing Terraform..." -ForegroundColor Gray
terraform init
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Terraform init failed" -ForegroundColor Red; Pop-Location; exit 1 }

terraform apply -auto-approve
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Frontend terraform apply failed" -ForegroundColor Red; Pop-Location; exit 1 }
$FRONTEND_URL = terraform output -raw frontend_url
Pop-Location
Write-Host "✓ Frontend deployed: $FRONTEND_URL" -ForegroundColor Green

# Step 6: Update API CORS
Write-Host "Updating API CORS..." -ForegroundColor Yellow
Push-Location "$projectRoot/terraform/6_agents"
$tfvarsContent = Get-Content terraform.tfvars
$newTfvars = @()
foreach ($line in $tfvarsContent) {
    if ($line -match '^\s*frontend_url\s*=') {
        $newTfvars += "frontend_url                = `"$FRONTEND_URL`""
    } else {
        $newTfvars += $line
    }
}
Set-Content terraform.tfvars $newTfvars

terraform apply -auto-approve
Pop-Location

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✓ Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Frontend: $FRONTEND_URL" -ForegroundColor Green
Write-Host "API: $API_URL" -ForegroundColor Green
Write-Host ""
