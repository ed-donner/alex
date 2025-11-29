# Phase 5: Database Setup (Cloud SQL - Equivalent to AWS RDS)

## Overview

This guide sets up Cloud SQL PostgreSQL on GCP, which is the equivalent of AWS RDS PostgreSQL.

## AWS vs GCP Comparison

| AWS RDS | GCP Cloud SQL |
|---------|---------------|
| RDS PostgreSQL | Cloud SQL PostgreSQL |
| Multi-AZ | High Availability Configuration |
| Read Replicas | Read Replicas |
| Parameter Groups | Database Flags |
| Security Groups | Firewall Rules / Authorized Networks |
| RDS Proxy | Cloud SQL Auth Proxy |
| IAM Authentication | IAM Database Authentication |

## Steps

### Step 1: Deploy Terraform

**Enable required APIs (if not already enabled):**

**For Linux/Mac (Bash):**
```bash
gcloud services enable sqladmin.googleapis.com servicenetworking.googleapis.com --project=YOUR_PROJECT_ID
```

**For Windows (PowerShell):**
```powershell
gcloud services enable sqladmin.googleapis.com servicenetworking.googleapis.com --project=YOUR_PROJECT_ID
```

**For Linux/Mac (Bash):**
```bash
cd terraform/5_database/
terraform init
terraform plan
terraform apply
```

**For Windows (PowerShell):**
```powershell
cd "alex-gcp\terraform\5_database"
terraform init
terraform plan
terraform apply
```

### Step 2: Connect to Database

**Option A: Using Cloud SQL Auth Proxy (Recommended)**

**For Linux/Mac (Bash):**
```bash
# Install Cloud SQL Auth Proxy
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.linux.amd64
chmod +x cloud-sql-proxy

# Start proxy (public IP enabled on the instance)
./cloud-sql-proxy --port 5432 PROJECT_ID:REGION:INSTANCE_NAME

# Connect via psql (use the same port you set above)
psql "host=127.0.0.1 port=5432 user=postgres dbname=alex"
```

**For Windows (PowerShell):**
```powershell
# Download Cloud SQL Auth Proxy (Windows x64)
Invoke-WebRequest `
  -Uri "https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.x64.exe" `
  -OutFile "cloud-sql-proxy.exe"

# Make sure port 5432 is free. Check with:
# netstat -ano | findstr 5432
# If another process is using it, either stop that process or pick a different local port (e.g. 5433)

# Start proxy (change --port if 5432 is taken)
.\cloud-sql-proxy.exe --port 5432 PROJECT_ID:REGION:INSTANCE_NAME

# If 127.0.0.1 binding fails due to security policies, bind to 0.0.0.0:
# .\cloud-sql-proxy.exe --address 0.0.0.0 --port 5433 PROJECT_ID:REGION:INSTANCE_NAME

# Connect via psql (use the same host/port you set above)
Use gcloud secrets versions access latest --secret=alex-db-password to retrieve the password.
psql "host=127.0.0.1 port=5432 user=postgres dbname=alex"
# If you used --address 0.0.0.0 and port 5433:
# psql "host=127.0.0.1 port=5433 user=postgres dbname=alex"

# Important: Keep the proxy window open. Pressing Ctrl+C stops the proxy and any client connections will immediately drop.
#
# Tip: Run the proxy in a separate PowerShell window so you can keep working:
# Start-Process powershell -ArgumentList '-NoExit','-Command','cd "C:\path\to\project\alex-gcp\terraform\5_database"; .\cloud-sql-proxy.exe --address 0.0.0.0 --port 5433 PROJECT_ID:REGION:INSTANCE_NAME'
```

**Option B: Using Private IP (within VPC)**

```bash
psql "host=PRIVATE_IP port=5432 user=postgres dbname=alex"
```

> **Important:** Option B only works for clients running **inside the same VPC** (Cloud Run, GCE, etc.). For local development, either enable a public IP (set `enable_public_ip = true` in `terraform.tfvars` and add your home IP to `authorized_networks`) or run the proxy from a VM inside the VPC.

### Step 3: Database Initialization

Run the initialization script located at `backend/database/migrations/001_schema.sql`:

**For Linux/Mac (Bash):**
```bash
psql -h 127.0.0.1 -U postgres -d alex -f backend/database/migrations/001_schema.sql
```

**For Windows (PowerShell):**
```powershell
psql -h 127.0.0.1 -U postgres -d alex -f ".\backend\database\migrations\001_schema.sql"
```

