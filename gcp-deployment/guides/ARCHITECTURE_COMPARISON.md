# AWS vs GCP Architecture Comparison

## Current State (AWS) vs Target State (GCP)

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   Frontend   │──────│ API Gateway  │──────│   Lambda     │  │
│  │  (Next.js)   │      │              │      │   (API)      │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│                                 │                                │
│                                 ▼                                │
│                          ┌──────────────┐                        │
│                          │     SQS      │                        │
│                          │  (Job Queue) │                        │
│                          └──────────────┘                        │
│                                 │                                │
│                    ┌────────────┼────────────┐                   │
│                    ▼            ▼            ▼                   │
│            ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│            │ Planner  │  │  Tagger  │  │ Reporter │            │
│            │ (Lambda) │  │ (Lambda) │  │ (Lambda) │            │
│            └──────────┘  └──────────┘  └──────────┘            │
│                    │            │            │                   │
│                    └────────────┼────────────┘                   │
│                                 │                                │
│                    ┌────────────┼────────────┐                   │
│                    ▼            ▼            ▼                   │
│            ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│            │ Charter  │  │Retirement│  │Researcher│            │
│            │ (Lambda) │  │ (Lambda) │  │(App Run)│            │
│            └──────────┘  └──────────┘  └──────────┘            │
│                                 │                                │
│                    ┌────────────┼────────────┐                   │
│                    ▼            ▼            ▼                   │
│            ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│            │  Bedrock │  │ SageMaker│  │S3 Vectors│            │
│            │   (LLM)  │  │(Embedding)│  │  (Search)│            │
│            └──────────┘  └──────────┘  └──────────┘            │
│                                 │                                │
│                                 ▼                                │
│                          ┌──────────────┐                        │
│                          │   Aurora     │                        │
│                          │  (PostgreSQL)│                        │
│                          └──────────────┘                        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        GCP ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   Frontend   │──────│ Cloud Run    │──────│ Cloud Run    │  │
│  │  (Next.js)   │      │  (API)       │      │   (API)      │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│                                 │                                │
│                                 ▼                                │
│                          ┌──────────────┐                        │
│                          │  Pub/Sub     │                        │
│                          │  (Job Queue) │                        │
│                          └──────────────┘                        │
│                                 │                                │
│                    ┌────────────┼────────────┐                   │
│                    ▼            ▼            ▼                   │
│            ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│            │ Planner  │  │  Tagger  │  │ Reporter │            │
│            │(Cloud Run)│ │(Cloud Run)│ │(Cloud Run)│            │
│            └──────────┘  └──────────┘  └──────────┘            │
│                    │            │            │                   │
│                    └────────────┼────────────┘                   │
│                                 │                                │
│                    ┌────────────┼────────────┐                   │
│                    ▼            ▼            ▼                   │
│            ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│            │ Charter  │  │Retirement│  │Researcher│            │
│            │(Cloud Run)│ │(Cloud Run)│ │(Cloud Run)│            │
│            └──────────┘  └──────────┘  └──────────┘            │
│                                 │                                │
│                    ┌────────────┼────────────┐                   │
│                    ▼            ▼            ▼                   │
│            ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│            │ Vertex AI│  │ Vertex AI│  │ Vertex AI│            │
│            │ (Gemini) │  │(Embedding)│  │(Vector   │            │
│            │          │  │          │  │  Search) │            │
│            └──────────┘  └──────────┘  └──────────┘            │
│                                 │                                │
│                                 ▼                                │
│                          ┌──────────────┐                        │
│                          │  Cloud SQL   │                        │
│                          │  (PostgreSQL)│                        │
│                          └──────────────┘                        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Service-by-Service Mapping

### Compute Services

| Component | AWS | GCP | Migration Status |
|-----------|-----|-----|------------------|
| **API Backend** | Lambda | Cloud Run | 🔄 To Do |
| **Planner Agent** | Lambda | Cloud Run | 🔄 To Do |
| **Tagger Agent** | Lambda | Cloud Run | 🔄 To Do |
| **Reporter Agent** | Lambda | Cloud Run | 🔄 To Do |
| **Charter Agent** | Lambda | Cloud Run | 🔄 To Do |
| **Retirement Agent** | Lambda | Cloud Run | 🔄 To Do |
| **Researcher Agent** | App Runner | Cloud Run | 🔄 To Do |

### Messaging & Orchestration

| Component | AWS | GCP | Migration Status |
|-----------|-----|-----|------------------|
| **Job Queue** | SQS | Pub/Sub | 🔄 To Do |
| **Event Scheduling** | EventBridge | Cloud Scheduler | 🔄 To Do |

### AI/ML Services

| Component | AWS | GCP | Migration Status |
|-----------|-----|-----|------------------|
| **LLM Inference** | Bedrock (Nova Pro) | Vertex AI (Gemini 2.0 Flash) | ✅ Done |
| **Embeddings** | SageMaker Endpoint | Vertex AI Embeddings API | 🔄 To Do |
| **Vector Search** | S3 Vectors | Vertex AI Vector Search | 🔄 To Do |

### Storage & Database

