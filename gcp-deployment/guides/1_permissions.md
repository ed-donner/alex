# Phase 1: GCP Permissions Setup

## Overview

This guide sets up the foundational IAM permissions on GCP, equivalent to AWS's IAM setup in the original course.

## AWS vs GCP Comparison

| AWS Concept | GCP Equivalent |
|-------------|----------------|
| IAM User | Service Account / User |
| IAM Role | IAM Role (predefined or custom) |
| IAM Policy | IAM Policy Binding |
| Trust Policy | Service Account Impersonation |
| Access Keys | Service Account Keys (avoid) / Workload Identity |

## Steps

### Step 1: Create a GCP Project

**For Linux/Mac (Bash):**
```bash
# Set your project ID
export PROJECT_ID="alex-multiagent-saas"
export REGION="us-central1"

# Create project (or use existing)
gcloud projects create $PROJECT_ID --name="Alex Multi-Agent SaaS"

# Set as default
gcloud config set project $PROJECT_ID

# Link billing account
gcloud billing accounts list
gcloud billing projects link $PROJECT_ID --billing-account=YOUR_BILLING_ACCOUNT_ID
```

**For Windows (PowerShell):**
```powershell
# Set your project ID
$PROJECT_ID = "alex-multiagent-saas"
$REGION = "us-central1"

# Create project (or use existing)
gcloud projects create $PROJECT_ID --name="Alex Multi-Agent SaaS"

# Set as default
gcloud config set project $PROJECT_ID

# Link billing account
gcloud billing accounts list
gcloud billing projects link $PROJECT_ID --billing-account=YOUR_BILLING_ACCOUNT_ID
```

**Note:** If you see a quota project warning, run:
```powershell
gcloud auth application-default set-quota-project $PROJECT_ID
```

### Step 2: Enable Required APIs

**For Linux/Mac (Bash):**
```bash
gcloud services enable \
  compute.googleapis.com \
  run.googleapis.com \
  cloudfunctions.googleapis.com \
  sqladmin.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  storage.googleapis.com \
  dns.googleapis.com \
  certificatemanager.googleapis.com \
  cloudbuild.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com
```

**For Windows (PowerShell):**
```powershell
gcloud services enable `
  compute.googleapis.com `
  run.googleapis.com `
  cloudfunctions.googleapis.com `
  sqladmin.googleapis.com `
  aiplatform.googleapis.com `
  artifactregistry.googleapis.com `
  secretmanager.googleapis.com `
  cloudresourcemanager.googleapis.com `
  iam.googleapis.com `
  storage.googleapis.com `
  dns.googleapis.com `
  certificatemanager.googleapis.com `
  cloudbuild.googleapis.com `
  logging.googleapis.com `
  monitoring.googleapis.com
```

**Alternative (PowerShell - single line):**
```powershell
gcloud services enable compute.googleapis.com run.googleapis.com cloudfunctions.googleapis.com sqladmin.googleapis.com aiplatform.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com cloudresourcemanager.googleapis.com iam.googleapis.com storage.googleapis.com dns.googleapis.com certificatemanager.googleapis.com cloudbuild.googleapis.com logging.googleapis.com monitoring.googleapis.com
```

### Step 3: Initialize Terraform

Navigate to `terraform/1_permissions/` and run:

```bash
cd terraform/1_permissions/
terraform init
terraform plan
terraform apply
```

### Step 4: Verify Setup

**For Linux/Mac (Bash):**
```bash
# List service accounts
gcloud iam service-accounts list

# Check IAM bindings
gcloud projects get-iam-policy $PROJECT_ID
```

**For Windows (PowerShell):**
```powershell
# List service accounts
gcloud iam service-accounts list

