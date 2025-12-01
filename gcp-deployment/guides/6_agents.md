# Phase 6: Agent Deployment (Cloud Run - Equivalent to AWS Lambda/App Runner)

## Overview

This guide deploys the multi-agent backend on GCP using Cloud Run, which is equivalent to AWS Lambda/App Runner.

## AWS vs GCP Comparison

| AWS Service | GCP Equivalent | Use Case |
|-------------|----------------|----------|
| Lambda | Cloud Functions (Gen 2) | Event-driven, short tasks |
| App Runner | Cloud Run | Containerized web services |
| Bedrock AgentCore | Vertex AI Agents | Agent orchestration |
| API Gateway | Cloud Run (built-in) / API Gateway | HTTP endpoints |
| SQS | Cloud Pub/Sub | Message queuing |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Cloud Run Services                      │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  Researcher  │   Ingestor   │   Planner    │   Executor     │
│    Agent     │    Agent     │    Agent     │    Agent       │
├──────────────┴──────────────┴──────────────┴────────────────┤
│                     Vertex AI (Claude/Gemini)                │
├─────────────────────────────────────────────────────────────┤
│                      Cloud SQL (PostgreSQL)                  │
└─────────────────────────────────────────────────────────────┘
```

## Steps

### Step 1: Build Container Images

```bash
# Set variables
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export REPO="alex-containers"

# Configure Docker for Artifact Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build and push agent images
cd backend/agents

# Build researcher agent
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/researcher:latest -f Dockerfile.researcher .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/researcher:latest

# Build other agents similarly...
```

### Step 2: Deploy Terraform

```bash
cd terraform/6_agents/
terraform init
terraform plan
terraform apply
```

### Step 3: Configure Environment Variables

Cloud Run services need these environment variables:

```bash
# Set via Terraform or gcloud
gcloud run services update researcher-agent \
  --set-env-vars="PROJECT_ID=${PROJECT_ID}" \
  --set-env-vars="REGION=${REGION}" \
  --set-secrets="ANTHROPIC_API_KEY=anthropic-api-key:latest" \
  --set-secrets="DB_PASSWORD=alex-db-password:latest"
```

### Step 4: Inter-Service Communication

For agents to communicate with each other:

```python
import os
import requests
from google.auth.transport.requests import Request
from google.oauth2 import id_token

def call_agent(agent_url: str, payload: dict) -> dict:
    """Call another Cloud Run agent service."""
    # Get ID token for authentication
    auth_req = Request()
    token = id_token.fetch_id_token(auth_req, agent_url)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(agent_url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()

# Example usage
result = call_agent(
    os.environ["RESEARCHER_AGENT_URL"],
    {"query": "Research AI trends"}
)
```

## Agent Code Structure

### Base Agent Class

```python
# backend/agents/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict
import anthropic
from google.cloud import secretmanager

class BaseAgent(ABC):
    def __init__(self):
        self.client = self._init_anthropic_client()
    
    def _init_anthropic_client(self) -> anthropic.Anthropic:
        """Initialize Anthropic client with API key from Secret Manager."""
        api_key = self._get_secret("anthropic-api-key")
        return anthropic.Anthropic(api_key=api_key)
    
    def _get_secret(self, secret_id: str) -> str:
        """Get secret from Secret Manager."""
        client = secretmanager.SecretManagerServiceClient()
        project_id = os.environ["PROJECT_ID"]
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input and return result."""
        pass
```

### FastAPI Endpoint

```python
# backend/agents/researcher/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from base import BaseAgent

app = FastAPI()

class ResearchRequest(BaseModel):
    query: str
    context: dict = {}

class ResearchAgent(BaseAgent):
    async def process(self, input_data: dict) -> dict:
        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system="You are a research assistant...",
            messages=[
                {"role": "user", "content": input_data["query"]}
            ]
        )
        return {"result": message.content[0].text}

agent = ResearchAgent()

@app.post("/research")
async def research(request: ResearchRequest):
    try:
        result = await agent.process(request.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

### Dockerfile

**Important**: When using local path dependencies (like `alex-database`), you must explicitly install the database package to ensure all transitive dependencies (including `pg8000`) are installed. See [FIX_PG8000_DEPENDENCY.md](FIX_PG8000_DEPENDENCY.md) for details.

```dockerfile
# backend/reporter/Dockerfile (example)
FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

# Install Python package manager
RUN pip install uv

# Copy database package (required dependency)
COPY database ./database

# Copy shared modules
COPY common ./common

# Copy agent-specific files
COPY reporter/pyproject.toml reporter/uv.lock ./

# Update pyproject.toml to use ./database instead of ../database
RUN sed -i.bak 's|path = "../database"|path = "./database"|g' pyproject.toml && rm pyproject.toml.bak

# Install Python dependencies
# First install database package with all its dependencies (including pg8000)
RUN cd database && uv pip install --system -e . && cd ..
# Then sync the main project dependencies
RUN uv sync --no-install-project

# Copy agent application code
COPY reporter/*.py ./

# Cloud Run expects port 8000
ENV PORT=8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

## Scaling Configuration

Cloud Run automatically scales based on traffic:

```hcl
# In terraform
resource "google_cloud_run_v2_service" "agent" {
  template {
    scaling {
      min_instance_count = 0   # Scale to zero
      max_instance_count = 10  # Max instances
    }
    
    containers {
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
        cpu_idle = true  # Don't charge for idle CPU
      }
    }
  }
}
```

## Monitoring

```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=researcher-agent" --limit=50

# View metrics
gcloud monitoring dashboards list
```

## Troubleshooting

### Cold Start Issues
- Increase `min_instance_count` to 1
- Use smaller container images
- Optimize initialization code

### Memory Errors
- Increase memory limits in Cloud Run
- Profile memory usage with Cloud Profiler

### Timeout Issues
- Increase request timeout (max 60 min)
- Use async processing for long tasks

## Next Steps

After deploying agents, proceed to [7_frontend.md](7_frontend.md) for frontend deployment.