| Component | AWS | GCP | Migration Status |
|-----------|-----|-----|------------------|
| **Database** | Aurora Serverless v2 | Cloud SQL PostgreSQL | ✅ Done |
| **Object Storage** | S3 | Cloud Storage | 🔄 To Do (if needed) |
| **Secrets** | Secrets Manager | Secret Manager | ✅ Done |

### Networking & API

| Component | AWS | GCP | Migration Status |
|-----------|-----|-----|------------------|
| **API Gateway** | API Gateway | Cloud Run + API Gateway | 🔄 To Do |
| **CDN** | CloudFront | Cloud CDN | 🔄 To Do |
| **DNS** | Route 53 | Cloud DNS | 🔄 To Do (if needed) |

## Code Pattern Changes

### Invoking Agents

**AWS Pattern (Current)**:
```python
import boto3

lambda_client = boto3.client('lambda')
response = lambda_client.invoke(
    FunctionName='alex-reporter',
    InvocationType='RequestResponse',
    Payload=json.dumps({'job_id': job_id})
)
result = json.loads(response['Payload'].read())
```

**GCP Pattern (Target)**:
```python
import requests
from google.auth.transport.requests import Request
from google.oauth2 import id_token

# Get authentication token
auth_req = Request()
token = id_token.fetch_id_token(auth_req, 'https://reporter-xxxxx.run.app')

# Make HTTP request
response = requests.post(
    'https://reporter-xxxxx.run.app',
    json={'job_id': job_id},
    headers={'Authorization': f'Bearer {token}'}
)
result = response.json()
```

### Job Queueing

**AWS Pattern (Current)**:
```python
import boto3

sqs = boto3.client('sqs')
sqs.send_message(
    QueueUrl='https://sqs.us-east-1.amazonaws.com/.../alex-queue',
    MessageBody=json.dumps({'job_id': job_id})
)
```

**GCP Pattern (Target)**:
```python
from google.cloud import pubsub_v1

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(project_id, 'alex-job-queue')
future = publisher.publish(
    topic_path,
    json.dumps({'job_id': job_id}).encode('utf-8')
)
message_id = future.result()
```

### Vector Search

**AWS Pattern (Current)**:
```python
import boto3

s3v = boto3.client('s3vectors')
response = s3v.query_vectors(
    vectorBucketName='alex-vectors-123456',
    indexName='financial-research',
    queryVector={'float32': embedding},
    topK=3
)
```

**GCP Pattern (Target)**:
```python
from google.cloud import aiplatform

aiplatform.init(project=project_id, location=region)
index = aiplatform.MatchingEngineIndex(index_id=index_id)
results = index.find_neighbors(
    deployed_index_id=deployed_index_id,
    queries=[embedding],
    num_neighbors=3
)
```

### Embeddings

**AWS Pattern (Current)**:
```python
import boto3

sagemaker = boto3.client('sagemaker-runtime')
response = sagemaker.invoke_endpoint(
    EndpointName='alex-embedding-endpoint',
    ContentType='application/json',
    Body=json.dumps({'inputs': text})
)
embedding = json.loads(response['Body'].read())
```

**GCP Pattern (Target)**:
```python
from vertexai.preview.language_models import TextEmbeddingModel

model = TextEmbeddingModel.from_pretrained("textembedding-gecko@003")
embeddings = model.get_embeddings([text])
embedding = embeddings[0].values
```

## Migration Priority Matrix

### 🔴 High Priority (Blocking)
1. **Pub/Sub Migration** - Required for job orchestration
2. **Agent Compute Migration** - Core functionality
3. **API Backend Migration** - Frontend integration

### 🟡 Medium Priority (Important)
4. **Vector Storage Migration** - Market insights feature
5. **Embedding Service Migration** - Vector search dependency

### 🟢 Low Priority (Nice to Have)
6. **Monitoring Migration** - Observability improvements
7. **CDN Migration** - Performance optimization

## Cost Comparison (Estimated)

| Service | AWS Cost | GCP Cost | Notes |
|---------|----------|----------|-------|
| **Compute** | Lambda: $0.20/1M requests | Cloud Run: $0.40/1M requests | GCP slightly more expensive |
| **LLM** | Bedrock Nova Pro: $0.003/1K tokens | Vertex AI Gemini: $0.000125/1K tokens | **GCP 24x cheaper!** |
| **Database** | Aurora: ~$0.10/hour | Cloud SQL: ~$0.10/hour | Similar pricing |
| **Vector Search** | S3 Vectors: ~$0.10/GB/month | Vertex AI: ~$0.50/GB/month | GCP more expensive but more features |
| **Message Queue** | SQS: $0.40/1M requests | Pub/Sub: $0.40/1M requests | Similar pricing |

**Key Insight**: Gemini 2.0 Flash is significantly cheaper than Nova Pro, which may offset other cost differences.

## Next Steps

1. ✅ **Read**: `GCP_MIGRATION_PLAN.md` for detailed migration steps
2. ✅ **Start**: `MIGRATION_QUICKSTART.md` for immediate action items
3. 🔄 **Execute**: Phase 2 - Pub/Sub migration (2-3 hours)
4. 🔄 **Execute**: Phase 3 - Agent compute migration (5-7 days)
5. 🔄 **Execute**: Phase 4 - Vector storage migration (3-4 days)

