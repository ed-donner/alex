# Building Alex: Part 5 - Database & Shared Infrastructure

Welcome to Part 5! We're now entering the second phase of building Alex - transforming it from a research tool into a complete financial planning SaaS platform. In this guide, we'll set up Aurora Serverless v2 PostgreSQL with the Data API and create a reusable database library that all our AI agents will use.

## REMINDER - MAJOR TIP!!

There's a file `gameplan.md` in the project root that describes the entire Alex project to an AI Agent, so that you can ask questions and get help. There's also an identical `CLAUDE.md` and `AGENTS.md` file. If you need help, simply start your favorite AI Agent, and give it this instruction:

> I am a student on the course AI in Production. We are in the course repo. Read the file `gameplan.md` for a briefing on the project. Read this file completely and read all the linked guides carefully. Do not start any work apart from reading and checking directory structure. When you have completed all reading, let me know if you have questions before we get started.

After answering questions, say exactly which guide you're on and any issues. Be careful to validate every suggestion; always ask for the root cause and evidence of problems. LLMs have a tendency to jump to conclusions, but they often correct themselves when they need to provide evidence.

## Why Aurora Serverless v2 with Data API?

AWS offers several database options, each with different strengths:

### Common AWS Database Services

| Service           | Type            | Best For                                  | Why We Didn't Choose It                                     |
| ----------------- | --------------- | ----------------------------------------- | ----------------------------------------------------------- |
| **DynamoDB**      | NoSQL           | Simple key-value lookups, high-scale apps | No SQL joins, complex for relational data like portfolios   |
| **RDS (Regular)** | Traditional SQL | Predictable workloads, always-on apps     | Requires VPC/networking setup, always running = higher cost |
| **DocumentDB**    | Document NoSQL  | MongoDB-compatible apps                   | Overkill for structured financial data                      |
| **Neptune**       | Graph           | Social networks, recommendation engines   | Wrong fit - we don't need graph relationships               |
| **Timestream**    | Time-series     | IoT, metrics, logs                        | Too specialized for general portfolio data                  |

### Why Aurora Serverless v2 PostgreSQL?

We chose **Aurora Serverless v2 with Data API** because it offers:

1. **No VPC Complexity** - The Data API provides HTTP access, eliminating networking setup
2. **Scales to Zero** - Can pause after inactivity, reducing costs to ~$1.44/day minimum
3. **PostgreSQL** - Full SQL support with JSONB for flexible data (allocation percentages)
4. **Serverless** - Automatically scales with demand, perfect for learning projects
5. **Data API** - Direct HTTP access from Lambda without connection pools or VPC
6. **Pay-per-use** - Only pay for what you use, ideal for development

For students learning AWS, this removes the complexity of VPCs, security groups, and connection management while providing a production-grade database that works seamlessly with Lambda functions.

## What We're Building

In this guide, you'll deploy:

- Aurora Serverless v2 PostgreSQL cluster with Data API enabled (no VPC needed!)
- Complete database schema for portfolios, users, and reports
- Shared database package with Pydantic validation
- Seed data with 22 popular ETFs
- Database reset scripts for easy development

Here's how the database fits into our architecture:

```mermaid
graph TB
    User[User] -->|Manage Portfolio| API[API Gateway]
    API -->|CRUD Operations| Lambda[API Lambda]
    Lambda -->|Data API| Aurora[(Aurora Serverless v2<br/>PostgreSQL)]

    Planner[Financial Planner<br/>Orchestrator] -->|Read/Write| Aurora
    Tagger[InstrumentTagger] -->|Update Instruments| Aurora
    Reporter[Report Writer] -->|Store Reports| Aurora
    Charter[Chart Maker] -->|Store Charts| Aurora
    Retirement[Retirement Specialist] -->|Store Projections| Aurora

    style Aurora fill:#FF9900
    style Planner fill:#FFD700
    style API fill:#90EE90
```

## Prerequisites

Before starting, ensure you have:

- Completed Guides 1-4 (all infrastructure from Parts 1-4)
- AWS CLI configured
- Python with `uv` package manager installed
- Terraform installed
- Docker Desktop installed and running (for local testing)

## Step 0: Additional IAM Permissions

Since Guide 4, we need additional AWS permissions for Aurora and related services.

