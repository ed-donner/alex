# Alex Architecture Overview (S3 Vectors Version)

## System Architecture

The Alex platform uses a modern serverless architecture on AWS, combining AI services with cost-effective infrastructure:


```mermaid
graph TB
    %% API Gateway
    APIGW[fa:fa-shield-alt API Gateway<br/>REST API<br/>API Key Auth]
    
    %% Backend Services
    Lambda[fa:fa-bolt Lambda<br/>alex-ingest<br/>Document Processing]
    AgentCore[fa:fa-robot Bedrock AgentCore<br/>Multi-Agent Platform<br/>Planner, Reporter, Charter, Retirement]
    
    %% Scheduler Components
    EventBridge[fa:fa-clock EventBridge<br/>Scheduler<br/>Every 2 Hours]
    SchedulerLambda[fa:fa-bolt Lambda<br/>alex-scheduler<br/>Trigger Research]
    
    %% AI Services
    SageMaker[fa:fa-brain SageMaker<br/>Embedding Model<br/>all-MiniLM-L6-v2]
    Bedrock[fa:fa-robot AWS Bedrock<br/>Nova Pro via LiteLLM<br/>AgentCore Runtime]
    
    %% Data Storage
    S3Vectors[fa:fa-database S3 Vectors<br/>Vector Storage<br/>90% Cost Reduction!]
    SQS[fa:fa-arrows-alt SQS<br/>Agent Orchestration<br/>Fan-out Pattern]
    
    %% Connections
    AgentCore -->|Store Results| APIGW
    AgentCore -->|Execute via| Bedrock
    APIGW -->|Invoke| Lambda
    
    EventBridge -->|Every 2hrs| SchedulerLambda
    SchedulerLambda -->|Trigger via SQS| SQS
    SQS -->|Fan-out to| AgentCore
    
    Lambda -->|Get Embeddings| SageMaker
    Lambda -->|Store Vectors| S3Vectors
    
    AgentCore -->|Tool Registry| Bedrock
    
    %% Styling
    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef ai fill:#10B981,stroke:#047857,stroke-width:2px,color:#fff
    classDef storage fill:#3B82F6,stroke:#1E40AF,stroke-width:2px,color:#fff
    classDef highlight fill:#90EE90,stroke:#228B22,stroke-width:3px,color:#000
    classDef scheduler fill:#9333EA,stroke:#6B21A8,stroke-width:2px,color:#fff
    classDef agentcore fill:#DC2626,stroke:#991B1B,stroke-width:3px,color:#fff
    
    class APIGW,Lambda,SageMaker,SchedulerLambda aws
    class Bedrock,AgentCore ai
    class S3Vectors storage
    class S3Vectors highlight
    class EventBridge scheduler
    class SQS storage
    class AgentCore agentcore
```


## Component Details

### 1. **Bedrock AgentCore**
- **Agents**: Planner, Tagger, Reporter with AgentCore Browser Tool, Charter, Retirement
- **Purpose**: Multi-agent orchestration platform
- **Runtime**: AWS Bedrock AgentCore with Nova Pro
- **Features**: Shared tool registry, parallel execution, standardized templates

### 2. **API Gateway**
- **Type**: REST API
- **Auth**: API Key authentication
- **Endpoints**: `/ingest` (POST)
- **Purpose**: Secure access to Lambda functions

### 3. **Lambda Functions**
- **alex-ingest**: Processes documents and stores embeddings
  - Runtime: Python 3.12
  - Memory: 512MB
  - Timeout: 30 seconds
- **alex-scheduler**: Triggers automated research
  - Runtime: Python 3.11
  - Memory: 128MB
  - Timeout: 150 seconds

### 4. **S3 Vectors** 
- **Purpose**: Native vector storage in S3
- **Features**: 
  - Sub-second similarity search
  - Automatic optimization
  - No minimum charges
  - Strongly consistent writes
- **Cost**: ~$30/month (vs ~$300/month for OpenSearch)
- **Scale**: Millions of vectors per index


### 5. **SageMaker Serverless**
- **Model**: sentence-transformers/all-MiniLM-L6-v2
- **Purpose**: Generate 384-dimensional embeddings
- **Memory**: 3GB
- **Concurrency**: 10 max

### 6. **EventBridge Scheduler**
- **Rule**: alex-research-schedule
- **Schedule**: Every 2 hours
- **Target**: alex-scheduler Lambda
- **Purpose**: Automated research generation

### 7. **AWS Bedrock**
- **Provider**: AWS Bedrock
- **Model**: OpenAI OSS 120B (open-weight model)
- **Region**: us-west-2 (model only available here)
- **Purpose**: Research generation and analysis
- **Features**: 128K context window, cross-region access

## Data Flow

1. **Manual Research Flow**:
   ```
   User → App Runner → Bedrock (generate) → API Gateway → Lambda → S3 Vectors
   ```

2. **Automated Research Flow**:
   ```
   EventBridge (every 2hrs) → Lambda Scheduler → App Runner → Bedrock → API Gateway → Lambda → S3 Vectors
   ```

3. **Direct Ingest Flow**:
   ```
   User → API Gateway → Lambda → SageMaker (embed) → S3 Vectors
   ```

4. **Search Flow** (future):
   ```
   User → API Gateway → Lambda → S3 Vectors (similarity search)
   ```

## Cost Optimization

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| S3 Vectors | ~$30 | 90% cheaper than OpenSearch! |
| SageMaker Serverless | ~$5-10 | Pay per request |
| Lambda | ~$1 | Minimal invocations |
| App Runner | ~$5 | 1 vCPU, 2GB RAM |
| API Gateway | ~$1 | REST API |
| **Total** | **~$42-47** | Previously ~$250+ |

## Security Features

- **API Gateway**: API key authentication
- **IAM Roles**: Least privilege access
- **S3 Vectors**: Always private (no public access)
- **App Runner**: HTTPS by default
- **Secrets**: Environment variables for API keys

## Deployment Architecture

```mermaid
graph LR
    Dev[fa:fa-laptop Developer]
    GH[fa:fa-code-branch GitHub Repo]
    TF[fa:fa-cog Terraform]
    AWS[fa:fa-cloud AWS]
    
    Dev -->|Push| GH
    Dev -->|Run| TF
    TF -->|Deploy| AWS
    
    subgraph AWS Infrastructure
        S3[S3 State]
        Resources[All Resources]
    end
    
    TF -.->|State| S3
    TF -->|Create| Resources
```

## Technology Stack

- **Infrastructure**: Terraform
- **Compute**: Lambda, App Runner
- **AI/ML**: SageMaker, AWS Bedrock
- **Storage**: S3 Vectors
- **API**: API Gateway
- **Languages**: Python 3.12
- **Container**: Docker

## Key Advantages of S3 Vectors

1. **Cost**: 90% reduction vs traditional vector databases
2. **Simplicity**: Just S3 - no complex infrastructure
3. **Scale**: Handles millions of vectors
4. **Performance**: Sub-second queries
5. **Integration**: Native AWS service

## Future Enhancements

- Frontend application (Next.js)
- User authentication
- Advanced search features
- Real-time updates
- Analytics dashboard