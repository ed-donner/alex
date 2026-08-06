# Update Cloud Run services to use new Docker images
# Run this after rebuilding Docker images

param(
    [string]$ProjectId = "",
    [string]$Region = "us-central1",
    [string]$Repo = "alex-agents",
    [string]$ImageTag = "latest"
)

# Load .env if available
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
            Write-Host "ERROR: Could not determine project ID" -ForegroundColor Red
            exit 1
        }
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Updating Cloud Run Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project: $ProjectId" -ForegroundColor Gray
Write-Host "Region: $Region" -ForegroundColor Gray
Write-Host ""

$agents = @("planner", "tagger", "reporter", "charter", "retirement")
$ARTIFACT_REGISTRY = "${Region}-docker.pkg.dev/${ProjectId}/${Repo}"

foreach ($agent in $agents) {
    Write-Host "Updating $agent..." -ForegroundColor Yellow
    $imageUrl = "${ARTIFACT_REGISTRY}/${agent}:${ImageTag}"
    
    gcloud run services update alex-$agent `
        --region=$Region `
        --image=$imageUrl `
        --project=$ProjectId `
        --quiet
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ $agent updated successfully" -ForegroundColor Green
    } else {
        Write-Host "✗ Failed to update $agent" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Update Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next: Apply Terraform to update environment variables:" -ForegroundColor Yellow
Write-Host "  cd terraform/6_agents" -ForegroundColor Gray
Write-Host "  terraform apply" -ForegroundColor Gray
Write-Host ""

