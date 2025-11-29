# Rebuild and push all agent Docker images
# This script rebuilds images after code changes (e.g., database client fixes)

param(
    [string]$ProjectId = "",
    [string]$Region = "us-central1",
    [string]$Repo = "alex-agents",
    [string]$ImageTag = "latest"
)

# Load .env file if it exists
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
        if ([string]::IsNullOrEmpty($ProjectId)) {
            Write-Host "ERROR: Could not determine project ID. Set GCP_PROJECT_ID in .env or use -ProjectId parameter" -ForegroundColor Red
            exit 1
        }
    }
}

$ARTIFACT_REGISTRY = "${Region}-docker.pkg.dev/${ProjectId}/${Repo}"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Rebuilding Agent Docker Images" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project: $ProjectId" -ForegroundColor Gray
Write-Host "Region: $Region" -ForegroundColor Gray
Write-Host "Repository: $Repo" -ForegroundColor Gray
Write-Host "Tag: $ImageTag" -ForegroundColor Gray
Write-Host ""

# Authenticate Docker
Write-Host "Authenticating Docker with Artifact Registry..." -ForegroundColor Yellow
gcloud auth configure-docker "${Region}-docker.pkg.dev" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to authenticate Docker" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Docker authenticated" -ForegroundColor Green
Write-Host ""

# Build and push each agent
$agents = @("planner", "tagger", "reporter", "charter", "retirement")
$backendDir = Join-Path $projectRoot "backend"

foreach ($agent in $agents) {
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host "Building $agent..." -ForegroundColor Cyan
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    
    $imageName = "${ARTIFACT_REGISTRY}/${agent}:${ImageTag}"
    
    # Build the image
    Write-Host "Building Docker image..." -ForegroundColor Yellow
    docker build --platform linux/amd64 `
        -f "$backendDir/$agent/Dockerfile" `
        -t $imageName `
        $backendDir
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to build $agent image" -ForegroundColor Red
        continue
    }
    
    Write-Host "✓ Image built successfully" -ForegroundColor Green
    
    # Push the image
    Write-Host "Pushing to Artifact Registry..." -ForegroundColor Yellow
    docker push $imageName
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to push $agent image" -ForegroundColor Red
        continue
    }
    
    Write-Host "✓ $agent pushed successfully" -ForegroundColor Green
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Rebuild Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Apply Terraform to update Cloud Run services:" -ForegroundColor Gray
Write-Host "   cd terraform/6_agents" -ForegroundColor Gray
Write-Host "   terraform apply" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Or force Cloud Run to use new image (if using 'latest' tag):" -ForegroundColor Gray
Write-Host "   gcloud run services update alex-planner --region=$Region --image=$ARTIFACT_REGISTRY/planner:$ImageTag" -ForegroundColor Gray
Write-Host ""

