# Plan: Update Researcher Model to Nova Pro

## Goal Description
The researcher agent fails with a `500 Server Error` on invocation because LiteLLM throws an `UnsupportedParamsError` indicating that the configured model `global.openai.gpt-oss-120b-1:0` does not support the `tools` parameter. 

The researcher agent must use tool calling to browse the web (via the Playwright MCP server) and store research (via the ingest pipeline tool). Because the default model `global.openai.gpt-oss-120b-1:0` cannot use tools, we need to switch the model to **Amazon Nova Pro** (`bedrock/us.amazon.nova-pro-v1:0`), which is fully supported and supports tool calling.

We will achieve this by explicitly setting the `researcher_model` variable in `terraform.tfvars` and redeploying.

---

## User Review Required
Ensure that you have requested and been granted model access to **Amazon Nova Pro** in the **us-west-2** (Oregon) region in your AWS Bedrock console.

---

## Proposed Changes

### Researcher Terraform Configuration
Update [terraform.tfvars](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/4_researcher/terraform.tfvars) to set `researcher_model` to `"bedrock/us.amazon.nova-pro-v1:0"`.

#### [MODIFY] [terraform.tfvars](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/4_researcher/terraform.tfvars)

```diff
 # Enable automated research scheduler (optional, default is false)
 scheduler_enabled = false
+
+# Configure the researcher to use the Nova Pro model (supports tool calling)
+researcher_model = "bedrock/us.amazon.nova-pro-v1:0"
```

---

## Verification Plan

### Automated Tests
1. Redeploy the Researcher service:
   ```bash
   cd backend/researcher
   uv run deploy.py
   ```
   *This will run `terraform apply` to update the Lambda's environment variables.*

### Manual Verification
1. Run the research test script to verify that the agent successfully uses tools and completes research:
   ```bash
   cd backend/researcher
   uv run test_research.py
   ```
