# Phase 2: Vertex AI Setup (Equivalent to AWS SageMaker)

## Overview

This guide sets up Vertex AI on GCP, which is the equivalent of AWS SageMaker. Vertex AI provides:
- Model training and deployment
- Access to foundation models (Gemini 2.0 Flash recommended, Claude optional)
- MLOps pipelines
- Custom model hosting

**Recommended Model: Gemini 2.0 Flash**
- **Cost-effective**: Significantly cheaper than Claude models in Vertex AI
- **Fast**: Optimized for speed and efficiency
- **Native GCP integration**: Uses Application Default Credentials (no API keys needed)
- **Full feature support**: Supports all OpenAI Agents SDK features via LiteLLM

## AWS vs GCP Comparison

| AWS SageMaker | GCP Vertex AI |
|---------------|---------------|
| SageMaker Endpoints | Vertex AI Endpoints |
| SageMaker Notebooks | Vertex AI Workbench |
| SageMaker Training Jobs | Vertex AI Training |
| Bedrock (LLMs) | Model Garden / Generative AI |
| SageMaker Pipelines | Vertex AI Pipelines |
| SageMaker Feature Store | Vertex AI Feature Store |

## Model Options on GCP

**Recommended: Gemini 2.0 Flash (Default)**
- Native Vertex AI integration
- Cost-effective pricing
- No API keys required (uses ADC)
- Full LiteLLM support

**Alternative: OpenAI API (via Secret Manager)**
- Use OpenAI models (GPT-4o, GPT-4o-mini, etc.) alongside Gemini
- API keys stored securely in Secret Manager
- Good for specific use cases requiring GPT models

**Optional: Claude (Higher Cost)**
- Available via Anthropic API (requires API key)
- More expensive than Gemini in Vertex AI
- Enable with `enable_anthropic_api = true` in terraform

## Steps

### Step 1: Enable Required APIs

**Important:** Ensure all required APIs from [Phase 1](1_permissions.md) are enabled, plus the Vertex AI API.

**For Linux/Mac (Bash):**
```bash
# Enable Vertex AI API (required for this phase)
gcloud services enable aiplatform.googleapis.com --project=YOUR_PROJECT_ID

# Verify all required APIs are enabled
gcloud services list --enabled --project=YOUR_PROJECT_ID
```

**For Windows (PowerShell):**
```powershell
# Enable Vertex AI API (required for this phase)
gcloud services enable aiplatform.googleapis.com --project=alex-multi-agent-saas-479504

# Verify all required APIs are enabled
gcloud services list --enabled --project=alex-multi-agent-saas-479504
```

**Required APIs for this phase:**
- `aiplatform.googleapis.com` (Vertex AI API)
- `secretmanager.googleapis.com` (Secret Manager API - for API keys)
- All APIs from Phase 1 (compute, run, cloudfunctions, sqladmin, artifactregistry, etc.)

**If you get API errors during terraform apply:**
1. Enable the missing API: `gcloud services enable <API_NAME> --project=YOUR_PROJECT_ID`
2. Wait 2-3 minutes for propagation
3. Retry `terraform apply`

### Step 2: Deploy Terraform

**Prerequisites:** Complete [Phase 1: Permissions Setup](1_permissions.md) first, as this step requires the Vertex AI service account.

**Get the Vertex AI Service Account Email:**

You'll need the service account email from Phase 1. Get it using one of these methods:

**Method 1: From Terraform Output (Recommended)**
```bash
cd terraform/1_permissions/
terraform output vertex_ai_service_account_email
```

**Method 2: Using gcloud Command**
```bash
gcloud iam service-accounts list \
  --project=YOUR_PROJECT_ID \
  --filter="email:vertex-ai-sa" \
  --format="value(email)"
```

**Method 3: Construct Manually**
The format is: `<account-id>@<project-id>.iam.gserviceaccount.com`
- Account ID: `vertex-ai-sa`
- Example: `vertex-ai-sa@alex-multi-agent-saas-479504.iam.gserviceaccount.com`

**For Windows (PowerShell):**
```powershell
# Method 1: Terraform output
cd "alex-gcp\terraform\1_permissions"
terraform output vertex_ai_service_account_email

# Method 2: gcloud command
gcloud iam service-accounts list --project=alex-multi-agent-saas-479504 --filter="email:vertex-ai-sa" --format="value(email)"
```

**Deploy Terraform:**

