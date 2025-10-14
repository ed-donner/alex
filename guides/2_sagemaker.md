# Building Alex: Part 2 - SageMaker Serverless Deployment

Welcome back! In this guide, we'll deploy a SageMaker Serverless endpoint that will generate embeddings for Alex's knowledge base. This is a critical component - it converts text into numerical vectors that can be searched and compared.

## REMINDER - MAJOR TIP!!

There's a file `gameplan.md` in the project root that describes the entire Alex project to an AI Agent, so that you can ask questions and get help. There's also an identical `CLAUDE.md` and `AGENTS.md` file. If you need help, simply start your favorite AI Agent, and give it this instruction:

> I am a student on the course AI in Production. We are in the course repo. Read the file `gameplan.md` for a briefing on the project. Read this file completely and read all the linked guides carefully. Do not start any work apart from reading and checking directory structure. When you have completed all reading, let me know if you have questions before we get started.

After answering questions, say exactly which guide you're on and any issues. Be careful to validate every suggestion; always ask for the root cause and evidence of problems. LLMs have a tendency to jump to conclusions, but they often correct themselves when they need to provide evidence.

## Architecture Overview

## Why SageMaker?

We're using SageMaker for several important reasons:
1. **Production-ready**: Handles scaling, monitoring, and availability
2. **Cost-effective**: Serverless endpoints scale to zero when not in use
3. **Professional skill**: SageMaker is widely used in industry AI deployments

## What We're Building

We'll deploy:
- A SageMaker model that automatically downloads `all-MiniLM-L6-v2` from HuggingFace Hub
- A serverless endpoint that scales automatically
- Infrastructure as Code using Terraform

The beauty of this approach: no model preparation needed! SageMaker's HuggingFace container handles everything.

## Prerequisites

Before starting:
- Complete [1_permissions.md](1_permissions.md) 
- Have Terraform installed (version 1.5+)

## Step 1: Configure Terraform Variables

First, let's set up the Terraform configuration for this guide:

```bash
# Navigate to the SageMaker terraform directory
cd terraform/2_sagemaker

# Copy the example variables file
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and set your AWS region (should match your DEFAULT_AWS_REGION):
```hcl
aws_region = "us-east-1"  # Use your DEFAULT_AWS_REGION from .env
```

⚠️ **Important for non-US-East-1 regions**:
If you're deploying to a region other than `us-east-1`, you also need to update the SageMaker image URI in `variables.tf`:

1. Open `terraform/2_sagemaker/variables.tf`
2. On line 9, find the `sagemaker_image_uri` default value
3. Replace `us-east-1` with your region (e.g., `ap-southeast-2`)
4. The line should look like: `"763104351884.dkr.ecr.YOUR-REGION.amazonaws.com/huggingface-pytorch-inference:1.13.1-transformers4.26.0-cpu-py39-ubuntu20.04"`

This is necessary because AWS doesn't allow cross-region ECR image pulls.

## Step 2: Deploy with Terraform

Now let's deploy the SageMaker infrastructure. With the HuggingFace approach, there's no need to prepare model artifacts - the model will be downloaded automatically from HuggingFace Hub!

```bash
# Initialize Terraform (creates local state file)
terraform init

# Deploy the SageMaker infrastructure
terraform apply
```

When prompted, type `yes` to confirm the deployment. This will create:
- IAM role for SageMaker
- SageMaker model configuration (with HuggingFace model ID)
- Serverless endpoint

## Step 3: Understanding What Was Created

Terraform created several resources:

1. **IAM Role**: Gives SageMaker permissions it needs
2. **SageMaker Model**: Configuration pointing to HuggingFace model `sentence-transformers/all-MiniLM-L6-v2`
3. **Serverless Endpoint**: The API endpoint for generating embeddings

After deployment, Terraform will display important outputs including setup instructions.

### Save Your Configuration

**Important**: Update your `.env` file with the endpoint name:

1. Note the endpoint name from Terraform output (should be `alex-embedding-endpoint`)
2. Edit `.env` in Cursor
3. Update this line:
   ```
   # Part 2 - SageMaker
   SAGEMAKER_ENDPOINT=alex-embedding-endpoint
   ```

💡 **Tip**: Terraform outputs are shown at the end of `terraform apply`. You can also view them anytime with:
```bash
terraform output
```

## Step 4: Test the Endpoint

Let's verify the endpoint works with a simple test:

```bash
# Navigate to backend directory where test payload is located
cd ../../backend

