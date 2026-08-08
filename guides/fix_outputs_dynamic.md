# Plan: Make Scheduler Outputs Dynamic

## Goal Description
Yes, the message is a hardcoded string inside your [outputs.tf](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/4_researcher/outputs.tf) file. Even though the actual schedule in AWS is updated to run every 10 minutes, the output text still says "Running every 2 hours".

We will modify [outputs.tf](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/4_researcher/outputs.tf) to dynamically query and display the `schedule_expression` value from the `aws_scheduler_schedule.research_schedule` resource.

---

## User Review Required
No breaking changes. This only makes the Terraform output messages dynamic.

---

## Proposed Changes

### Researcher Terraform Outputs
Modify [outputs.tf](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/4_researcher/outputs.tf) to interpolate `aws_scheduler_schedule.research_schedule[0].schedule_expression`.

#### [MODIFY] [outputs.tf](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/4_researcher/outputs.tf)

```diff
 output "scheduler_status" {
   description = "Status of the automated scheduler"
   value = !local.researcher_deployed ? "Disabled - deploy the researcher image first" : (
-    var.scheduler_enabled ? "Enabled - Running every 2 hours" : "Disabled"
+    var.scheduler_enabled ? "Enabled - Running ${aws_scheduler_schedule.research_schedule[0].schedule_expression}" : "Disabled"
   )
 }
 
 output "setup_instructions" {
   description = "Instructions for completing setup"
   value = local.researcher_deployed ? format(
     "✅ Researcher service deployed successfully!\n\nService URL: %s\n\nTest the researcher:\ncurl %s/health\n\n%s",
     aws_lambda_function_url.researcher[0].function_url,
     trimsuffix(aws_lambda_function_url.researcher[0].function_url, "/"),
-    var.scheduler_enabled ? "⏰ Automated research is running every 2 hours" : "💡 To enable automated research, set scheduler_enabled = true"
+    var.scheduler_enabled ? "⏰ Automated research is running ${aws_scheduler_schedule.research_schedule[0].schedule_expression}" : "💡 To enable automated research, set scheduler_enabled = true"
   ) : "Run 'uv run deploy.py' to build, push, and deploy the researcher image."
 }
```

---

## Verification Plan

### Automated Tests
1. Run `terraform plan` in the `terraform/4_researcher/` directory and check that the outputs are updated:
   ```bash
   cd terraform/4_researcher
   terraform plan
   ```
2. Verify that the output shows `Running rate(10 minutes)` or similar.
