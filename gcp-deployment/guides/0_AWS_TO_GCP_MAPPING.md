# AWS to GCP Service Mapping Guide

## Overview

This guide translates the AWS deployment for the Multi-Agent SaaS App (Alex) to Google Cloud Platform (GCP). The original course deploys using AWS services; this translation provides equivalent GCP services and Terraform configurations.

## Service Mapping Reference

| AWS Service | GCP Equivalent | Purpose |
|-------------|----------------|---------|
| **IAM** | Cloud IAM | Identity and Access Management |
| **SageMaker** | Vertex AI | ML model hosting and training |
| **Bedrock** | Vertex AI (Model Garden) | LLM/AI services (Claude, Gemini) |
| **Lambda** | Cloud Functions / Cloud Run | Serverless compute |
| **App Runner** | Cloud Run | Container hosting |
| **ECR** | Artifact Registry | Container registry |
| **RDS (PostgreSQL)** | Cloud SQL | Managed database |
| **S3** | Cloud Storage | Object storage |
| **API Gateway** | API Gateway / Cloud Endpoints | HTTP API management |
| **VPC** | VPC | Virtual Private Cloud |
| **CloudWatch** | Cloud Monitoring & Logging | Observability |
| **Secrets Manager** | Secret Manager | Secrets management |
| **CloudFront** | Cloud CDN | Content delivery |
| **Route 53** | Cloud DNS | DNS management |
| **ECS/Fargate** | Cloud Run / GKE Autopilot | Container orchestration |
| **SQS** | Cloud Pub/Sub | Message queuing |
| **EventBridge** | Cloud Scheduler / Eventarc | Event-driven architecture |

## Deployment Phase Mapping

### Week 3 Day 3: 1_permissions and 2_sagemaker
- **AWS**: IAM roles, policies, SageMaker endpoints
- **GCP**: Service accounts, IAM bindings, Vertex AI endpoints

### Week 3 Day 4: 3_ingest
- **AWS**: S3 buckets, Lambda functions for data ingestion
- **GCP**: Cloud Storage buckets, Cloud Functions

### Week 3 Day 5: 4_researcher
- **AWS**: Lambda/App Runner for research agents, Bedrock
- **GCP**: Cloud Run services, Vertex AI API

### Week 4 Day 1: 5_database
- **AWS**: RDS PostgreSQL
- **GCP**: Cloud SQL PostgreSQL

### Week 4 Day 2: 6_agents
- **AWS**: Lambda functions, Bedrock AgentCore
- **GCP**: Cloud Functions/Run, Vertex AI Agents

### Week 4 Day 3: 7_frontend
- **AWS**: App Runner, CloudFront, Route 53
- **GCP**: Cloud Run, Cloud CDN, Cloud DNS

### Week 4 Day 4: 8_enterprise
- **AWS**: Enterprise features, monitoring, scaling
- **GCP**: Identity Platform, Cloud Monitoring, Autoscaling

## Key Differences

### Authentication
- **AWS**: IAM users, roles, access keys
- **GCP**: Service accounts, Workload Identity, OAuth

### AI/ML Services
- **AWS Bedrock**: Direct API access to Claude, Titan models
- **GCP Vertex AI**: Access to Gemini, Claude (via Model Garden), PaLM

### Serverless
- **AWS Lambda**: Function-based, cold starts
- **Cloud Functions**: Similar to Lambda (Gen 2 uses Cloud Run under the hood)
- **Cloud Run**: Better for containerized apps, request-based scaling

### Container Registry
- **AWS ECR**: Docker registry
- **GCP Artifact Registry**: Multi-format (Docker, npm, Python, Maven)

## Prerequisites for GCP Deployment

1. **GCP Account** with billing enabled
2. **gcloud CLI** installed and configured
3. **Terraform** >= 1.5.0
4. **Docker** for container builds
5. **Enable required APIs**:
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
     dns.googleapis.com \
     certificatemanager.googleapis.com
   ```

## Project Structure

```
alex-gcp/
├── guides/
│   ├── 0_AWS_TO_GCP_MAPPING.md
│   ├── 1_permissions.md
│   ├── 2_vertex_ai.md
│   ├── 3_ingest.md
│   ├── 4_researcher.md
│   ├── 5_database.md
│   ├── 6_agents.md
│   ├── 7_frontend.md
│   └── 8_enterprise.md
├── terraform/
│   ├── 1_permissions/
│   ├── 2_vertex_ai/
│   ├── 3_ingest/
│   ├── 4_researcher/
│   ├── 5_database/
│   ├── 6_agents/
│   ├── 7_frontend/
│   └── 8_enterprise/
└── scripts/
    └── deploy.sh
```