# Check IAM bindings
gcloud projects get-iam-policy $PROJECT_ID
```

**Note:** Make sure `$PROJECT_ID` is set in your current PowerShell session. If you opened a new terminal, set it again with `$PROJECT_ID = "alex-multiagent-saas"`.

## Service Accounts Created

| Service Account | Purpose |
|-----------------|---------|
| `vertex-ai-sa` | Vertex AI model access |
| `cloud-run-sa` | Cloud Run service execution |
| `cloud-functions-sa` | Cloud Functions execution |
| `cloud-sql-sa` | Cloud SQL access |
| `storage-sa` | Cloud Storage access |
| `deploy-sa` | CI/CD deployment |

## Best Practices

1. **Use Workload Identity** instead of service account keys
2. **Principle of Least Privilege** - grant minimum required permissions
3. **Use predefined roles** where possible
4. **Audit IAM regularly** using Cloud Audit Logs

## Troubleshooting

### Permission Denied Errors

**For Linux/Mac (Bash):**
```bash
# Check current permissions
gcloud auth list
gcloud projects get-iam-policy $PROJECT_ID --format=json | jq '.bindings[] | select(.members[] | contains("YOUR_EMAIL"))'
```

**For Windows (PowerShell):**
```powershell
# Check current permissions
gcloud auth list
gcloud projects get-iam-policy $PROJECT_ID --format=json | ConvertFrom-Json | Select-Object -ExpandProperty bindings | Where-Object { $_.members -contains "YOUR_EMAIL" }
```

### Application Default Credentials (ADC) Issues

**Common Error:** `error getting credentials using GOOGLE_APPLICATION_CREDENTIALS environment variable: open <path>: The system cannot find the file specified`

This occurs when the `GOOGLE_APPLICATION_CREDENTIALS` environment variable points to a non-existent file, preventing Terraform from using the default ADC location.

**Solution:**

**For Linux/Mac (Bash):**
```bash
# Unset the environment variable to use default ADC location
unset GOOGLE_APPLICATION_CREDENTIALS

# Or set it to the default location
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/application_default_credentials.json"
```

**For Windows (PowerShell):**
```powershell
# Unset the environment variable to use default ADC location
$env:GOOGLE_APPLICATION_CREDENTIALS = $null
# Or use:
Remove-Item Env:GOOGLE_APPLICATION_CREDENTIALS -ErrorAction SilentlyContinue

# Or set it to the default location
$env:GOOGLE_APPLICATION_CREDENTIALS = "$env:APPDATA\gcloud\application_default_credentials.json"
```

**After setting up ADC:**
```powershell
# Login to set up Application Default Credentials
gcloud auth application-default login

# Set quota project (if you see a warning)
gcloud auth application-default set-quota-project $PROJECT_ID
```

### API Not Enabled

**Common Error:** `Error 403: API has not been used in project before or it is disabled`

**For Linux/Mac (Bash):**
```bash
# List all enabled APIs
gcloud services list --enabled

# Check if a specific API is enabled
gcloud services list --enabled --filter="name:artifactregistry.googleapis.com"

# Enable a specific API
gcloud services enable artifactregistry.googleapis.com --project=$PROJECT_ID

# Enable all required APIs (if you missed any)
gcloud services enable \
  compute.googleapis.com \
  run.googleapis.com \
  cloudfunctions.googleapis.com \
  sqladmin.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  storage.googleapis.com \
  dns.googleapis.com \
  certificatemanager.googleapis.com \
  cloudbuild.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  --project=$PROJECT_ID
```

**For Windows (PowerShell):**
```powershell
# List all enabled APIs
gcloud services list --enabled

# Check if a specific API is enabled
gcloud services list --enabled --filter="name:artifactregistry.googleapis.com" --project=$PROJECT_ID

# Enable a specific API
gcloud services enable artifactregistry.googleapis.com --project=$PROJECT_ID

# Enable all required APIs (if you missed any)
gcloud services enable `
  compute.googleapis.com `
  run.googleapis.com `
  cloudfunctions.googleapis.com `
  sqladmin.googleapis.com `
  aiplatform.googleapis.com `
  artifactregistry.googleapis.com `
  secretmanager.googleapis.com `
  cloudresourcemanager.googleapis.com `
  iam.googleapis.com `
  storage.googleapis.com `
  dns.googleapis.com `
  certificatemanager.googleapis.com `
  cloudbuild.googleapis.com `
  logging.googleapis.com `
  monitoring.googleapis.com `
  --project=$PROJECT_ID
```

**Important Notes:**
- **API Propagation Delay**: After enabling an API, it may take 2-5 minutes to fully propagate across GCP systems. If you get an error immediately after enabling, wait a few minutes and retry.
- **Verify API Status**: Always verify an API is enabled before running Terraform. The command above will show `STATE: ENABLED` when ready.
- **Artifact Registry API**: This API is commonly missed and required for container image storage. If Terraform fails with "Artifact Registry API has not been used", enable it explicitly and wait 2-3 minutes before retrying.

## Next Steps

After completing permissions setup, proceed to [2_vertex_ai.md](2_vertex_ai.md) for Vertex AI setup (equivalent to AWS SageMaker).