### Step 4: Connection from Cloud Run

In your Cloud Run service, use the Cloud SQL connector:

```python
import os
from google.cloud.sql.connector import Connector
import pg8000
import sqlalchemy

def get_connection():
    connector = Connector()
    
    def getconn():
        conn = connector.connect(
            os.environ["INSTANCE_CONNECTION_NAME"],
            "pg8000",
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASS"],
            db=os.environ["DB_NAME"],
        )
        return conn
    
    pool = sqlalchemy.create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )
    return pool
```

### Step 5: Set Up Secrets

**Get the Cloud Run service account email (needed for secret access):**

**Method 1 – Terraform output (recommended)**
```bash
cd terraform/1_permissions/
terraform output cloud_run_service_account_email
```

**Method 2 – gcloud command**
```bash
gcloud iam service-accounts list \
  --project=YOUR_PROJECT_ID \
  --filter="email:cloud-run-sa" \
  --format="value(email)"
```

**Method 3 – Construct manually**
- Pattern: `cloud-run-sa@<project-id>.iam.gserviceaccount.com`
- Example: `cloud-run-sa@alex-multi-agent-saas-479504.iam.gserviceaccount.com`

Store database credentials in Secret Manager:

**For Linux/Mac (Bash):**
```bash
# Create secrets
echo -n "your_password" | gcloud secrets create db-password --data-file=-
echo -n "postgres" | gcloud secrets create db-user --data-file=-

# Grant access to Cloud Run service account
gcloud secrets add-iam-policy-binding db-password \
    --member="serviceAccount:cloud-run-sa@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

**For Windows (PowerShell):**
```powershell
# Create secrets
"your_password" | Set-Content -Path "$env:TEMP\db-password.txt" -NoNewline
"postgres" | Set-Content -Path "$env:TEMP\db-user.txt" -NoNewline

gcloud secrets create db-password --data-file="$env:TEMP\db-password.txt"
gcloud secrets create db-user --data-file="$env:TEMP\db-user.txt"

Remove-Item "$env:TEMP\db-password.txt","$env:TEMP\db-user.txt"

# Grant access to Cloud Run service account
gcloud secrets add-iam-policy-binding db-password `
    --member="serviceAccount:cloud-run-sa@PROJECT_ID.iam.gserviceaccount.com" `
    --role="roles/secretmanager.secretAccessor"
```

## Database Schema Example

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    clerk_id VARCHAR(255) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Conversations table
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Messages table
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    tokens_used INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
```

## Backup and Recovery

```bash
# Create on-demand backup
gcloud sql backups create --instance=alex-postgres --project=YOUR_PROJECT_ID

# List backups
gcloud sql backups list --instance=alex-postgres --project=YOUR_PROJECT_ID

# Restore from backup
gcloud sql backups restore BACKUP_ID --restore-instance=alex-postgres --project=YOUR_PROJECT_ID
```

> **Tip:** If you see `HTTPError 404` when creating backups, run `gcloud config set project YOUR_PROJECT_ID` and make sure the authenticated account has Cloud SQL permissions for that project.

## Troubleshooting

### Service Networking API not enabled
```bash
# Enable API (required for private service access)
gcloud services enable servicenetworking.googleapis.com --project=YOUR_PROJECT_ID

# Wait 2-3 minutes for propagation, then rerun terraform apply
```

### Cloud SQL Proxy can't bind to port 5432 (Windows)
```powershell
# Check which processes are using the port
netstat -ano | findstr 5432

# Option A: Stop the process that's using 5432 (e.g., local Postgres service)
# Option B: Start the proxy on a different port (e.g., 5433)
.\cloud-sql-proxy.exe --port 5433 PROJECT_ID:REGION:INSTANCE_NAME

# Then connect with psql using the same port
psql "host=127.0.0.1 port=5433 user=postgres dbname=alex"
```

### Connection Issues
```bash
# Check instance status
gcloud sql instances describe alex-postgres

# Check authorized networks
gcloud sql instances describe alex-postgres --format="value(settings.ipConfiguration.authorizedNetworks)"

# Test connectivity
pg_isready -h INSTANCE_IP -p 5432
```

### Performance Issues
```bash
# Check slow queries
SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;

# Check connections
SELECT count(*) FROM pg_stat_activity;
```

## Next Steps

After setting up the database, proceed to [6_agents.md](6_agents.md) for agent deployment.
