# =============================================================================
# Destroy Alex Multi-Agent SaaS Deployment on GCP
# =============================================================================
# This script destroys all GCP resources created by the Alex deployment
# Resources are destroyed in reverse order of deployment to handle dependencies
# =============================================================================

param(
    [string]$ProjectId = "",
    [string]$Region = "us-central1",
    [switch]$SkipConfirmation = $false,
    [switch]$DestroySecrets = $false,
    [switch]$DestroyAll = $true,
    [switch]$DestroyFrontend = $false,
    [switch]$DestroyAgents = $false,
    [switch]$DestroyDatabase = $false,
    [switch]$DestroyPubSub = $false,
    [switch]$DestroyVertexAI = $false,
    [switch]$DestroyPermissions = $false
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

# Determine what to destroy
$destroyPhases = @()

if ($DestroyAll) {
    $destroyPhases = @("7_frontend", "6_agents", "5_database", "3_pubsub", "2_vertex_ai", "1_permissions")
} else {
    if ($DestroyFrontend) { $destroyPhases += "7_frontend" }
    if ($DestroyAgents) { $destroyPhases += "6_agents" }
    if ($DestroyDatabase) { $destroyPhases += "5_database" }
    if ($DestroyPubSub) { $destroyPhases += "3_pubsub" }
    if ($DestroyVertexAI) { $destroyPhases += "2_vertex_ai" }
    if ($DestroyPermissions) { $destroyPhases += "1_permissions" }
}

if ($destroyPhases.Count -eq 0) {
    Write-Host "No phases selected for destruction. Use -DestroyAll or specific phase flags." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Red
Write-Host "  DESTROY ALEX DEPLOYMENT" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Red
Write-Host ""
Write-Host "Project ID: $ProjectId" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host ""
Write-Host "Phases to destroy:" -ForegroundColor Yellow
foreach ($phase in $destroyPhases) {
    Write-Host "  - $phase" -ForegroundColor Yellow
}
Write-Host ""

if ($DestroySecrets) {
    Write-Host "⚠️  WARNING: Secrets will also be destroyed!" -ForegroundColor Red
    Write-Host ""
}

if (-not $SkipConfirmation) {
    $confirmation = Read-Host "Are you sure you want to destroy these resources? (yes/no)"
    if ($confirmation -ne "yes") {
        Write-Host "Destruction cancelled." -ForegroundColor Green
        exit 0
    }
}

Write-Host ""
Write-Host "Starting destruction..." -ForegroundColor Cyan
Write-Host ""

$terraformDir = Join-Path $projectRoot "terraform"
$errors = @()

foreach ($phase in $destroyPhases) {
    $phaseDir = Join-Path $terraformDir $phase
    
    if (-not (Test-Path $phaseDir)) {
        Write-Host "⚠️  Phase directory not found: $phase" -ForegroundColor Yellow
        continue
    }
    
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host "Destroying: $phase" -ForegroundColor Cyan
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    
    Push-Location $phaseDir
    
    try {
        # Check if terraform is initialized
        if (-not (Test-Path ".terraform")) {
            Write-Host "Initializing Terraform..." -ForegroundColor Gray
            terraform init -upgrade 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "⚠️  Failed to initialize Terraform for $phase" -ForegroundColor Yellow
                Pop-Location
                continue
            }
        }
        
        # Destroy resources
        Write-Host "Running terraform destroy..." -ForegroundColor Gray
        terraform destroy -auto-approve
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Successfully destroyed $phase" -ForegroundColor Green
        } else {
            Write-Host "❌ Error destroying $phase" -ForegroundColor Red
            $errors += $phase
        }
    }
    catch {
        Write-Host "❌ Exception destroying $phase : $_" -ForegroundColor Red
        $errors += $phase
    }
    finally {
        Pop-Location
    }
    
    Write-Host ""
}

# Destroy secrets if requested
if ($DestroySecrets) {
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host "Destroying Secrets" -ForegroundColor Cyan
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    
    $secrets = @(
        "alex-db-password",
        "polygon-api-key",
        "openai-api-key",
        "clerk-publishable-key",
        "clerk-secret-key"
    )
    
    foreach ($secret in $secrets) {
        Write-Host "Checking secret: $secret..." -ForegroundColor Gray
        $exists = gcloud secrets describe $secret --project=$ProjectId 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Destroying secret: $secret..." -ForegroundColor Yellow
            gcloud secrets delete $secret --project=$ProjectId --quiet
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ Destroyed secret: $secret" -ForegroundColor Green
            } else {
                Write-Host "⚠️  Failed to destroy secret: $secret" -ForegroundColor Yellow
            }
        } else {
            Write-Host "Secret $secret does not exist, skipping..." -ForegroundColor Gray
        }
    }
    Write-Host ""
}

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DESTRUCTION SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($errors.Count -eq 0) {
    Write-Host "✅ All selected phases destroyed successfully!" -ForegroundColor Green
} else {
    Write-Host "⚠️  Some phases had errors:" -ForegroundColor Yellow
    foreach ($error in $errors) {
        Write-Host "  - $error" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "You may need to manually clean up these resources in the GCP Console." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Note: Some resources may take a few minutes to fully delete." -ForegroundColor Gray
Write-Host "Check the GCP Console to verify all resources are removed." -ForegroundColor Gray
Write-Host ""