```bash
cd terraform/2_vertex_ai/
terraform init
terraform plan  # You'll be prompted for vertex_ai_service_account - use the email from above
terraform apply
```

**Note:** When prompted for `vertex_ai_service_account`, enter the full service account email (e.g., `vertex-ai-sa@alex-multi-agent-saas-479504.iam.gserviceaccount.com`).

**Terraform Variables:**
- `enable_anthropic_api` (default: `false`) - Set to `true` only if you want to use Claude via Anthropic API. For cost savings, keep it `false` and use Gemini 2.0 Flash instead.

**After Terraform Apply - Set Up OpenAI API Key:**

The terraform creates a secret for OpenAI API key, but you need to add the actual key value:

**For Linux/Mac (Bash):**
```bash
# Create a file with your OpenAI API key
echo -n "your-openai-api-key-here" > /tmp/openai-key.txt

# Add the secret version
gcloud secrets versions add openai-api-key \
  --data-file=/tmp/openai-key.txt \
  --project=YOUR_PROJECT_ID

# Clean up
rm /tmp/openai-key.txt
```

**For Windows (PowerShell):**
```powershell
# Create a file with your OpenAI API key
"your-openai-api-key-here" | Out-File -FilePath "$env:TEMP\openai-key.txt" -NoNewline -Encoding utf8

# Add the secret version
gcloud secrets versions add openai-api-key `
  --data-file="$env:TEMP\openai-key.txt" `
  --project=alex-multi-agent-saas-479504

# Clean up
Remove-Item "$env:TEMP\openai-key.txt"
```

**Note:** Gemini 2.0 Flash doesn't require an API key - it uses Application Default Credentials (ADC) which you already set up in Phase 1.

### Step 3: Configure Model Selection

**Recommended: Use Gemini 2.0 Flash (Cost-Effective)**

Gemini 2.0 Flash is significantly more cost-effective than Claude models in Vertex AI. The terraform configuration defaults to using Gemini (Anthropic API disabled by default).

**When deploying terraform, you can optionally enable Anthropic API:**
- Set `enable_anthropic_api = false` (default) to use Gemini 2.0 Flash
- Set `enable_anthropic_api = true` if you want to use Claude via Anthropic API

### Step 4: Using Gemini 2.0 Flash with LiteLLM (Recommended)

**For use with OpenAI Agents SDK (as used in Alex backend):**

```python
from litellm import completion
import os
from google.cloud import secretmanager

# Get project ID from environment
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "your-project-id")
REGION = os.getenv("GCP_REGION", "us-central1")

# Initialize Vertex AI (happens automatically with LiteLLM)
# No API key needed - uses Application Default Credentials

# Use Gemini 2.0 Flash via LiteLLM
response = completion(
    model="vertex_ai/gemini-2.0-flash-exp",  # or "gemini-2.0-flash-exp"
    messages=[
        {"role": "user", "content": "Hello, Gemini!"}
    ],
    project=PROJECT_ID,
    location=REGION
)

print(response.choices[0].message.content)
```

**For use with OpenAI Agents SDK (as in agent.py files):**

```python
from agents import Agent, Runner
from litellm import LitellmModel
import os

# Set GCP project and region
os.environ["GCP_PROJECT_ID"] = "your-project-id"
os.environ["GCP_REGION"] = "us-central1"

# Create model using LiteLLM
model = LitellmModel(model="vertex_ai/gemini-2.0-flash-exp")

# Use with Agent
agent = Agent(
    name="My Agent",
    instructions="You are a helpful assistant.",
    model=model
)

result = await Runner.run(agent, input="Hello!")
print(result.final_output)
```

**Available Gemini Models:**
- `vertex_ai/gemini-2.0-flash-exp` - Gemini 2.0 Flash (recommended, cost-effective)
- `vertex_ai/gemini-1.5-pro` - Gemini 1.5 Pro (more capable, higher cost)
- `vertex_ai/gemini-1.5-flash` - Gemini 1.5 Flash (faster, lower cost)

### Step 5: Using OpenAI API Keys (Alongside Gemini)

**OpenAI API keys are stored in Secret Manager and can be used alongside Gemini:**