### Create Custom RDS Policy

1. Sign in to the AWS Console as your root user (just for IAM setup)
2. Navigate to **IAM** → **Policies**
3. Click **Create policy**
4. Click the **JSON** tab
5. Replace the content with:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RDSPermissions",
      "Effect": "Allow",
      "Action": [
        "rds:CreateDBCluster",
        "rds:CreateDBInstance",
        "rds:CreateDBSubnetGroup",
        "rds:DeleteDBCluster",
        "rds:DeleteDBInstance",
        "rds:DeleteDBSubnetGroup",
        "rds:DescribeDBClusters",
        "rds:DescribeDBInstances",
        "rds:DescribeDBSubnetGroups",
        "rds:DescribeGlobalClusters",
        "rds:ModifyDBCluster",
        "rds:ModifyDBInstance",
        "rds:ModifyDBSubnetGroup",
        "rds:AddTagsToResource",
        "rds:ListTagsForResource",
        "rds:RemoveTagsFromResource",
        "rds-data:ExecuteStatement",
        "rds-data:BatchExecuteStatement",
        "rds-data:BeginTransaction",
        "rds-data:CommitTransaction",
        "rds-data:RollbackTransaction"
      ],
      "Resource": "*"
    },
    {
      "Sid": "RDSServiceLinkedRole",
      "Effect": "Allow",
      "Action": "iam:CreateServiceLinkedRole",
      "Resource": "*",
      "Condition": {
        "StringLike": {
          "iam:AWSServiceName": [
            "rds.amazonaws.com",
            "rds.application-autoscaling.amazonaws.com"
          ]
        }
      }
    },
    {
      "Sid": "EC2Permissions",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeVpcs",
        "ec2:DescribeVpcAttribute",
        "ec2:DescribeSubnets",
        "ec2:DescribeAvailabilityZones",
        "ec2:DescribeSecurityGroups",
        "ec2:CreateSecurityGroup",
        "ec2:DeleteSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:AuthorizeSecurityGroupEgress",
        "ec2:RevokeSecurityGroupIngress",
        "ec2:RevokeSecurityGroupEgress",
        "ec2:CreateTags",
        "ec2:DescribeTags"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SecretsManagerPermissions",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:DeleteSecret",
        "secretsmanager:DescribeSecret",
        "secretsmanager:GetSecretValue",
        "secretsmanager:GetResourcePolicy",
        "secretsmanager:PutSecretValue",
        "secretsmanager:UpdateSecret",
        "secretsmanager:TagResource",
        "secretsmanager:UntagResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "KMSPermissions",
      "Effect": "Allow",
      "Action": [
        "kms:CreateGrant",
        "kms:Decrypt",
        "kms:DescribeKey",
        "kms:Encrypt"
      ],
      "Resource": "*"
    }
  ]
}
```

6. Click **Next: Tags**, then **Next: Review**
7. For **Policy name**, enter: `AlexRDSCustomPolicy`
8. For **Description**, enter: `RDS and Data API permissions for Alex project`
9. Click **Create policy**

### Add Required AWS Managed Policies

1. Still in IAM, click **User groups** in the left sidebar
2. Click on the `AlexAccess` group (created in Guide 1)
3. Click **Permissions** tab, then **Add permissions** → **Attach policies**
4. Search for and select these AWS managed policies:
   - `AmazonRDSDataFullAccess`
   - `AWSLambda_FullAccess`
   - `AmazonSQSFullAccess`
   - `AmazonEventBridgeFullAccess`
   - `SecretsManagerReadWrite`
5. Also select the custom policy you just created:
   - `AlexRDSCustomPolicy`
6. Click **Add permissions**

### Verify Permissions

Sign out and sign back in with your IAM user, then verify:

```bash
# Should return empty list or existing clusters
aws rds describe-db-clusters

# Should show the command exists and list required parameters
aws rds-data execute-statement --help
# You should see: "the following arguments are required: --resource-arn, --secret-arn, --sql"
# This confirms the Data API commands are available
```

## Step 1: Deploy Aurora Serverless v2

Now let's deploy the database infrastructure with Terraform.

### Configure and Deploy the Database

```bash
# Starting from the project root (alex directory)
cd terraform/5_database

