# Test script for agent workflow
# This script creates a job and triggers the planner agent

param(
    [string]$PlannerUrl = "",
    [string]$ClerkUserId = "user_test123",
    [string]$DbPassword = "",
    [string]$DbHost = "",
    [int]$DbPort = 0
)

# Function to load .env file
function Load-EnvFile {
    param([string]$EnvPath)
    
    if (-not (Test-Path $EnvPath)) {
        Write-Host "Warning: .env file not found at $EnvPath" -ForegroundColor Yellow
        return @{}
    }
    
    $envVars = @{}
    Get-Content $EnvPath | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*)\s*=\s*(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove quotes if present
            if ($value -match '^["''](.*)["'']$') {
                $value = $matches[1]
            }
            $envVars[$key] = $value
        }
    }
    return $envVars
}

# Load .env file from project root
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$envPath = Join-Path $projectRoot ".env"
$envVars = Load-EnvFile -EnvPath $envPath

# Set environment variables from .env
foreach ($key in $envVars.Keys) {
    if (-not [string]::IsNullOrEmpty($envVars[$key])) {
        Set-Item -Path "env:$key" -Value $envVars[$key]
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Agent Workflow Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Get Planner URL
if ([string]::IsNullOrEmpty($PlannerUrl)) {
    if ($env:PLANNER_URL) {
        $PlannerUrl = $env:PLANNER_URL
    } else {
        Write-Host "Getting Planner URL from Terraform..." -ForegroundColor Yellow
        Push-Location "$PSScriptRoot/../../terraform/6_agents"
        $PlannerUrl = terraform output -raw planner_service_url 2>$null
        Pop-Location
        if ([string]::IsNullOrEmpty($PlannerUrl)) {
            Write-Host "ERROR: Could not get Planner URL. Set it manually with -PlannerUrl or PLANNER_URL in .env" -ForegroundColor Red
            exit 1
        }
    }
}
Write-Host "Planner URL: $PlannerUrl" -ForegroundColor Green
Write-Host ""

# Step 2: Get database connection info
if ([string]::IsNullOrEmpty($DbHost)) {
    $DbHost = $env:DB_HOST
    if ([string]::IsNullOrEmpty($DbHost)) {
        $DbHost = "127.0.0.1"
    }
}

if ($DbPort -eq 0) {
    $DbPort = $env:DB_PORT
    if ([string]::IsNullOrEmpty($DbPort)) {
        $DbPort = 5432
    } else {
        $DbPort = [int]$DbPort
    }
}

# Get database user and name
$DbUser = $env:DATABASE_USER
if ([string]::IsNullOrEmpty($DbUser)) {
    $DbUser = $env:DB_USER
    if ([string]::IsNullOrEmpty($DbUser)) {
        $DbUser = "alex_app"  # Default from codebase
    }
}

$DbName = $env:DATABASE_NAME
if ([string]::IsNullOrEmpty($DbName)) {
    $DbName = $env:DB_NAME
    if ([string]::IsNullOrEmpty($DbName)) {
        $DbName = "alex"  # Default from codebase
    }
}

if ([string]::IsNullOrEmpty($DbPassword)) {
    # Try to get password from Secret Manager if DB_PASSWORD_SECRET_ID is set
    if ($env:DB_PASSWORD_SECRET_ID -and $env:GCP_PROJECT_ID) {
        Write-Host "Retrieving database password from Secret Manager..." -ForegroundColor Yellow
        try {
            $DbPassword = gcloud secrets versions access latest --secret=$env:DB_PASSWORD_SECRET_ID --project=$env:GCP_PROJECT_ID 2>$null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "Warning: Failed to get password from Secret Manager. Will prompt for password." -ForegroundColor Yellow
                $DbPassword = ""
            }
        } catch {
            Write-Host "Warning: Failed to get password from Secret Manager. Will prompt for password." -ForegroundColor Yellow
            $DbPassword = ""
        }
    } else {
        # Try direct DB_PASSWORD from .env
        $DbPassword = $env:DB_PASSWORD
    }
    
    if ([string]::IsNullOrEmpty($DbPassword)) {
        $DbPassword = Read-Host "Enter database password"
    }
}

$env:PGPASSWORD = $DbPassword

Write-Host "Database connection:" -ForegroundColor Cyan
Write-Host "  Host: $DbHost" -ForegroundColor Gray
Write-Host "  Port: $DbPort" -ForegroundColor Gray
Write-Host "  User: $DbUser" -ForegroundColor Gray
Write-Host "  Database: $DbName" -ForegroundColor Gray
Write-Host ""

# Helper function to run psql and handle errors
function Invoke-PSQL {
    param(
        [string]$Command,
        [hashtable]$Variables = @{},
        [switch]$Silent
    )
    
    # Build psql command with variables if provided
    $psqlArgs = @("-h", $DbHost, "-p", $DbPort, "-U", $DbUser, "-d", $DbName, "-t")
    
    # Add variables using -v option
    foreach ($key in $Variables.Keys) {
        $psqlArgs += "-v"
        $psqlArgs += "${key}=$($Variables[$key])"
    }
    
    $psqlArgs += "-c"
    $psqlArgs += $Command
    
    $output = & psql $psqlArgs 2>&1
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -ne 0) {
        if (-not $Silent) {
            Write-Host "ERROR: Database connection failed" -ForegroundColor Red
            Write-Host $output -ForegroundColor Red
        }
        return $null
    }
    
    if ($output) {
        return $output.Trim()
    }
    return ""
}