```python
from litellm import completion
from google.cloud import secretmanager
import os

def get_secret(secret_id: str) -> str:
    """Get secret from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    project_id = os.getenv("GCP_PROJECT_ID")
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# Get OpenAI API key
openai_api_key = get_secret("openai-api-key")

# Use OpenAI via LiteLLM
response = completion(
    model="gpt-4o-mini",  # or "gpt-4o", "gpt-3.5-turbo", etc.
    messages=[
        {"role": "user", "content": "Hello, OpenAI!"}
    ],
    api_key=openai_api_key
)

print(response.choices[0].message.content)
```

**Mixed Usage Example (Gemini for most tasks, OpenAI for specific needs):**

```python
# Use Gemini 2.0 Flash for general tasks (cost-effective)
gemini_response = completion(
    model="vertex_ai/gemini-2.0-flash-exp",
    messages=[{"role": "user", "content": "General question"}],
    project=PROJECT_ID,
    location=REGION
)

# Use OpenAI for specific tasks requiring GPT-4
openai_response = completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Complex reasoning task"}],
    api_key=openai_api_key
)
```

### Step 6: Using Claude (Optional - Higher Cost)

**If you enabled Anthropic API in terraform (`enable_anthropic_api = true`):**

```python
import anthropic
from google.cloud import secretmanager

def get_secret(secret_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    project_id = os.getenv("GCP_PROJECT_ID")
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# Get Anthropic API key
api_key = get_secret("anthropic-api-key")
client = anthropic.Anthropic(api_key=api_key)

# Make a request
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Hello, Claude!"}
    ]
)
print(message.content[0].text)
```

**Note:** Claude models are more expensive in Vertex AI. Consider using Gemini 2.0 Flash for cost savings.

## Custom Model Deployment

For deploying custom models (like fine-tuned models):

```python
from google.cloud import aiplatform

# Initialize
aiplatform.init(project="your-project", location="us-central1")

# Upload model
model = aiplatform.Model.upload(
    display_name="my-custom-model",
    artifact_uri="gs://your-bucket/model-artifacts/",
    serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-0:latest",
)

# Deploy to endpoint
endpoint = model.deploy(
    machine_type="n1-standard-4",
    min_replica_count=1,
    max_replica_count=3,
)

# Get predictions
response = endpoint.predict(instances=[{"input": "test"}])
```

## Cost Optimization Tips

1. **Use preemptible/spot VMs** for training jobs
2. **Auto-scale endpoints** based on traffic
3. **Use Model Garden** for foundation models (pay-per-use)
4. **Batch predictions** for non-real-time workloads

## Troubleshooting

### API Not Enabled Errors

**Common Errors:**
- `Error 403: Secret Manager API has not been used in project before or it is disabled`
- `Error 403: Vertex AI API has not been used in project before or it is disabled`

**Solution:**

**For Linux/Mac (Bash):**
```bash
# Enable missing APIs
gcloud services enable aiplatform.googleapis.com secretmanager.googleapis.com --project=YOUR_PROJECT_ID

# Verify APIs are enabled
gcloud services list --enabled --project=YOUR_PROJECT_ID --filter="name:(aiplatform.googleapis.com OR secretmanager.googleapis.com)"

# Wait 2-3 minutes for propagation, then retry terraform apply
```

**For Windows (PowerShell):**
```powershell
# Enable missing APIs
gcloud services enable aiplatform.googleapis.com secretmanager.googleapis.com --project=alex-multi-agent-saas-479504

# Verify APIs are enabled
gcloud services list --enabled --project=alex-multi-agent-saas-479504 --filter="name:(aiplatform.googleapis.com OR secretmanager.googleapis.com)"

# Wait 2-3 minutes for propagation, then retry terraform apply
```

**Note:** GCP APIs can take 2-5 minutes to fully propagate after enabling. If you still get errors, wait a few more minutes and retry.

### Quota Issues
```bash
# Check quotas
gcloud compute project-info describe --project=YOUR_PROJECT

# Request quota increase via Cloud Console
```

### Permission Denied
```bash
# Verify service account has aiplatform.user role
gcloud projects get-iam-policy YOUR_PROJECT --format=json | \
  jq '.bindings[] | select(.role | contains("aiplatform"))'
```

## Next Steps

After setting up Vertex AI, proceed to [3_ingest.md](3_ingest.md) for data ingestion setup.

**For Backend Integration:**
- See [GEMINI_SETUP.md](GEMINI_SETUP.md) for detailed instructions on updating your backend agent code to use Gemini 2.0 Flash
- Includes code examples, environment variable setup, and troubleshooting