# Copy the example variables file
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and set your values:

```hcl
aws_region = "us-east-1"  # Your AWS region
min_capacity = 0.5        # Minimum ACUs (0.5 = ~$43/month)
max_capacity = 1.0        # Maximum ACUs (keep low for dev)
```

Deploy the database:

```bash
# Initialize Terraform (creates local state file)
terraform init

# Deploy the database infrastructure
terraform apply
```

Type `yes` when prompted. This will create:

- Aurora Serverless v2 cluster with Data API enabled
- Database credentials in Secrets Manager
- Security group and subnet configuration
- The `alex` database

Deployment takes about 10-15 minutes. After deployment, Terraform will display important outputs including the cluster ARN and secret ARN.

### Save Your Configuration

**Important**: Update your `.env` file with the database values:

1. View the Terraform outputs:

   ```bash
   terraform output
   ```

2. Edit the `.env` file in your project root:

   - In Cursor's file explorer, click on the `.env` file in the alex directory
   - If you don't see it, make sure hidden files are visible (Cmd+Shift+. on Mac, Ctrl+H on Linux/Windows)

3. Add these lines with values from Terraform output:
   ```
   # Part 5 - Database
   AURORA_CLUSTER_ARN=arn:aws:rds:us-east-1:123456789012:cluster:alex-aurora-cluster
   AURORA_SECRET_ARN=arn:aws:secretsmanager:us-east-1:123456789012:secret:alex-aurora-credentials-xxxxx
   ```

💡 **Tip**: The exact ARN values are shown in your Terraform output. Copy them carefully!

## Step 2: Initialize the Database

Now let's test the connection and create our schema.

```bash
# Starting from the project root (alex directory)
cd backend/database

# Test the Data API connection
uv run test_data_api.py
```

You should see:

```
✅ Successfully connected to Aurora using Data API!
Database version: PostgreSQL 15.x
```

## Step 3: Run Database Migrations

Create the database schema:

```bash
# From backend/database directory
uv run run_migrations.py
```

You should see:

```
Starting migration: 001_schema.sql
✅ Migration completed successfully
All migrations completed!
```

## Step 4: Load Seed Data

Now let's populate the instruments table with 22 popular ETFs:

```bash
# From backend/database directory
uv run seed_data.py
```

You should see:

```
Seeding 22 instruments...
✅ SPY - SPDR S&P 500 ETF
✅ QQQ - Invesco QQQ Trust
✅ BND - Vanguard Total Bond Market ETF
[... more ETFs ...]
✅ Successfully seeded 22 instruments
```

## Step 5: Create Test Data (Optional)

For development, let's create a test user with a sample portfolio:

```bash
# From backend/database directory
uv run reset_db.py --with-test-data
```

You should see:

```
Dropping all tables...
Running migrations...
Loading default instruments...
Creating test user with portfolio...
✅ Database reset complete with test data!

Test user created:
- User ID: test_user_001
- Display Name: Test User
- 3 accounts (401k, Roth IRA, Taxable)
- 5 positions in 401k account
```

## Step 6: Verify Database Integrity

Finally, run the verification script to get a full report on the database's health. This is a valuable check to confirm
everything is set up correctly before you proceed to Part 6.

```bash
1 # From backend/database directory
2 uv run verify_database.py
```

The script will output a detailed report summarizing table counts, data integrity, and more. The key thing to look for is the
final confirmation banner at the end of the report:

```bash
---
🎉 DATABASE VERIFICATION COMPLETE
---
✅ All tables created successfully
✅ Instruments loaded with complete allocation data
✅ All allocation percentages sum to 100%
✅ Indexes and triggers are in place
✅ Database is ready for Part 6: Agent Orchestra!
```

## Understanding the Database Schema

Our schema includes five tables with clear separation between user-specific and shared reference data:

```mermaid
erDiagram
    users ||--o{ accounts : "owns"
    users ||--o{ jobs : "requests"
    accounts ||--o{ positions : "contains"
    positions }o--|| instruments : "references"

    users {
        varchar clerk_user_id PK
        varchar display_name
        integer years_until_retirement
        decimal target_retirement_income
        jsonb asset_class_targets
        jsonb region_targets
    }

    accounts {
        uuid id PK
        varchar clerk_user_id FK
        varchar account_name
        text account_purpose
        decimal cash_balance
        decimal cash_interest
    }

    positions {
        uuid id PK
        uuid account_id FK
        varchar symbol FK
        decimal quantity
        date as_of_date
    }

    instruments {
        varchar symbol PK
        varchar name
        varchar instrument_type
        decimal current_price
        jsonb allocation_regions
        jsonb allocation_sectors
        jsonb allocation_asset_class
    }

    jobs {
        uuid id PK
        varchar clerk_user_id FK
        varchar job_type
        varchar status
        jsonb request_payload
        jsonb report_payload
        jsonb charts_payload
        jsonb retirement_payload
        jsonb summary_payload
        text error_message
        timestamp started_at
        timestamp completed_at
    }
```

### Table Descriptions

- **users**: Minimal user data (Clerk handles auth)
- **instruments**: ETFs, stocks, and funds with current prices and allocation data (shared reference data)
- **accounts**: User's investment accounts (401k, IRA, etc.)
- **positions**: Holdings in each account
- **jobs**: Async job tracking for analysis requests with separate fields for each agent's output:
  - `report_payload`: Reporter agent's markdown analysis
  - `charts_payload`: Charter agent's visualization data
  - `retirement_payload`: Retirement agent's projections
  - `summary_payload`: Planner's final summary and metadata

All data is validated through Pydantic schemas before database insertion, ensuring data integrity. Each agent writes its results to its own dedicated JSONB field in the `jobs` table, eliminating the need for complex merging logic. Agent execution tracking is handled by LangFuse and CloudWatch Logs, not in the database.

## Cost Management

Aurora Serverless v2 costs approximately:

- **Minimum capacity (0.5 ACU)**: ~$43/month
- **Running normally**: $1.44-$2.88/day

### Managing Costs

To minimize costs when not actively developing:

```bash
# To completely destroy the database and stop all charges:
cd terraform/5_database
terraform destroy

# To recreate the database later:
terraform apply
```

⚠️ **Warning**: `terraform destroy` will delete your database and all data. Only do this when you're done with development or taking a break.

**Recommendation**: Complete Parts 5-8 within 3-5 days, then destroy to avoid ongoing charges.

## Troubleshooting

### Data API Connection Issues

If you can't connect to the Data API:

1. **Check cluster status**:

```bash
aws rds describe-db-clusters --db-cluster-identifier alex-aurora-cluster
```

Status should be "available"

2. **Check Data API is enabled**:

```bash
aws rds describe-db-clusters --db-cluster-identifier alex-aurora-cluster --query 'DBClusters[0].EnableHttpEndpoint'
```

Should return `true`

3. **Verify secrets** (the secret name includes a random suffix):

```bash
# List all secrets to find the correct name
aws secretsmanager list-secrets --query "SecretList[?contains(Name, 'alex-aurora-credentials')].Name"

# Then get the secret value (replace with actual name from above)
aws secretsmanager get-secret-value --secret-id alex-aurora-credentials-xxxxx --query SecretString --output text | jq .
```

Should show username and password

### Migration Failures

If migrations fail:

1. **Check SQL syntax**:

```bash
# From the backend/database directory
# Migrations are in the migrations subdirectory
cat migrations/001_schema.sql
```

2. **Reset and retry**:

```bash
# From the backend/database directory
uv run reset_db.py
# This will drop all tables, run migrations, and reload seed data
```

### Pydantic Validation Errors

If you see validation errors:

1. **Check allocation sums**:
   All allocation dictionaries must sum to 100.0

2. **Check Literal types**:
   Only use allowed values for regions, sectors, and asset classes

3. **Review schema definitions**:

```bash
# From the backend/database directory
cat src/schemas.py
```

## Next Steps

Excellent! You now have a production-grade database with:

- ✅ Aurora Serverless v2 with Data API (no VPC complexity!)
- ✅ Complete schema for financial data
- ✅ Pydantic validation for all data
- ✅ 22 ETFs with allocation data
- ✅ Shared database package for all agents

Continue to [6_agents.md](6_agents.md) where we'll build the AI agent orchestra that uses this database to provide comprehensive financial analysis!

Your database is ready and waiting for the agents! 🚀
