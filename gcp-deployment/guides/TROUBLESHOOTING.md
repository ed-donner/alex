# Troubleshooting Guide

This guide covers common issues and solutions when deploying and running Alex on GCP.

## Table of Contents

1. [Environment Variables](#environment-variables)
2. [Pub/Sub Issues](#pubsub-issues)
3. [Cloud Run Logs](#cloud-run-logs)
4. [Docker Build Issues](#docker-build-issues)
5. [Database Connection Issues](#database-connection-issues)
6. [Authentication Issues](#authentication-issues)
7. [API Not Enabled Errors](#api-not-enabled-errors)

## Environment Variables

### Issue: Environment Variables Not Loading

**Symptoms:**
- `GCP_PROJECT_ID` is `None` or wrong value
- Configuration errors in application

**Solutions:**

1. **Verify `.env` file exists in root directory:**
   ```bash
   # Required variables
   GCP_PROJECT_ID=your-gcp-project-id
   GCP_REGION=us-central1
   PUBSUB_TOPIC=alex-job-queue
   ```

2. **Check environment variable loading:**
   ```bash
   cd backend/api
   uv run python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('GCP_PROJECT_ID:', os.getenv('GCP_PROJECT_ID'))"
   ```

3. **For Cloud Run, set environment variables in Terraform:**
   - Check `terraform/6_agents/main.tf` for environment variable configuration
   - Ensure all required variables are set in `terraform.tfvars`

## Pub/Sub Issues

### Error: "404 Requested project not found"

**Symptoms:**
```
google.api_core.exceptions.NotFound: 404 Requested project not found
```

**Solutions:**

1. **Set GCP_PROJECT_ID in .env file:**
   ```bash
   GCP_PROJECT_ID=your-gcp-project-id
   ```

2. **Verify current gcloud project:**
   ```bash
   gcloud config get-value project
   ```

3. **Set gcloud default project:**
   ```bash
   gcloud config set project your-gcp-project-id
   ```

### Error: "Permission denied" or "403 Forbidden"

**Symptoms:**
```
google.api_core.exceptions.PermissionDenied: 403 User does not have permission
```

**Solutions:**

1. **Grant Pub/Sub Publisher role:**
   ```bash
   gcloud pubsub topics add-iam-policy-binding alex-job-queue \
     --member="serviceAccount:cloud-run-sa@your-gcp-project-id.iam.gserviceaccount.com" \
     --role="roles/pubsub.publisher" \
     --project=your-gcp-project-id
   ```

2. **Verify topic exists:**
   ```bash
   gcloud pubsub topics list --project=your-gcp-project-id
   ```

### Error: "Topic not found"

**Solutions:**

1. **Deploy Pub/Sub Terraform:**
   ```bash
   cd terraform/3_pubsub
   terraform apply
   ```

2. **Or create topic manually:**
   ```bash
   gcloud pubsub topics create alex-job-queue --project=your-gcp-project-id
   ```

### Issue: Old Pub/Sub Messages with Invalid Job IDs

**Symptoms:**
- Errors like `invalid input syntax for type uuid: "test-123"`
- Old test messages in queue

**Solution: Purge the Pub/Sub subscription**
```bash
gcloud pubsub subscriptions seek alex-planner-subscription \
  --time=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
  --project=your-gcp-project-id
```

## Cloud Run Logs

### View Recent Logs

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=alex-planner" \
  --limit 20 \
  --format="table(timestamp,severity,textPayload)" \
  --project=your-gcp-project-id \
  --freshness=10m
```

### View Only Errors

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=alex-planner AND severity>=ERROR" \
  --limit 10 \
  --format="value(textPayload)" \
  --project=your-gcp-project-id \
  --freshness=10m
```

### Follow Logs in Real-Time

```bash
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=alex-planner" \
  --project=your-gcp-project-id
```

### View Logs for All Agents

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=~'alex-.*'" \
  --limit 50 \
  --format="table(timestamp,resource.labels.service_name,severity,textPayload)" \
  --project=your-gcp-project-id \
  --freshness=10m
```

## Docker Build Issues

### Error: "Distribution not found at: file:///database"

**Cause:** Docker build context doesn't include the `database` directory.

**Solution:** Build from `backend/` directory, not individual agent directories:

```bash
cd backend

# Build planner
docker build -f planner/Dockerfile -t us-central1-docker.pkg.dev/your-gcp-project-id/alex-agents/planner:latest .

# Build other agents similarly
docker build -f tagger/Dockerfile -t us-central1-docker.pkg.dev/your-gcp-project-id/alex-agents/tagger:latest .
```

**Key Points:**
- Build context must be `backend/` directory
- Use `-f agent/Dockerfile` to specify Dockerfile location
- Dockerfiles copy `database` and `common` directories into image

### Error: "sed command fails"

If `sed -i` doesn't work in Dockerfile, use Python instead:

```dockerfile
RUN python3 -c "import re; content = open('pyproject.toml').read(); open('pyproject.toml', 'w').write(re.sub(r'path = \"\.\./database\"', 'path = \"./database\"', content))"
```

## Database Connection Issues

### Error: "Instance connection name not found"

**Solutions:**

1. **Verify Cloud SQL instance exists:**
   ```bash
   gcloud sql instances list --project=your-gcp-project-id
   ```

2. **Get connection name:**
   ```bash
   gcloud sql instances describe alex-postgres --project=your-gcp-project-id --format="value(connectionName)"
   ```

3. **Set environment variable:**
   ```bash
   INSTANCE_CONNECTION_NAME=your-gcp-project-id:us-central1:alex-postgres
   ```

### Error: "Permission denied" for database

**Solutions:**

1. **Grant Cloud SQL Client role to service account:**
   ```bash
   gcloud projects add-iam-policy-binding your-gcp-project-id \
     --member="serviceAccount:cloud-run-sa@your-gcp-project-id.iam.gserviceaccount.com" \
     --role="roles/cloudsql.client"
   ```

2. **Verify database password secret exists:**
   ```bash
   gcloud secrets versions access latest --secret="alex-db-password" --project=your-gcp-project-id
   ```

## Authentication Issues

### Error: "Application Default Credentials not found"

**Solutions:**

1. **Authenticate with gcloud:**
   ```bash
   gcloud auth application-default login
   ```

2. **Set quota project:**
   ```bash
   gcloud auth application-default set-quota-project your-gcp-project-id
   ```

3. **For Cloud Run, use service account:**
   - Service accounts are automatically used by Cloud Run
   - Verify service account has required IAM roles

## API Not Enabled Errors

### Error: "API has not been used in project before or it is disabled"

**Symptoms:**
```
Error 403: API has not been used in project before or it is disabled
```

**Solutions:**

1. **Enable required APIs:**
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
     pubsub.googleapis.com \
     cloudbuild.googleapis.com \
     logging.googleapis.com \
     monitoring.googleapis.com \
     --project=your-gcp-project-id
   ```

2. **Wait 2-5 minutes for API propagation**

3. **Verify API is enabled:**
   ```bash
   gcloud services list --enabled --project=your-gcp-project-id
   ```

## Quick Reference

### Common Commands

| Task | Command |
|------|---------|
| Check project | `gcloud config get-value project` |
| List Cloud Run services | `gcloud run services list --project=your-gcp-project-id` |
| View logs | `gcloud logging read "resource.type=cloud_run_revision" --limit=20` |
| Check Pub/Sub topics | `gcloud pubsub topics list --project=your-gcp-project-id` |
| List secrets | `gcloud secrets list --project=your-gcp-project-id` |
| Check Cloud SQL instances | `gcloud sql instances list --project=your-gcp-project-id` |

### Environment Variables Checklist

- [ ] `GCP_PROJECT_ID` set in `.env`
- [ ] `GCP_REGION` set in `.env`
- [ ] `PUBSUB_TOPIC` set in `.env`
- [ ] `INSTANCE_CONNECTION_NAME` set (for database)
- [ ] `DB_PASSWORD_SECRET_ID` set (for database)
- [ ] All required APIs enabled
- [ ] Service accounts have required IAM roles

## Getting More Help

1. **Check Terraform outputs:**
   ```bash
   cd terraform/[phase]
   terraform output
   ```

2. **Check Cloud Console:**
   - Cloud Run: https://console.cloud.google.com/run
   - Pub/Sub: https://console.cloud.google.com/cloudpubsub
   - Cloud SQL: https://console.cloud.google.com/sql
   - Logs: https://console.cloud.google.com/logs

3. **Review guide files:**
   - `guides/1_permissions.md` - IAM setup
   - `guides/5_database.md` - Database setup
   - `guides/6_agents.md` - Agent deployment

