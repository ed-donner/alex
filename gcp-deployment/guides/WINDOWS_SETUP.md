# Windows Setup Guide for Alex GCP Deployment

This guide covers setting up the GCP deployment environment on Windows.

## Prerequisites Installation

### 1. Install Google Cloud SDK

Download and install from: https://cloud.google.com/sdk/docs/install

After installation, open **PowerShell** and run:
```powershell
gcloud init
gcloud auth login
```

### 2. Install Terraform

**Option A: Using Chocolatey (recommended)**
```powershell
# Install Chocolatey first if you don't have it
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install Terraform
choco install terraform
```

**Option B: Manual Installation**
1. Download from: https://developer.hashicorp.com/terraform/downloads
2. Extract to `C:\terraform`
3. Add `C:\terraform` to your PATH environment variable

Verify installation:
```powershell
terraform --version
```

### 3. Install Docker Desktop

1. Download from: https://www.docker.com/products/docker-desktop
2. Install and restart your computer
3. Start Docker Desktop

Verify installation:
```powershell
docker --version
```

### 4. Install Git (if not already installed)

Download from: https://git-scm.com/download/win

## Project Setup

### 1. Extract the Project

Extract `alex-gcp-deployment.zip` to a folder, e.g., `C:\Projects\alex-gcp`

### 2. Set Environment Variables

Open PowerShell and set your project ID:
```powershell
$env:PROJECT_ID = "your-gcp-project-id"
$env:REGION = "us-central1"
```

To make these permanent, add to your PowerShell profile:
```powershell
notepad $PROFILE
# Add these lines:
# $env:PROJECT_ID = "your-gcp-project-id"
# $env:REGION = "us-central1"
```

### 3. Authenticate with GCP

```powershell
gcloud auth login
gcloud auth application-default login
gcloud config set project $env:PROJECT_ID
```

## Deployment

### Option 1: Using PowerShell Script

```powershell
cd C:\Projects\alex-gcp

# Allow script execution (one-time)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Run full deployment
.\scripts\deploy.ps1 full

# Or deploy phase by phase
.\scripts\deploy.ps1 phase 1_permissions
.\scripts\deploy.ps1 phase 2_vertex_ai
.\scripts\deploy.ps1 phase 5_database
.\scripts\deploy.ps1 phase 6_agents
.\scripts\deploy.ps1 phase 7_frontend
```

### Option 2: Manual Terraform Commands

```powershell
cd C:\Projects\alex-gcp\terraform\1_permissions

# Copy and edit variables
Copy-Item terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars  # Edit with your values

# Deploy
terraform init
terraform plan
terraform apply
```

## Windows-Specific Notes

### Path Separators
Terraform on Windows handles both `/` and `\` path separators, so the terraform files work without modification.

### Line Endings
If you encounter issues with scripts, ensure files have Windows line endings (CRLF). In VS Code:
- Click "LF" in the bottom right
- Select "CRLF"

### Docker on Windows
- Ensure Docker Desktop is running before building images
- WSL 2 backend is recommended for better performance
- If you get permission errors, run PowerShell as Administrator

### Long Path Support
If you encounter path length issues:
```powershell
# Run as Administrator
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

## Troubleshooting

### "gcloud is not recognized"
Add Google Cloud SDK to PATH:
1. Open System Properties → Environment Variables
2. Add `C:\Users\<YourUser>\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin` to PATH

### "terraform is not recognized"
Add Terraform to PATH or use full path:
```powershell
C:\terraform\terraform.exe init
```

### Docker Connection Errors
1. Ensure Docker Desktop is running
2. Check Docker is set to use Linux containers (right-click Docker icon → Switch to Linux containers)

### Permission Denied on Scripts
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### SSL/TLS Errors
```powershell
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
```

## VS Code Setup (Recommended)

Install these extensions for better experience:
- HashiCorp Terraform
- Google Cloud Code
- Docker

## Next Steps

1. Follow the guides in the `guides/` folder in order
2. Start with `1_permissions.md`
3. Edit `terraform.tfvars` files with your project ID before each phase
