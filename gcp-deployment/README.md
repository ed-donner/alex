# Alex Multi-Agent SaaS - GCP Deployment

This repository contains the GCP deployment configuration for the Alex Multi-Agent SaaS application, translated from the original AWS deployment.

## 📋 Prerequisites

1. **GCP Account** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Terraform** >= 1.5.0
4. **Docker** installed
5. **Git** installed

## 🚀 Quick Start

### 1. Clone and Configure

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

# Authenticate with GCP
gcloud auth login
gcloud config set project $PROJECT_ID
```

### 2. Enable APIs

```bash
gcloud services enable \
  compute.googleapis.com \
  run.googleapis.com \
  cloudfunctions.googleapis.com \
  sqladmin.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  storage.googleapis.com \
  servicenetworking.googleapis.com \
  cloudbuild.googleapis.com
```

### 3. Deploy

```bash
# Make deploy script executable
chmod +x scripts/deploy.sh

# Run full deployment
./scripts/deploy.sh full
```

## 📁 Project Structure

```
gcp-deployment/
├── README.md                     # This file
├── guides/
│   ├── 0_AWS_TO_GCP_MAPPING.md  # AWS to GCP service mapping
│   ├── 1_permissions.md         # IAM setup guide
│   ├── 2_vertex_ai.md           # Vertex AI setup guide
│   ├── 5_database.md            # Cloud SQL setup guide
│   ├── 6_agents.md              # Agent deployment guide
│   ├── 7_frontend.md            # Frontend deployment guide
│   ├── ARCHITECTURE_COMPARISON.md # Detailed architecture comparison
│   ├── TROUBLESHOOTING.md       # Combined troubleshooting guide
│   ├── GEMINI_SETUP.md          # Gemini model setup guide
│   └── WINDOWS_SETUP.md         # Windows-specific setup
├── terraform/
│   ├── 1_permissions/           # IAM and service accounts
│   ├── 2_vertex_ai/             # Vertex AI configuration
│   ├── 3_pubsub/                # Pub/Sub topic and subscription
│   ├── 5_database/              # Cloud SQL PostgreSQL
│   ├── 6_agents/                # Cloud Run services (agents)
│   └── 7_frontend/              # Frontend with Cloud CDN
├── backend/                     # Agent code and API
│   ├── planner/                 # Orchestrator agent
│   ├── tagger/                  # Instrument classification
│   ├── reporter/                # Portfolio analysis
│   ├── charter/                 # Visualization agent
│   ├── retirement/              # Retirement projection
│   ├── researcher/              # Market research agent
│   ├── api/                     # FastAPI backend
│   ├── database/                # Shared database library
│   └── common/                  # Shared utilities (LLM config)
├── frontend/                     # NextJS React application
└── scripts/                     # Deployment scripts
```

## 🔄 AWS to GCP Service Mapping

This deployment uses GCP-native services as alternatives to the AWS services used in the original course. Below is a detailed comparison of the resources used:

| AWS Service | GCP Equivalent | Key Differences |
|-------------|----------------|------------------|
| **IAM** | **Cloud IAM** | Uses service accounts instead of IAM roles. Workload Identity Federation for CI/CD. |
| **SageMaker** | **Vertex AI** | Vertex AI provides embeddings via API (no endpoint deployment needed). Model Garden for foundation models. |
| **Bedrock** | **Vertex AI Model Garden** | Access to Gemini 2.0 Flash (recommended, cost-effective) and Claude via Anthropic API. No inference profiles needed. |
| **Lambda** | **Cloud Run** | Container-based serverless. Better for multi-file applications. Scales to zero automatically. |
| **App Runner** | **Cloud Run** | Same service as Lambda alternative. Supports any containerized application. |
| **ECR** | **Artifact Registry** | Multi-format registry (Docker, npm, Python, Maven). Better integration with Cloud Build. |
| **RDS Aurora Serverless v2** | **Cloud SQL PostgreSQL** | Managed PostgreSQL with automatic backups. Uses Cloud SQL Proxy or Unix socket for connections. No Data API needed. |
| **S3** | **Cloud Storage** | Object storage with similar API. Used for static frontend hosting. |
| **S3 Vectors** | **Vertex AI Vector Search** (TODO) | Vector search functionality needs GCP implementation. Currently placeholder in code. |
| **API Gateway** | **Cloud Run** (built-in) | Cloud Run provides HTTPS endpoints automatically. No separate API Gateway needed. |
| **SQS** | **Cloud Pub/Sub** | Message queuing with push/pull subscriptions. Better integration with Cloud Run. |
| **CloudFront** | **Cloud CDN** | Content delivery network. Optional for frontend deployment. |
| **Route 53** | **Cloud DNS** | DNS management. Optional for custom domains. |
| **Secrets Manager** | **Secret Manager** | Similar functionality. Integrated with Cloud Run via environment variables. |
| **CloudWatch** | **Cloud Monitoring & Logging** | Unified observability platform. Better integration with GCP services. |

### Key Architectural Differences

#### 1. **Serverless Compute**
- **AWS**: Lambda functions (zip-based, 50MB limit, requires packaging)
- **GCP**: Cloud Run (container-based, no size limit, easier deployment)
- **Benefit**: No need for `package_docker.py` scripts. Direct container deployment.

#### 2. **AI/ML Services**
- **AWS**: Bedrock (requires model access requests, inference profiles for cross-region)
- **GCP**: Vertex AI Model Garden (Gemini 2.0 Flash recommended, no API keys needed with ADC)
- **Benefit**: Lower costs with Gemini, native GCP integration, simpler setup.

#### 3. **Database**
- **AWS**: Aurora Serverless v2 with Data API (HTTP-based, no VPC needed)
- **GCP**: Cloud SQL PostgreSQL with Unix socket or Cloud SQL Proxy
- **Benefit**: Standard PostgreSQL connections, better performance, automatic backups.

#### 4. **Message Queuing**
- **AWS**: SQS (simple queue service)
- **GCP**: Pub/Sub (publish/subscribe with topics and subscriptions)
- **Benefit**: Better integration with Cloud Run, push subscriptions available.

#### 5. **Vector Storage** (Future Implementation)
- **AWS**: S3 Vectors (90% cost savings vs OpenSearch)
- **GCP**: Vertex AI Vector Search or Matching Engine (to be implemented)
- **Status**: Currently placeholder in code. See `backend/reporter/agent.py` for TODO.

#### 6. **Container Registry**
- **AWS**: ECR (Elastic Container Registry)
- **GCP**: Artifact Registry (multi-format, better CI/CD integration)
- **Benefit**: Supports Docker, npm, Python packages in one registry.

### Cost Comparison

| Service Category | AWS | GCP | Notes |
|-----------------|-----|-----|-------|
| **Serverless Compute** | Lambda: $0.20 per 1M requests | Cloud Run: Pay per request, scales to zero | GCP often cheaper for low traffic |
| **Database** | Aurora: ~$50-100/month | Cloud SQL: ~$30-100/month | Similar pricing, GCP slightly cheaper |
| **AI/ML** | Bedrock: Varies by model | Vertex AI: Gemini 2.0 Flash is cost-effective | Gemini significantly cheaper than Claude |
| **Container Registry** | ECR: $0.10/GB/month | Artifact Registry: $0.10/GB/month | Similar pricing |
| **Message Queuing** | SQS: $0.40 per 1M requests | Pub/Sub: $0.40 per 1M requests | Similar pricing |

**Recommendation**: Use Gemini 2.0 Flash for most tasks to reduce AI costs significantly compared to Claude models.

## 📖 Deployment Phases

### Phase 1: Permissions
Sets up service accounts and IAM bindings.

```bash
cd terraform/1_permissions
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
terraform init && terraform apply
```

### Phase 2: Vertex AI
Configures Vertex AI for ML/LLM access.

```bash
cd terraform/2_vertex_ai
terraform init && terraform apply
```

### Phase 5: Database
Deploys Cloud SQL PostgreSQL.

```bash
cd terraform/5_database
terraform init && terraform apply
```

### Phase 6: Agents
Deploys multi-agent backend on Cloud Run.

```bash
cd terraform/6_agents
terraform init && terraform apply
```

### Phase 7: Frontend
Deploys NextJS frontend with optional Cloud CDN.

```bash
cd terraform/7_frontend
terraform init && terraform apply
```

## 🔐 Setting Up Secrets

Store your API keys in Secret Manager:

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"

# OpenAI API key (optional, if using OpenAI alongside Gemini)
echo -n "sk-proj-xxx" | gcloud secrets create openai-api-key --data-file=- --project=$PROJECT_ID

# Clerk keys (required for frontend authentication)
echo -n "pk_live_xxx" | gcloud secrets create clerk-publishable-key --data-file=- --project=$PROJECT_ID
echo -n "sk_live_xxx" | gcloud secrets create clerk-secret-key --data-file=- --project=$PROJECT_ID

# Database password (created automatically by terraform/5_database)
# You can update it manually if needed:
echo -n "your-db-password" | gcloud secrets versions add alex-db-password --data-file=- --project=$PROJECT_ID
```