# Step 3: Create test user and account (if needed)
Write-Host "Step 1: Setting up test user and account..." -ForegroundColor Yellow

# Check if user exists
$userExists = Invoke-PSQL -Command "SELECT COUNT(*) FROM users WHERE clerk_user_id = '$ClerkUserId';"
if ($null -eq $userExists) {
    Write-Host "ERROR: Cannot connect to database. Is Cloud SQL proxy running?" -ForegroundColor Red
    Write-Host "  Start proxy: cloud-sql-proxy --port=$DbPort $($env:INSTANCE_CONNECTION_NAME)" -ForegroundColor Yellow
    exit 1
}

if ($userExists -eq "0") {
    Write-Host "Creating test user..." -ForegroundColor Yellow
    $null = Invoke-PSQL -Command "INSERT INTO users (clerk_user_id, display_name) VALUES ('$ClerkUserId', 'Test User') ON CONFLICT (clerk_user_id) DO NOTHING;" -Silent
}

# Get or create account
$accountId = Invoke-PSQL -Command "SELECT id FROM accounts WHERE clerk_user_id = '$ClerkUserId' LIMIT 1;"

if ([string]::IsNullOrEmpty($accountId)) {
    Write-Host "Creating test account..." -ForegroundColor Yellow
    $accountId = Invoke-PSQL -Command "INSERT INTO accounts (id, clerk_user_id, account_name, account_purpose, cash_balance) VALUES (gen_random_uuid(), '$ClerkUserId', 'Test 401k', '401k', 0.00) RETURNING id;"
}

if ([string]::IsNullOrEmpty($accountId)) {
    Write-Host "ERROR: Failed to create or retrieve account" -ForegroundColor Red
    exit 1
}

Write-Host "Account ID: $accountId" -ForegroundColor Green

# Add test positions if needed
$positionCount = Invoke-PSQL -Command "SELECT COUNT(*) FROM positions p JOIN accounts a ON p.account_id = a.id WHERE a.clerk_user_id = '$ClerkUserId';"

if ($positionCount -eq "0") {
    Write-Host "Adding test positions (SPY, QQQ, BND)..." -ForegroundColor Yellow
    $sqlPositions = "INSERT INTO positions (id, account_id, symbol, quantity) VALUES (gen_random_uuid(), '$accountId', 'SPY', 10), (gen_random_uuid(), '$accountId', 'QQQ', 5), (gen_random_uuid(), '$accountId', 'BND', 20) ON CONFLICT DO NOTHING;"
    $null = Invoke-PSQL -Command $sqlPositions -Silent
}

Write-Host "User and account ready" -ForegroundColor Green
Write-Host ""

# Step 4: Create job
Write-Host "Step 2: Creating analysis job..." -ForegroundColor Yellow
$payloadJson = (@{
    analysis_type = "portfolio_analysis"
    options = @{}
} | ConvertTo-Json -Compress)

# Write SQL to temporary file to avoid quote escaping issues
$tempFile = [System.IO.Path]::GetTempFileName()
# Build SQL content - use single quotes around JSON, JSON itself has double quotes which is fine
$sqlContent = "INSERT INTO jobs (id, clerk_user_id, job_type, status, request_payload) VALUES (gen_random_uuid(), '$ClerkUserId', 'portfolio_analysis', 'pending', '$payloadJson'::jsonb) RETURNING id;"
# Write to file using UTF8 encoding
[System.IO.File]::WriteAllText($tempFile, $sqlContent, [System.Text.Encoding]::UTF8)

