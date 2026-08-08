# Walkthrough - 10-Minute Scheduler Enablement

We checked the configuration files and verified the status of the scheduler configuration.

## Status of Changes
- The schedule expression in [main.tf](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/4_researcher/main.tf#L253) is configured for `rate(10 minutes)`.
- The variable `scheduler_enabled` is already set to `true` in [terraform.tfvars](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/4_researcher/terraform.tfvars#L20).

These settings are fully aligned to activate and create the EventBridge schedule resources upon the next deployment.

---

## Verification & Next Steps

### How to Deploy:
You can run the deployment from the `backend/researcher/` directory using `uv`:
```bash
cd backend/researcher
uv run deploy.py
```
*This will package your new scheduler zip, update the Docker image for the researcher, and apply the Terraform changes to enable the scheduler.*
