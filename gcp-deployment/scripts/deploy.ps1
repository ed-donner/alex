# =============================================================================
# GCP Deployment Script for Alex Multi-Agent SaaS (Windows PowerShell)
# =============================================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("full", "phase", "build", "destroy", "help")]
    [string]$Command = "help",
    
    [Parameter(Position=1)]
    [string]$Phase = ""
)

# Configuration - Set these or use environment variables
$PROJECT_ID = if ($env:PROJECT_ID) { $env:PROJECT_ID } else { "" }
$REGION = if ($env:REGION) { $env:REGION } else { "us-central1" }
$ENVIRONMENT = if ($env:ENVIRONMENT) { $env:ENVIRONMENT } else { "dev" }

# Colors
function Write-Status { param($Message) Write-Host "[INFO] $Message" -ForegroundColor Green }
function Write-Warning { param($Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Error { param($Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }

# Check prerequisites
function Test-Prerequisites {
    Write-Status "Checking prerequisites..."
    
    # Check gcloud
    if (-not (Get-Command "gcloud" -ErrorAction SilentlyContinue)) {
        Write-Error "gcloud CLI is not installed. Download from: https://cloud.google.com/sdk/docs/install"
        exit 1
    }
    
    # Check terraform
    if (-not (Get-Command "terraform" -ErrorAction SilentlyContinue)) {
        Write-Error "Terraform is not installed. Download from: https://developer.hashicorp.com/terraform/downloads"
        exit 1
    }
    
    # Check docker
    if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
        Write-Error "Docker is not installed. Download Docker Desktop from: https://www.docker.com/products/docker-desktop"
        exit 1
    }
    
    # Check PROJECT_ID
    if ([string]::IsNullOrEmpty($PROJECT_ID)) {
        Write-Error "PROJECT_ID is not set. Run: `$env:PROJECT_ID = 'your-project-id'"
        exit 1
    }
    
    Write-Status "All prerequisites met!"
}

# Setup GCP project
function Set-GCPProject {
    Write-Status "Setting up GCP project..."
    
    gcloud config set project $PROJECT_ID
    gcloud config set compute/region $REGION
    
    Write-Status "Enabling required APIs..."
    $apis = @(
        "compute.googleapis.com",
        "run.googleapis.com",
        "cloudfunctions.googleapis.com",
        "sqladmin.googleapis.com",
        "aiplatform.googleapis.com",
        "artifactregistry.googleapis.com",
        "secretmanager.googleapis.com",
        "cloudresourcemanager.googleapis.com",
        "iam.googleapis.com",
        "storage.googleapis.com",
        "servicenetworking.googleapis.com",
        "cloudbuild.googleapis.com"
    )
    
    gcloud services enable $apis
}

# Deploy a phase
function Deploy-Phase {
    param([string]$PhaseName)
    
    Write-Status "Deploying phase: $PhaseName"
    
    $originalLocation = Get-Location
    Set-Location "terraform\$PhaseName"
    
    # Check for tfvars
    if (-not (Test-Path "terraform.tfvars")) {
        Write-Warning "terraform.tfvars not found, copying from example..."
        if (Test-Path "terraform.tfvars.example") {
            Copy-Item "terraform.tfvars.example" "terraform.tfvars"
            Write-Warning "Please edit terraform\$PhaseName\terraform.tfvars with your values"
        }
    }
    
    # Run terraform
    terraform init
    if ($LASTEXITCODE -ne 0) { Set-Location $originalLocation; exit 1 }
    
    terraform plan -out=tfplan
    if ($LASTEXITCODE -ne 0) { Set-Location $originalLocation; exit 1 }
    
    terraform apply tfplan
    if ($LASTEXITCODE -ne 0) { Set-Location $originalLocation; exit 1 }
    
    Set-Location $originalLocation
}

# Build and push container images
function Build-Images {
    Write-Status "Building and pushing container images..."
    
    # Configure Docker for Artifact Registry
    gcloud auth configure-docker "$REGION-docker.pkg.dev"
    
    $REPO = "$REGION-docker.pkg.dev/$PROJECT_ID/alex-containers"
    
    # Build each agent
    $agents = @("researcher", "planner", "executor", "orchestrator")
    foreach ($agent in $agents) {
        $agentPath = "backend\agents\$agent"
        if (Test-Path $agentPath) {
            Write-Status "Building $agent agent..."
            docker build -t "$REPO/${agent}:latest" -f "$agentPath\Dockerfile" $agentPath
            docker push "$REPO/${agent}:latest"
        }
    }
    
    # Build frontend
    if (Test-Path "frontend") {
        Write-Status "Building frontend..."
        docker build -t "$REPO/frontend:latest" frontend
        docker push "$REPO/frontend:latest"
    }
}

# Full deployment
function Invoke-FullDeploy {
    Test-Prerequisites
    Set-GCPProject
    
    Write-Status "Starting full deployment..."
    
    Deploy-Phase "1_permissions"
    Deploy-Phase "2_vertex_ai"
    Deploy-Phase "5_database"
    
    Build-Images
    
    Deploy-Phase "6_agents"
    Deploy-Phase "7_frontend"
    
    Write-Status "Deployment complete!"
    
    Set-Location "terraform\7_frontend"
    $frontendUrl = terraform output -raw frontend_url
    Set-Location "..\6_agents"
    $backendUrl = terraform output -raw orchestrator_url
    Set-Location "..\.."
    
    Write-Status "Frontend URL: $frontendUrl"
    Write-Status "Backend API URL: $backendUrl"
}

# Destroy all resources
function Invoke-Destroy {
    Write-Warning "This will destroy all resources. Continue? (y/N)"
    $confirm = Read-Host
    
    if ($confirm -ne "y") {
        Write-Status "Aborted"
        exit 0
    }
    
    $phases = @("7_frontend", "6_agents", "5_database", "2_vertex_ai", "1_permissions")
    $originalLocation = Get-Location
    
    foreach ($phase in $phases) {
        Write-Status "Destroying $phase..."
        Set-Location "terraform\$phase"
        terraform destroy -auto-approve
        Set-Location $originalLocation
    }
    
    Write-Status "All resources destroyed"
}

# Show help
function Show-Help {
    Write-Host @"
GCP Deployment Script for Alex Multi-Agent SaaS

Usage: .\deploy.ps1 <command> [options]

Commands:
    full        Run full deployment
    phase <n>   Deploy specific phase (e.g., 1_permissions)
    build       Build and push container images
    destroy     Destroy all resources
    help        Show this help message

Before running, set environment variables:
    `$env:PROJECT_ID = "your-gcp-project-id"
    `$env:REGION = "us-central1"  # optional, defaults to us-central1

Examples:
    .\deploy.ps1 full
    .\deploy.ps1 phase 1_permissions
    .\deploy.ps1 build
    .\deploy.ps1 destroy
"@
}

# Main
switch ($Command) {
    "full" { Invoke-FullDeploy }
    "phase" {
        if ([string]::IsNullOrEmpty($Phase)) {
            Write-Error "Please specify a phase (e.g., .\deploy.ps1 phase 1_permissions)"
            exit 1
        }
        Test-Prerequisites
        Deploy-Phase $Phase
    }
    "build" {
        Test-Prerequisites
        Build-Images
    }
    "destroy" { Invoke-Destroy }
    "help" { Show-Help }
    default { Show-Help }
}