try {
    # Execute SQL from file
    $output = psql -h $DbHost -p $DbPort -U $DbUser -d $DbName -t -f $tempFile 2>&1
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -eq 0 -and $output) {
        $rawOutput = $output.Trim()
        Write-Host "Raw psql output: $rawOutput" -ForegroundColor Gray
        
        # Extract UUID from output (may include "INSERT 0 1" text)
        # Pattern: UUID format xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (case-insensitive)
        $uuidPattern = '([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
        
        $jobId = $null
        if ($rawOutput -match $uuidPattern) {
            if ($matches -and $matches.Count -gt 1) {
                $jobId = $matches[1]
                Write-Host "Extracted job ID: $jobId" -ForegroundColor Gray
            }
        }
        
        # If regex didn't work, try simpler extraction
        if ([string]::IsNullOrEmpty($jobId)) {
            # Split by whitespace and take first token (should be UUID)
            $tokens = $rawOutput -split '\s+'
            if ($tokens.Count -gt 0) {
                $firstToken = $tokens[0].Trim()
                # Verify it looks like a UUID
                if ($firstToken -match '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') {
                    $jobId = $firstToken
                    Write-Host "Extracted job ID from first token: $jobId" -ForegroundColor Gray
                }
            }
        }
        
        if ([string]::IsNullOrEmpty($jobId)) {
            Write-Host "WARNING: Could not extract job ID from output: $rawOutput" -ForegroundColor Yellow
        }
    } else {
        $jobId = $null
        Write-Host "ERROR: Database connection failed" -ForegroundColor Red
        Write-Host $output -ForegroundColor Red
    }
} finally {
    # Clean up temp file
    if (Test-Path $tempFile) {
        Remove-Item $tempFile -Force
    }
}

if ([string]::IsNullOrEmpty($jobId)) {
    # Fallback: try using psql with -v variable (avoids quote escaping)
    Write-Host "Trying alternative method with psql variables..." -ForegroundColor Yellow
    
    # Create a new temp file - try with dollar-quoting
    $tempFile2 = [System.IO.Path]::GetTempFileName()
    # Use dollar-quoting: $tag$content$tag$ to avoid quote escaping
    # Build the SQL by concatenation to avoid PowerShell variable expansion
    $dollarStart = '$json$'
    $dollarEnd = '$json$'
    $sqlContent2 = "INSERT INTO jobs (id, clerk_user_id, job_type, status, request_payload) VALUES (gen_random_uuid(), '$ClerkUserId', 'portfolio_analysis', 'pending', " + $dollarStart + $payloadJson + $dollarEnd + "::jsonb) RETURNING id;"
    [System.IO.File]::WriteAllText($tempFile2, $sqlContent2, [System.Text.Encoding]::UTF8)
    
    try {
        $output2 = psql -h $DbHost -p $DbPort -U $DbUser -d $DbName -t -f $tempFile2 2>&1
        $exitCode2 = $LASTEXITCODE
        
        if ($exitCode2 -eq 0 -and $output2) {
            $rawOutput2 = $output2.Trim()
            Write-Host "Alternative method output: $rawOutput2" -ForegroundColor Gray
            
            # Try regex first
            $uuidPattern2 = '([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
            if ($rawOutput2 -match $uuidPattern2) {
                if ($matches -and $matches.Count -gt 1) {
                    $jobId = $matches[1]
                    Write-Host "Successfully created job with alternative method: $jobId" -ForegroundColor Green
                }
            }
            
            # Fallback to first token
            if ([string]::IsNullOrEmpty($jobId)) {
                $tokens2 = $rawOutput2 -split '\s+'
                if ($tokens2.Count -gt 0) {
                    $firstToken2 = $tokens2[0].Trim()
                    if ($firstToken2 -match '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') {
                        $jobId = $firstToken2
                        Write-Host "Extracted job ID from first token: $jobId" -ForegroundColor Green
                    }
                }
            }
            
            if ([string]::IsNullOrEmpty($jobId)) {
                Write-Host "Alternative method also failed to extract job ID" -ForegroundColor Red
            }
        } else {
            Write-Host "Alternative method also failed:" -ForegroundColor Red
            Write-Host $output2 -ForegroundColor Red
        }
    } finally {
        if (Test-Path $tempFile2) {
            Remove-Item $tempFile2 -Force
        }
    }
}