**Note**: Gemini 2.0 Flash (recommended) doesn't require API keys - it uses Application Default Credentials (ADC) which are automatically configured when you run `gcloud auth application-default login`.

## 🌐 Using AI Models on GCP

### Recommended: Gemini 2.0 Flash (Cost-Effective)

Gemini 2.0 Flash is the recommended model for this deployment. It's significantly more cost-effective than Claude and provides excellent performance.

```python
from agents import Agent, Runner
from litellm import LitellmModel
import os

# Set GCP project and region
os.environ["GCP_PROJECT_ID"] = "your-gcp-project-id"
os.environ["GCP_REGION"] = "us-central1"

# Create model (uses Application Default Credentials, no API key needed)
model = LitellmModel(model="vertex_ai/gemini-2.0-flash-exp")

# Use with Agent
agent = Agent(
    name="My Agent",
    instructions="You are a helpful assistant.",
    model=model
)

result = await Runner.run(agent, input="Hello!")
```

### Alternative: OpenAI API (via Secret Manager)

If you need OpenAI models (GPT-4o, GPT-4o-mini), store the API key in Secret Manager:

```python
from google.cloud import secretmanager
import os

def get_secret(secret_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    project_id = os.getenv("GCP_PROJECT_ID")
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# Get API key from Secret Manager
api_key = get_secret("openai-api-key")

# Use with LiteLLM
from litellm import LitellmModel
model = LitellmModel(model="openai/gpt-4o-mini", api_key=api_key)
```