# Invoke the endpoint and output directly to console
aws sagemaker-runtime invoke-endpoint --endpoint-name alex-embedding-endpoint --content-type application/json --body fileb://vectorize_me.json --output json /dev/stdout
```

You'll see a JSON array with 384 floating-point numbers - that's the text "vectorize me" converted into a vector embedding!

**Note**: The first request to a serverless endpoint can take 10-60 seconds (cold start). Subsequent requests will be much faster.

## Cost Analysis

Your serverless endpoint:
- **Scales to zero**: No charges when not in use
- **Request pricing**: ~$0.00002 per second of compute
- **Memory**: 3GB allocated (AWS default limit for serverless)
- **Estimated cost**: $1-2/month for typical usage (1000 requests/day)

## Troubleshooting

If the endpoint invocation fails:

1. **Check endpoint status**:
```bash
aws sagemaker describe-endpoint --endpoint-name alex-embedding-endpoint
```
Status should be "InService"

2. **Check CloudWatch logs**:
```bash
aws logs tail /aws/sagemaker/Endpoints/alex-embedding-endpoint --follow
```

3. **Verify the HuggingFace model ID**:
Check that the endpoint is configured with the correct model:
```bash
aws sagemaker describe-model --model-name alex-embedding-model --query 'PrimaryContainer.Environment'
```
Should show: `{"HF_MODEL_ID": "sentence-transformers/all-MiniLM-L6-v2", "HF_TASK": "feature-extraction"}`

**Note**: If you're not in the default region, add `--region your-region` to these commands.

## Understanding Serverless vs Always-On

We chose serverless because:
- **Cold starts**: 5-10 seconds (acceptable for our use case)
- **Cost savings**: ~$1-2/month vs $50-100/month for always-on
- **Auto-scaling**: Handles traffic spikes automatically

For production systems with strict latency requirements, you might choose always-on endpoints.

## MLOps in SageMaker

### What is MLOps?

MLOps (Machine Learning Operations) is the practice of applying DevOps principles to machine learning systems. SageMaker is AWS's comprehensive platform for MLOps, providing tools for the entire ML lifecycle: data preparation, model training, deployment, monitoring, and retraining.

In production ML systems, you need to manage:
- **Model Versioning**: Track different versions of your models as they evolve
- **A/B Testing**: Compare model performance in production
- **Model Monitoring**: Detect when models degrade over time
- **Automated Retraining**: Retrain models when performance drops
- **Model Registry**: Central repository for approved models
- **Pipeline Automation**: Orchestrate the entire ML workflow

### Model Drift and Why It Matters

**Model drift** occurs when a model's performance degrades over time because the data it sees in production differs from its training data. For our embedding model, drift might occur if:
- Language usage evolves (new financial terms emerge)
- User behavior changes (different types of queries)
- Market conditions shift (new investment products)

SageMaker Model Monitor can automatically detect drift by:
- Analyzing prediction distributions over time
- Comparing current inputs to training data baselines
- Alerting when statistical properties change significantly
- Triggering automated retraining pipelines

### Explore SageMaker in the AWS Console

Let's explore what else SageMaker can do. Navigate to the SageMaker console and explore these sections:

1. **Go to SageMaker Console**:
   ```
   https://console.aws.amazon.com/sagemaker/
   ```

2. **Explore Key MLOps Features** (left sidebar):
   - **Model Registry**: Browse to see how teams manage model versions
   - **Pipelines**: View how ML workflows are automated
   - **Model Monitor**: See how drift detection works
   - **Experiments**: Track training runs and hyperparameters
   - **Feature Store**: Centralized feature management
   - **Ground Truth**: Data labeling service

3. **Check Your Endpoint**:
   - Click "Inference" → "Endpoints"
   - Find `alex-embedding-endpoint`
   - Click on it to see metrics, configuration, and monitoring options
   - Notice the "Data capture" option for model monitoring

4. **Explore Model Versions**:
   - Click "Inference" → "Models"
   - See how SageMaker tracks model artifacts and configurations
   - Each model has a unique ARN for versioning

### SageMaker vs Bedrock: When to Use Each

You've already worked with Bedrock, so let's clarify when to use each service:

| Aspect | SageMaker | Bedrock |
|--------|-----------|----------|
| **Use Case** | Deploy YOUR own models or fine-tuned models | Use pre-trained foundation models via API |
| **Model Source** | Open source, custom trained, or fine-tuned | AWS-hosted models (Claude, Llama, etc.) |
| **Customization** | Full control over model, training, infrastructure | Limited to prompt engineering and RAG |
| **Cost Model** | Pay for infrastructure (compute hours) | Pay per API call (tokens) |
| **Setup Complexity** | Higher - manage endpoints, scaling, monitoring | Lower - just API calls |
| **MLOps Features** | Full suite - versioning, monitoring, pipelines | Minimal - mostly usage tracking |
| **Best For** | • Custom models<br>• Fine-tuned models<br>• Specialized embeddings<br>• Full ML pipelines | • General language tasks<br>• Quick prototypes<br>• Standard AI capabilities |
| **Latency** | Predictable (always-on) or variable (serverless) | Generally low, consistent |
| **Scaling** | You manage (auto-scaling available) | Fully managed by AWS |

### Real-World Example Decisions

**Use SageMaker when:**
- You need a specific embedding model (like our all-MiniLM-L6-v2)
- You've fine-tuned a model on your company's data
- You need full control over model versioning and deployment
- You want to implement custom preprocessing or postprocessing
- You need to monitor for model drift
- Compliance requires on-premises or VPC deployment

**Use Bedrock when:**
- You need general-purpose language understanding (like our Part 6 agents)
- You want to prototype quickly without infrastructure
- The task fits well with prompt engineering
- You need access to cutting-edge foundation models
- You want to minimize operational overhead
- Token-based pricing fits your usage pattern

### Advanced SageMaker Capabilities

Beyond what we've deployed, SageMaker offers:

- **SageMaker Studio**: IDE for ML development
- **Multi-Model Endpoints**: Host multiple models on one endpoint
- **Model Compilation (Neo)**: Optimize models for specific hardware
- **Edge Deployment**: Deploy models to IoT devices
- **Distributed Training**: Train large models across multiple GPUs
- **Hyperparameter Tuning**: Automated optimization of model parameters
- **Batch Transform**: Process large datasets offline
- **Data Wrangler**: Visual data preparation tool

### Try This: Check Model Metrics

While your endpoint is running, check its CloudWatch metrics:

```bash
# View invocation metrics
aws cloudwatch get-metric-statistics --namespace "AWS/SageMaker" --metric-name "Invocations" --dimensions Name=EndpointName,Value=alex-embedding-endpoint --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) --end-time $(date -u +%Y-%m-%dT%H:%M:%S) --period 300 --statistics Sum --region $(aws configure get region)
```

This shows how SageMaker automatically tracks model usage - essential for MLOps!

## Troubleshooting

### Endpoint Already Exists Error

If you see "Cannot create already existing endpoint" error during `terraform apply`, this means the endpoint was created but Terraform lost track of it (usually because the apply was interrupted). To fix:

**Option 1: Import the existing endpoint** (recommended)
```bash
terraform import aws_sagemaker_endpoint.embedding_endpoint alex-embedding-endpoint
terraform apply
```

**Option 2: Delete and recreate**
```bash
aws sagemaker delete-endpoint --endpoint-name alex-embedding-endpoint
# Wait for deletion to complete (check with describe-endpoint)
terraform apply
```

### Terraform Apply Takes Forever

SageMaker serverless endpoints can take 3-5 minutes to create. Be patient and don't interrupt the process! If you do interrupt it, see "Endpoint Already Exists Error" above.

### Endpoint Creation Fails with IAM Role Error

If you see an error about the IAM role being invalid during `terraform apply`, this is due to a known issue with IAM propagation delays. The Terraform configuration includes a workaround that adds a 15-second delay before creating the endpoint to allow the IAM role to fully propagate.

If you still encounter issues:
1. Run `terraform destroy` to clean up
2. Wait a minute for IAM to fully propagate
3. Run `terraform apply` again

The error message may be misleading - it often indicates quota limits or propagation delays rather than actual IAM issues.

## Clean Up (Optional)

If you need to tear down just the SageMaker infrastructure:

```bash
cd terraform/2_sagemaker
terraform destroy
```

⚠️ This will only remove the SageMaker resources from this guide, not other parts!

## Next Steps

Congratulations! You've deployed a production-grade ML model on AWS. 

In the next guide, we'll:
1. Set up S3 Vectors for cost-effective vector storage (90% cheaper!)
2. Create a Lambda function to connect everything
3. Build an API for ingesting financial knowledge

Your SageMaker endpoint is ready and waiting. Let's continue building Alex! 🎉

Continue to: [3_ingest.md](3_ingest.md)