if ([string]::IsNullOrEmpty($jobId)) {
    Write-Host "ERROR: Failed to create job" -ForegroundColor Red
    exit 1
}

# Ensure job ID is a clean UUID (remove any extra text)
$jobId = $jobId.Trim()
if ($jobId -match '([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})') {
    $jobId = $matches[1]
} else {
    Write-Host "ERROR: Invalid job ID format: $jobId" -ForegroundColor Red
    exit 1
}

Write-Host "Created job: $jobId" -ForegroundColor Green
Write-Host ""

# Step 5: Get authentication token
Write-Host "Step 3: Getting authentication token..." -ForegroundColor Yellow
try {
    $token = gcloud auth print-identity-token 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to get identity token. Run 'gcloud auth login' first." -ForegroundColor Red
        exit 1
    }
    Write-Host "Token obtained" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to get identity token: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 6: Trigger planner
Write-Host "Step 4: Triggering planner agent..." -ForegroundColor Yellow
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}
$body = @{
    job_id = $jobId
} | ConvertTo-Json

try {
    Write-Host "Sending POST request to $PlannerUrl..." -ForegroundColor Cyan
    Write-Host "Job ID being sent: $jobId" -ForegroundColor Gray
    Write-Host "Request body: $body" -ForegroundColor Gray
    $response = Invoke-WebRequest -Uri "$PlannerUrl/" -Method POST -Headers $headers -Body $body -TimeoutSec 300
    Write-Host "Planner triggered successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Response:" -ForegroundColor Cyan
    Write-Host $response.Content
} catch {
    Write-Host "ERROR: Failed to trigger planner" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response body: $responseBody" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Debugging info:" -ForegroundColor Yellow
    Write-Host "  Job ID: $jobId" -ForegroundColor Gray
    Write-Host "  Job ID length: $($jobId.Length)" -ForegroundColor Gray
    Write-Host "  Is valid UUID format: $($jobId -match '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')" -ForegroundColor Gray
    
    # Verify job exists in database
    Write-Host "  Verifying job exists in database..." -ForegroundColor Yellow
    $jobCheck = Invoke-PSQL -Command "SELECT id, status FROM jobs WHERE id = '$jobId';" -Silent
    if ($jobCheck) {
        Write-Host "  Job found in database: $jobCheck" -ForegroundColor Green
    } else {
        Write-Host "  Job NOT found in database!" -ForegroundColor Red
    }
    
    exit 1
}
Write-Host ""

# Step 7: Wait and check status
Write-Host "Step 5: Waiting for job to complete (30 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

Write-Host "Checking job status..." -ForegroundColor Yellow
$sqlCheckStatus = "SELECT id, status, CASE WHEN report IS NOT NULL THEN 'Yes' ELSE 'No' END as has_report, CASE WHEN charts IS NOT NULL THEN 'Yes' ELSE 'No' END as has_charts, CASE WHEN retirement IS NOT NULL THEN 'Yes' ELSE 'No' END as has_retirement, updated_at FROM jobs WHERE id = '$jobId';"
$jobStatus = Invoke-PSQL -Command $sqlCheckStatus
if ($jobStatus) {
    Write-Host $jobStatus
} else {
    Write-Host "Could not retrieve job status" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Test Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To view Cloud Run logs (most recent errors):" -ForegroundColor Yellow
    $projectId = $env:GCP_PROJECT_ID
    if ([string]::IsNullOrEmpty($projectId)) {
        $projectId = (gcloud config get-value project 2>$null)
    }
    if (-not [string]::IsNullOrEmpty($projectId)) {
        Write-Host "  gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=alex-planner' --limit 20 --project $projectId --format json" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Or view in console:" -ForegroundColor Yellow
        Write-Host "  https://console.cloud.google.com/run/detail/$($PlannerUrl.Split('/')[2].Split('.')[0])/alex-planner/logs?project=$projectId" -ForegroundColor Gray
    } else {
        Write-Host "  gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=alex-planner' --limit 20 --format json" -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "To check job details in database:" -ForegroundColor Yellow
    $checkCmd = "psql -h $DbHost -p $DbPort -U $DbUser -d $DbName -c `"SELECT id, status, error_message, updated_at FROM jobs WHERE id = '$jobId';`""
    Write-Host "  $checkCmd" -ForegroundColor Gray
