# Plan: Enable 10-Minute Scheduler Execution

## Goal Description
We will enable the automated EventBridge scheduler in AWS to trigger the scheduler Lambda function every 10 minutes, which in turn calls the Researcher Lambda.

Currently:
1. The schedule expression in [main.tf](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/4_researcher/main.tf) is already set to `rate(10 minutes)`.
2. However, the scheduler resources are disabled because `scheduler_enabled` is set to `false` in [terraform.tfvars](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/4_researcher/terraform.tfvars).

We will set `scheduler_enabled = true` to activate and deploy the schedule, EventBridge role, and the scheduler Lambda resources.

---

## User Review Required
No breaking changes. This will create and deploy the EventBridge schedule resources on AWS.

---

## Proposed Changes

### Researcher Configuration
Modify [terraform.tfvars](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/4_researcher/terraform.tfvars) to set `scheduler_enabled` to `true`.

#### [MODIFY] [terraform.tfvars](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/4_researcher/terraform.tfvars)

```diff
 # API key from Part 3 (get from API Gateway console)
 alex_api_key = "JZzy8YKx6c9HTBxUxQiJl1DYzJutqLuI6Hj2f6Dy"
 
 # Enable automated research scheduler (optional, default is false)
-scheduler_enabled = false
+scheduler_enabled = true
```

---

## Verification Plan

### Automated Tests
1. Deploy the updated Terraform configurations containing the scheduler:
   ```bash
   cd backend/researcher
   uv run deploy.py
   ```
   *This will compile and upload the researcher image, package the scheduler zip file if needed, and run `terraform apply`.*

### Manual Verification
1. Open the AWS Console (in `us-west-2` or your default region).
2. Navigate to **Amazon EventBridge** -> **Schedules**.
3. Verify that `alex-research-schedule` is present and active, with the expression `rate(10 minutes)`.
4. Wait 10 minutes and check the CloudWatch logs for the `alex-researcher-scheduler` and `alex-researcher` Lambda functions to verify they triggered successfully.
