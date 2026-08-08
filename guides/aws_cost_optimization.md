# Project Alex: AWS Cost Optimization Guide 💰

This guide provides practical, production-ready strategies to minimize monthly AWS charges for Project Alex while keeping the SaaS platform fast, responsive, and reliable.

---

## Executive Cost Breakdown

The following table summarizes the estimated monthly cost by service for a standard development environment:

| Service / Component | Default Setup (24/7) | Optimized Setup | Potential Savings |
| :--- | :--- | :--- | :--- |
| **Aurora Serverless v2 PostgreSQL** | ~$45 - $90 / mo (0.5 - 2.0 ACU) | ~$0 - $15 / mo (Auto-pause / destroy) | **80% - 100%** |
| **App Runner (Research Agent)** | ~$25 - $35 / mo (1 vCPU / 2GB) | ~$0 - $5 / mo (Pause service) | **80% - 100%** |
| **SageMaker Serverless Endpoint** | ~$5 - $10 / mo | ~$1 - $3 / mo (Serverless usage only) | **50%** |
| **LLM Inference (AWS Bedrock)** | ~$20 - $50 / mo (Claude Sonnet) | ~$3 - $10 / mo (Amazon Nova Pro) | **80%** |
| **S3 Vectors (Knowledge Base)** | ~$1 - $3 / mo | ~$0.50 / mo | **50%** *(vs OpenSearch $90+/mo)* |
| **Lambda & API Gateway** | Free Tier / ~$1 - $3 / mo | Free Tier / < $1 / mo | **50%** |
| **CloudFront & S3 Frontend** | Free Tier / < $1 / mo | Free Tier / $0 / mo | **100%** |
| **CloudWatch Logs & Dashboard** | ~$5 - $15 / mo (Infinite log retention) | ~$1 - $2 / mo (7-day retention) | **80%** |
| **TOTAL ESTIMATED MONTHLY BILL** | **~$100 - $200 / mo** | **~$5 - $25 / mo** | **85% SAVINGS** |

---

## 1. Aurora Serverless v2 (Database) Optimization

Aurora Serverless v2 is the single largest cost driver because it runs 24/7 by default.

### Option A: Stop/Pause the Aurora Cluster When Inactive
When taking breaks or outside working hours, stop the cluster via AWS CLI or AWS Console:

```bash
# Stop Aurora Cluster (Stops billing for ACUs, only pay for storage ~$0.10/GB)
aws rds stop-db-cluster --db-cluster-identifier alex-aurora-cluster

# Start Aurora Cluster when ready to resume development
aws rds start-db-cluster --db-cluster-identifier alex-aurora-cluster
```

### Option B: Set ACU Capacity Floor to 0.5 ACU
In `terraform/5_database/main.tf`, verify that `min_capacity` is set to `0.5`:

```hcl
serverlessv2_scaling_configuration {
  min_capacity = 0.5   # Minimum possible scale (~$0.06/hour)
  max_capacity = 2.0   # Cap maximum burst to prevent unexpected billing spikes
}
```

### Option C: Destroy Database Infrastructure During Extended Breaks
If you won't be working on Project Alex for several days or weeks, destroy the database terraform stack:

```bash
cd terraform/5_database
terraform destroy
```

---

## 2. App Runner (Researcher Agent) Optimization

AWS App Runner bills for provisioned memory even when idle.

### Option A: Pause the App Runner Service
Pause the service when you aren't testing market research agents:

```bash
# Get App Runner Service ARN
SERVICE_ARN=$(aws apprunner list-services --query "ServiceSummaryList[?ServiceName=='alex-researcher'].ServiceArn" --output text)

# Pause Service (Stops vCPU & Memory billing completely)
aws apprunner pause-service --service-arn $SERVICE_ARN

# Resume Service when testing research features
aws apprunner resume-service --service-arn $SERVICE_ARN
```

### Option B: Destroy App Runner Stack
```bash
cd terraform/4_researcher
terraform destroy
```

---

## 3. Bedrock LLM Model Optimization (Nova Pro vs Claude Sonnet)

AWS Bedrock pricing depends heavily on the model invoked.

- **Claude 3.5 Sonnet**: ~$3.00 / 1M input tokens, ~$15.00 / 1M output tokens.
- **Amazon Nova Pro**: ~$0.80 / 1M input tokens, ~$3.20 / 1M output tokens (**~75-80% cheaper!**).

### Recommendation:
Ensure all agent configurations in `backend/` and `terraform/6_agents/terraform.tfvars` use the **Nova Pro** inference profile (`us.amazon.nova-pro-v1:0` or `eu.amazon.nova-pro-v1:0`).

---

## 4. Market Data Caching (Polygon API & DB Calls)

Project Alex includes an L1 memory and L2 UNLOGGED PostgreSQL market cache (`market_data_cache`).

### Recommendation:
- Populate the cache using `backend/database/seed_cache.py` during development:
  ```bash
  cd backend/database
  uv run seed_cache.py
  ```
- Cached reads prevent redundant Polygon API calls and eliminate unnecessary agent execution turns, directly lowering Bedrock LLM token consumption.

---

## 5. CloudWatch Logs Retention Optimization

By default, CloudWatch log groups retain log streams indefinitely, incurring ongoing storage fees.

### Action: Update Retention to 7 Days
In `terraform/6_agents/main.tf` and `terraform/7_frontend/main.tf`, enforce a 7-day log retention policy:

```hcl
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/alex-api"
  retention_in_days = 7   # Automatically delete logs after 7 days
}
```

Or set retention across existing log groups via AWS CLI:

```bash
aws logs put-retention-policy --log-group-name /aws/lambda/alex-planner --retention-in-days 7
aws logs put-retention-policy --log-group-name /aws/lambda/alex-api --retention-in-days 7
```

---

## 6. Complete Clean Teardown Command (End of Week / Off-Hours)

When you are done testing for the day/week, run teardown in reverse order:

```bash
# Teardown non-essential infrastructure to eliminate 95%+ of costs:
cd terraform/8_enterprise && terraform destroy -auto-approve
cd terraform/7_frontend && terraform destroy -auto-approve
cd terraform/6_agents && terraform destroy -auto-approve
cd terraform/5_database && terraform destroy -auto-approve    # Major savings ($45-90/mo)
cd terraform/4_researcher && terraform destroy -auto-approve  # Major savings ($25-35/mo)
cd terraform/3_ingestion && terraform destroy -auto-approve
cd terraform/2_sagemaker && terraform destroy -auto-approve
```

---

## Summary Checklist for Lowest AWS Bill

1. **Stop Aurora PostgreSQL** (`aws rds stop-db-cluster`) or run `terraform destroy` in `5_database` when not coding.
2. **Pause App Runner** (`aws apprunner pause-service`) when research agents are idle.
3. **Use Amazon Nova Pro** instead of Claude Sonnet for Bedrock LLM calls.
4. **Use S3 Vectors & UNLOGGED Market Cache** to minimize embedding and model invocation costs.
5. **Set CloudWatch Log Retention to 7 days**.
