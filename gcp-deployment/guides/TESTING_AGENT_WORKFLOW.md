# Testing Agent-to-Agent Communication

This guide walks you through testing the complete agent workflow: creating a job, triggering the planner via Pub/Sub, and verifying that agents communicate via HTTP and write results to the database.

## Prerequisites

✅ Cloud Run services deployed for all agents  
✅ Database seeded with 22 instruments  
✅ Cloud SQL proxy running (if testing locally)  
✅ Environment variables configured in `.env`

## Step 1: Get Cloud Run Service URLs

First, get the URLs of your deployed Cloud Run services:

```powershell
# Navigate to terraform directory
cd alex-gcp/terraform/6_agents

# Get all service URLs
terraform output
```

You should see URLs like:
- `planner_url = "https://alex-planner-xxxxx-uc.a.run.app"`
- `reporter_url = "https://alex-reporter-xxxxx-uc.a.run.app"`
- `tagger_url = "https://alex-tagger-xxxxx-uc.a.run.app"`
- etc.

**Add these to your `.env` file:**
```bash
PLANNER_URL=https://alex-planner-xxxxx-uc.a.run.app
TAGGER_URL=https://alex-tagger-xxxxx-uc.a.run.app
REPORTER_URL=https://alex-reporter-xxxxx-uc.a.run.app
CHARTER_URL=https://alex-charter-xxxxx-uc.a.run.app
RETIREMENT_URL=https://alex-retirement-xxxxx-uc.a.run.app
```

## Step 2: Create a Test User and Account

Before creating a job, you need a user and account in the database. You can do this via the API or directly in the database.

### Option A: Via API (if API is running)

```powershell
# Set your test Clerk user ID (or use a real one from Clerk)
$CLERK_USER_ID = "user_test123"

# Create user (replace with your API endpoint)
$headers = @{
    "Authorization" = "Bearer YOUR_CLERK_TOKEN"
    "Content-Type" = "application/json"
}

$body = @{
    clerk_user_id = $CLERK_USER_ID
    display_name = "Test User"
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:8000/api/user" -Method POST -Headers $headers -Body $body
```

### Option B: Direct Database Insert (for testing)

```powershell
# Connect to database via proxy
$env:PGPASSWORD = "YOUR_DB_PASSWORD"
psql -h 127.0.0.1 -p 5432 -U postgres -d alex

# In psql:
INSERT INTO users (clerk_user_id, display_name) 
VALUES ('user_test123', 'Test User')
ON CONFLICT (clerk_user_id) DO NOTHING;

INSERT INTO accounts (id, clerk_user_id, account_name, account_purpose, cash_balance)
VALUES (gen_random_uuid(), 'user_test123', 'Test 401k', '401k', 0.00)
ON CONFLICT (id) DO NOTHING;

-- Get the account ID
SELECT id, account_name FROM accounts WHERE clerk_user_id = 'user_test123';
\q
```

## Step 3: Add Test Positions

Add some positions to the account so the planner has data to analyze:

```powershell
# In psql (replace ACCOUNT_ID with actual UUID from Step 2):
INSERT INTO positions (id, account_id, symbol, quantity)
VALUES 
    (gen_random_uuid(), 'ACCOUNT_ID', 'SPY', 10),
    (gen_random_uuid(), 'ACCOUNT_ID', 'QQQ', 5),
    (gen_random_uuid(), 'ACCOUNT_ID', 'BND', 20)
ON CONFLICT (id) DO NOTHING;

-- Verify positions
SELECT p.symbol, p.quantity, a.account_name 
FROM positions p 
JOIN accounts a ON p.account_id = a.id 
WHERE a.clerk_user_id = 'user_test123';
```

## Step 4: Create a Job

### Option A: Via API (Recommended)

```powershell
# Create analysis job via API
$headers = @{
    "Authorization" = "Bearer YOUR_CLERK_TOKEN"
    "Content-Type" = "application/json"
}

$body = @{
    analysis_type = "portfolio_analysis"
    options = @{
        include_retirement_projection = $true
        include_charts = $true
    }
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:8000/api/analyze" -Method POST -Headers $headers -Body $body
$jobData = $response.Content | ConvertFrom-Json
$jobId = $jobData.job_id
Write-Host "Created job: $jobId"
```

### Option B: Direct Database Insert

```powershell
# In psql:
INSERT INTO jobs (id, clerk_user_id, job_type, status, request_payload)
VALUES (
    gen_random_uuid(),
    'user_test123',
    'portfolio_analysis',
    'pending',
    '{"analysis_type": "portfolio_analysis", "options": {}}'::jsonb
)
RETURNING id;

-- Copy the returned UUID
\q
```

## Step 5: Trigger Planner Agent

You can trigger the planner in two ways:

### Option A: Via Pub/Sub (Production Flow)

The job should already be queued if you created it via the API. If not, publish manually:

```powershell
cd alex-gcp/backend/api

# Load environment variables
$env:GOOGLE_APPLICATION_CREDENTIALS = ""  # Use ADC
gcloud auth application-default login

# Run the Pub/Sub test script (modify it to use your job_id)
uv run python test_pubsub.py
```

Or publish directly:

```powershell
# Get project ID and topic name from .env
$PROJECT_ID = (Get-Content .env | Select-String "GCP_PROJECT_ID").ToString().Split("=")[1].Trim()
$TOPIC = (Get-Content .env | Select-String "PUBSUB_TOPIC").ToString().Split("=")[1].Trim()

# Publish message
$message = @{
    job_id = "YOUR_JOB_ID_HERE"
    clerk_user_id = "user_test123"
    analysis_type = "portfolio_analysis"
} | ConvertTo-Json

gcloud pubsub topics publish $TOPIC --message $message --project $PROJECT_ID
```

### Option B: Direct HTTP POST (Testing)

```powershell
# Get ID token for Cloud Run authentication
$token = gcloud auth print-identity-token

# Get planner URL from terraform output or .env
$PLANNER_URL = "https://alex-planner-xxxxx-uc.a.run.app"

# Trigger planner directly
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

$body = @{
    job_id = "YOUR_JOB_ID_HERE"
} | ConvertTo-Json

Invoke-WebRequest -Uri "$PLANNER_URL/" -Method POST -Headers $headers -Body $body
```

## Step 6: Monitor Agent Execution

### Check Cloud Run Logs

```powershell
# Planner logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=alex-planner" --limit 50 --format json --project $PROJECT_ID

# Reporter logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=alex-reporter" --limit 50 --format json --project $PROJECT_ID

# Or use the Cloud Console: https://console.cloud.google.com/run
```

### Check Job Status in Database

```powershell
# In psql:
SELECT id, status, created_at, updated_at, error_message 
FROM jobs 
WHERE id = 'YOUR_JOB_ID_HERE';

-- Check if report was generated
SELECT id, status, report IS NOT NULL as has_report, charts IS NOT NULL as has_charts
FROM jobs 
WHERE id = 'YOUR_JOB_ID_HERE';
```

## Step 7: Verify Results

### Check Job Completion

```powershell
# In psql:
SELECT 
    id,
    status,
    CASE WHEN report IS NOT NULL THEN 'Yes' ELSE 'No' END as has_report,
    CASE WHEN charts IS NOT NULL THEN 'Yes' ELSE 'No' END as has_charts,
    CASE WHEN retirement IS NOT NULL THEN 'Yes' ELSE 'No' END as has_retirement,
    updated_at
FROM jobs 
WHERE clerk_user_id = 'user_test123'
ORDER BY created_at DESC
LIMIT 5;
```

### View Report Content

```powershell
# In psql:
SELECT 
    id,
    status,
    LEFT(report::text, 200) as report_preview,
    LEFT(charts::text, 200) as charts_preview
FROM jobs 
WHERE id = 'YOUR_JOB_ID_HERE' AND status = 'completed';
```

## Troubleshooting

### Planner Returns 404 "Job not found"

- **Cause**: Job ID doesn't exist in database
- **Fix**: Create the job first (Step 4), then use that exact UUID

### Planner Returns 500 Error

- **Cause**: Check Cloud Run logs for the actual error
- **Common issues**:
  - Missing environment variables (Cloud Run service URLs, database connection)
  - Database connection failure
  - Missing instruments in database (run `seed_data.py`)

### Agents Not Being Called

- **Cause**: Planner can't reach other agents
- **Fix**: 
  1. Verify `PLANNER_URL`, `TAGGER_URL`, etc. are set in Cloud Run environment variables
  2. Check IAM permissions: Planner service account needs `roles/run.invoker` on other services
  3. Verify agents are deployed and healthy: `gcloud run services list`

### Database Connection Errors

- **Cause**: Cloud SQL connection issues
- **Fix**:
  1. Verify `INSTANCE_CONNECTION_NAME` is set correctly
  2. Check VPC connector is attached to Cloud Run services
  3. Verify service account has `roles/cloudsql.client` permission

## Next Steps

Once the workflow is working:

1. **Test with real Clerk authentication** - Use actual user tokens from your frontend
2. **Monitor costs** - Check Cloud Run billing and Pub/Sub usage
3. **Add error handling** - Implement retries and dead-letter queues
4. **Performance testing** - Test with multiple concurrent jobs
5. **Frontend integration** - Connect the NextJS frontend to display results

## Quick Test Script

Here's a complete PowerShell script to test the workflow:

```powershell
# Set variables
$CLERK_USER_ID = "user_test123"
$PROJECT_ID = "alex-multi-agent-saas-479504"  # Replace with your project
$PLANNER_URL = "https://alex-planner-xxxxx-uc.a.run.app"  # Replace with actual URL

# 1. Create job in database
$env:PGPASSWORD = "YOUR_DB_PASSWORD"
$jobId = psql -h 127.0.0.1 -p 5432 -U postgres -d alex -t -c "INSERT INTO jobs (id, clerk_user_id, job_type, status, request_payload) VALUES (gen_random_uuid(), '$CLERK_USER_ID', 'portfolio_analysis', 'pending', '{}'::jsonb) RETURNING id;"
$jobId = $jobId.Trim()
Write-Host "Created job: $jobId"

# 2. Trigger planner
$token = gcloud auth print-identity-token
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}
$body = @{ job_id = $jobId } | ConvertTo-Json

try {
    $response = Invoke-WebRequest -Uri "$PLANNER_URL/" -Method POST -Headers $headers -Body $body
    Write-Host "Planner triggered successfully!"
    Write-Host $response.Content
} catch {
    Write-Host "Error: $_"
    Write-Host $_.Exception.Response
}

# 3. Check status (wait a few seconds first)
Start-Sleep -Seconds 10
psql -h 127.0.0.1 -p 5432 -U postgres -d alex -c "SELECT id, status, updated_at FROM jobs WHERE id = '$jobId';"
```