### Optional: Claude via Anthropic API

Claude is available but more expensive. Store API key in Secret Manager if needed.

See [guides/GEMINI_SETUP.md](guides/GEMINI_SETUP.md) for detailed setup instructions.

## 💰 Cost Estimation

| Service | Estimated Monthly Cost (Dev) |
|---------|------------------------------|
| Cloud Run | $20-50 (scale to zero) |
| Cloud SQL | $30-100 (db-custom-2-4096) |
| Artifact Registry | $5-10 |
| Cloud Storage | $5-10 |
| Vertex AI | Pay-per-use |
| Cloud CDN | Pay-per-GB |

## 🧹 Cleanup

To destroy all resources:

```bash
./scripts/deploy.sh destroy
```

Or manually:

```bash
for phase in 7_frontend 6_agents 5_database 2_vertex_ai 1_permissions; do
  cd terraform/$phase
  terraform destroy -auto-approve
  cd ../..
done
```

## ❓ Troubleshooting

For detailed troubleshooting information, see [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md).

### Common Issues

1. **API not enabled**: Run the API enable command above
2. **Permission denied**: Check IAM bindings in `terraform/1_permissions`
3. **Quota exceeded**: Request quota increase in GCP Console
4. **Environment variables not loading**: Check `.env` file in root directory
5. **Pub/Sub errors**: Verify topic exists and service account has permissions
6. **Missing pg8000 dependency**: See [guides/FIX_PG8000_DEPENDENCY.md](guides/FIX_PG8000_DEPENDENCY.md) - Fixed in Dockerfiles

### Useful Commands

```bash
# Check Cloud Run services
gcloud run services list --project=your-gcp-project-id

# View logs
gcloud logging read "resource.type=cloud_run_revision" --limit=50 --project=your-gcp-project-id

# Check database status
gcloud sql instances describe alex-postgres --project=your-gcp-project-id

# List Pub/Sub topics
gcloud pubsub topics list --project=your-gcp-project-id

# Check service accounts
gcloud iam service-accounts list --project=your-gcp-project-id
```

## 📚 Additional Resources

### GCP Documentation
- [GCP Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Cloud SQL Documentation](https://cloud.google.com/sql/docs)
- [Cloud Pub/Sub Documentation](https://cloud.google.com/pubsub/docs)
- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)

### Terraform
- [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)

### AI/ML
- [Vertex AI Model Garden](https://cloud.google.com/vertex-ai/docs/model-garden/overview)
- [Gemini API Documentation](https://ai.google.dev/docs)
- [Anthropic on Vertex AI](https://docs.anthropic.com/en/api/vertex)

### Guides in This Repository
- [AWS to GCP Mapping](guides/0_AWS_TO_GCP_MAPPING.md) - Service comparison
- [Architecture Comparison](guides/ARCHITECTURE_COMPARISON.md) - Detailed architecture differences
- [Troubleshooting Guide](guides/TROUBLESHOOTING.md) - Common issues and solutions
- [Gemini Setup](guides/GEMINI_SETUP.md) - Configuring Gemini models
- [Fix: pg8000 Dependency](guides/FIX_PG8000_DEPENDENCY.md) - Solution for missing database dependencies in agent containers

## 🤝 Contributing

Contributions are welcome! Please submit a PR with your GCP deployment improvements.

## 📝 License

This project is licensed under the MIT License - see the original course repository for details.
