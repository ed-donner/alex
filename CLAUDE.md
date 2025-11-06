# Alex - AI in Production Course Project Guide

## Project Overview

**Alex** (Agentic Learning Equities eXplainer) is a multi-agent enterprise-grade SaaS financial planning platform. This is the capstone project for Weeks 3 and 4 of the "AI in Production" course taught by Ed Donner on Udemy that deploys Agent solutions to production.

The user is a student on the course. You are working with the user to help them build Alex successfully. The user is working in Cursor (the VS Code fork), and they might be on a Windows PC, a Mac (intel or Apple silicon) or a Linux machine. All python code is run with uv and there are uv projects in every directory that needs it. The student is familiar with AWS services (Lambda, App Runner, Cloudfront) and has been introduced to Terraform, uv, NextJS and docker. They have budget alerts set, but they should still regularly check the billing screens in AWS console to keep a close watch on costs.

The student has an AWS root user, and also an IAM user called "aiengineer" with permissions. They have run `aws configure` and should be signed in as the aiengineer user with their default region.

### What Students Will Build

Students will deploy a complete production AI system featuring:
- **Multi-agent collaboration**: 5 specialized AI agents working together via orchestration
- **Serverless architecture**: Lambda, Aurora Serverless v2, App Runner, API Gateway, SQS
- **Cost-optimized vector storage**: S3 Vectors (90% cheaper than OpenSearch)
- **Real-time financial analysis**: Portfolio management, retirement projections, market research
- **Production-grade practices**: Observability, guardrails, security, monitoring
- **Full-stack application**: NextJS React frontend with Clerk authentication

### Learning Objectives

By completing this project, students will:
1. Deploy and manage production AI infrastructure on AWS
2. Implement multi-agent systems using the OpenAI Agents SDK
3. Integrate AWS Bedrock (with Nova Pro model) for LLM capabilities
4. Build cost-effective vector search with S3 Vectors and SageMaker embeddings
5. Create serverless agent orchestration with SQS and Lambda
6. Deploy a complete full-stack SaaS application
7. Implement enterprise features: monitoring, observability, guardrails, security

### Commercial Product

Alex is a SaaS product that provides insights on users' equity portfolios through reports and charts. Alex is integrated with Clerk for user management and the database architecture keeps user data separate.

---

## Directory Structure

```
alex/
├── guides/              # Step-by-step deployment guides (START HERE)
│   ├── 1_permissions.md
│   ├── 2_sagemaker.md
│   ├── 3_ingest.md
│   ├── 4_researcher.md
│   ├── 5_database.md
│   ├── 6_agents.md
│   ├── 7_frontend.md
│   ├── 8_enterprise.md
│   ├── architecture.md
│   └── agent_architecture.md
│
├── backend/             # Agent code and Lambda functions
│   ├── planner/         # Orchestrator agent
│   ├── tagger/          # Instrument classification agent
│   ├── reporter/        # Portfolio analysis agent
│   ├── charter/         # Visualization agent
│   ├── retirement/      # Retirement projection agent
│   ├── researcher/      # Market research agent (App Runner)
│   ├── ingest/          # Document ingestion Lambda
│   ├── database/        # Shared database library
│   └── api/             # FastAPI backend for frontend
│
├── frontend/            # NextJS React application
│   ├── pages/
│   ├── components/
│   └── lib/
│
├── terraform/           # Infrastructure as Code (IMPORTANT: Independent directories)
│   ├── 2_sagemaker/     # SageMaker embedding endpoint
│   ├── 3_ingestion/     # S3 Vectors and ingest Lambda
│   ├── 4_researcher/    # App Runner research service
│   ├── 5_database/      # Aurora Serverless v2
│   ├── 6_agents/        # Multi-agent Lambda functions
│   ├── 7_frontend/      # CloudFront, S3, API Gateway
│   └── 8_enterprise/    # CloudWatch dashboards and monitoring
│
└── scripts/             # Deployment and local development scripts
    ├── deploy.py        # Frontend deployment
    ├── run_local.py     # Local development
    └── destroy.py       # Cleanup script
```

---

## Course Structure: The 8 Guides

**IMPORTANT:** before working with the student, you MUST read all guides in the guides folder, in the correct order (1-8), to fully understand the project.

### Week 3: Research Infrastructure

**Day 3 - Foundations**
- **Guide 1: AWS Permissions** (1_permissions.md)
  - Set up IAM permissions for Alex project
  - Create AlexAccess group with required policies
  - Configure AWS CLI and credentials

- **Guide 2: SageMaker Deployment** (2_sagemaker.md)
  - Deploy SageMaker Serverless endpoint for embeddings
  - Use HuggingFace all-MiniLM-L6-v2 model
  - Test embedding generation
  - Understand serverless vs always-on endpoints

**Day 4 - Vector Storage**
- **Guide 3: Ingestion Pipeline** (3_ingest.md)
  - Create S3 Vectors bucket (90% cost savings!)
  - Deploy Lambda function for document ingestion
  - Set up API Gateway with API key auth
  - Test document storage and search

**Day 5 - Research Agent**
- **Guide 4: Researcher Agent** (4_researcher.md)
  - Deploy autonomous research agent on App Runner
  - Use AWS Bedrock with Nova Pro model
  - Integrate Playwright MCP server for web browsing
  - Set up EventBridge scheduler (optional)
  - **IMPORTANT**: Update `backend/researcher/server.py` with your region and model

### Week 4: Portfolio Management Platform

**Day 1 - Database**
- **Guide 5: Database & Infrastructure** (5_database.md)
  - Deploy Aurora Serverless v2 PostgreSQL
  - Enable Data API (no VPC complexity!)
  - Create database schema
  - Load seed data (22 ETFs)
  - Set up shared database library

**Day 2 - Agent Orchestra**
- **Guide 6: AI Agent Orchestra** (6_agents.md)
  - Deploy 5 Lambda agents (Planner, Tagger, Reporter, Charter, Retirement)
  - Set up SQS queue for orchestration
  - Configure agent collaboration patterns
  - Test local and remote execution
  - Implement parallel agent processing

**Day 3 - Frontend**
- **Guide 7: Frontend & API** (7_frontend.md)
  - Set up Clerk authentication
  - Deploy NextJS React frontend
  - Create FastAPI backend on Lambda
  - Configure CloudFront CDN
  - Test portfolio management and AI analysis

**Day 4 - Enterprise Features**
- **Guide 8: Enterprise Grade** (8_enterprise.md)
  - Implement scalability configurations
  - Add security layers (WAF, VPC endpoints, GuardDuty)
  - Set up CloudWatch dashboards and alarms
  - Implement guardrails and validation
  - Add explainability features
  - Configure LangFuse observability

For context, in prior weeks the students learned how to deploy to AWS, the key AWS services like Lambda and App Runner, and using Clerk for user management (needs NextJS to use Pages Router).

---

## IMPORTANT: Working with students - approach

Students might be on Windows PC, Mac (Intel or Apple Silicon) or Linux. Always use uv for ALL python code; there are uv projects in every directory. It is not a problem to have a uv project in a subdirectory of another uv project, although uv may show a warning.

Always do `uv add package` and `uv run module.py`, but NEVER `pip install xxx` and NEVER `python -c "code"` or `python -m module.py` or `python script.py`.
It is VERY IMPORTANT that you do not use the python command outside a uv project.
Try to lean away from shell scripts or Powershell scripts as they are platform dependent. Heavily favor writing python scripts (via uv) and managing files in the Cursor File Explorer, as this will be clear for all students.

## Working with Students: Core Principles

### Before starting, always read all the guides in the guides folder for the full background

### 1. **Always Establish Context First**

When a student asks for help:
1. **Ask which guide/day they're on** - This is critical for understanding what infrastructure they have deployed
2. **Ask what they're trying to accomplish** - Understand the goal before diving into code
3. **Ask what error or behavior they're seeing** - Get the actual error message, not their interpretation

### 2. **Diagnose Before Fixing** ⚠️ MOST IMPORTANT

**DO NOT jump to conclusions and write lots of code before the problem is truly understood.**

Common mistakes to avoid:
- Writing defensive code with `isinstance()` checks before understanding the root cause
- Adding try/except blocks that hide the real error
- Creating workarounds that mask the actual problem
- Making multiple changes at once (makes debugging impossible)

**Instead, follow this process:**
1. **Reproduce the issue** - Ask for exact error messages, logs, commands
2. **Identify root cause** - Use CloudWatch logs, AWS Console, error traces
3. **Verify understanding** - Explain what you think is happening and confirm with student
4. **Propose minimal fix** - Change one thing at a time
5. **Test and verify** - Confirm the fix works before moving on

### 3. **Common Root Causes (Check These First)**

Before writing any code, check these common issues:

**Docker Desktop Not Running** (Most common with `package_docker.py`)
- The script will fail with a generic uv warning about nested projects
- The real issue is Docker isn't running
- Students often get distracted by the uv warning (this was recently fixed in the script)
- **Always ask**: "Is Docker Desktop running?"

**AWS Permissions Issues** (Most common overall)
- Missing IAM policies for specific AWS services
- Region-specific permissions (ensure IAM allows Bedrock in your chosen region)
- Using inference profiles instead of direct model IDs (causes cross-region issues)
- **Check**: IAM policies, AWS region settings, bedrock_model_id configuration

**Terraform Variables Not Set**
- Each terraform directory needs its `terraform.tfvars` file configured
- Missing or incorrect variables cause cryptic errors
- **Check**: Does `terraform.tfvars` exist? Are all required variables set?

**AWS Region Mismatches**
- Bedrock models are available in major regions (us-east-1, us-west-2, eu-west-1, ap-southeast-1, etc.)
- Use **direct model IDs** (`amazon.nova-pro-v1:0`) not inference profiles to avoid cross-region routing
- Ensure `bedrock_region` in terraform.tfvars matches your IAM policy region
- **Check**: Region consistency in terraform.tfvars, IAM policies, and Lambda environment variables

**Bedrock Model Configuration (2024 Update)**
- AWS now provides **automatic access** to all serverless models (no manual approval needed)
- Use **direct model ID** `amazon.nova-pro-v1:0` NOT inference profile `us.amazon.nova-pro-v1:0`
- Nova Pro is the recommended model (Claude Sonnet has strict rate limits for student projects)
- **Check**: `bedrock_model_id` in `terraform/6_agents/terraform.tfvars` uses direct model ID

### 4. **Current Model Strategy**

**Use Nova Pro (Direct Model ID), not Claude Sonnet**
- **Recommended model ID**: `amazon.nova-pro-v1:0` (direct model, NOT inference profile)
- **Available regions**: us-east-1, us-west-2, eu-west-1, and other major AWS regions
- **Why not Claude Sonnet**: Too strict rate limits for student projects (causes frequent errors)
- **Why not inference profiles**: Adds unnecessary complexity and causes cross-region IAM errors
- **Model access**: Automatic as of 2024 (no manual request needed)

**Configuration:**
```hcl
# In terraform/6_agents/terraform.tfvars
bedrock_model_id = "amazon.nova-pro-v1:0"  # ✅ Direct model ID
bedrock_region = "us-east-1"               # Same as aws_region recommended
```

### 5. **Bedrock Model Access and Configuration (2024 Update)**

**AWS Has Changed Model Access**
- As of 2024, Bedrock model access is **automatic** for all serverless models
- No manual "request access" step needed in the console
- The old "Model access" management page has been retired
- IAM policies control access, not per-model permissions
- All serverless foundation models are enabled by default

**Critical: Inference Profiles vs Direct Model IDs**

⚠️ **Most Common Bedrock Error**: Using inference profile instead of direct model ID

**Symptoms:**
```
litellm.APIConnectionError: BedrockException -
{"Message":"User: arn:aws:sts::xxx:assumed-role/alex-lambda-agents-role/alex-xxx
is not authorized to perform: bedrock:InvokeModel on resource:
arn:aws:bedrock:us-west-2::foundation-model/amazon.nova-pro-v1:0
because no identity-based policy allows the bedrock:InvokeModel action"}
```

Even though `BEDROCK_REGION=us-east-1` in the Lambda environment, the error shows `us-west-2`.

**Root Cause:**
1. Inference profiles (`us.amazon.nova-pro-v1:0`) route requests **across multiple regions** for load balancing
2. Student's IAM policy only grants Bedrock permissions for `us-east-1`
3. The inference profile routes the request to `us-west-2` (or another region)
4. Lambda role doesn't have permission for that region → Authorization denied

**The Configuration Issue:**
```hcl
# ❌ WRONG - Inference profile (causes cross-region routing)
bedrock_model_id = "us.amazon.nova-pro-v1:0"
bedrock_region = "us-east-1"
```

The `us.` prefix indicates an inference profile, which ignores your `bedrock_region` setting and routes based on AWS's load balancing logic.

**Solution:**
1. Use **direct model ID** in `terraform/6_agents/terraform.tfvars`:
   ```hcl
   # ✅ CORRECT - Direct model ID (stays in specified region)
   bedrock_model_id = "amazon.nova-pro-v1:0"
   bedrock_region = "us-east-1"
   ```

2. Run `terraform apply` in `terraform/6_agents/` to update Lambda environment variables

3. Verify Lambda has correct environment:
   ```bash
   aws lambda get-function-configuration \
     --function-name alex-retirement \
     --query 'Environment.Variables.[BEDROCK_MODEL_ID, BEDROCK_REGION]' \
     --output table
   ```

   Should show:
   ```
   ---------------------------
   | GetFunctionConfiguration  |
   +---------------------------+
   |  amazon.nova-pro-v1:0     |
   |  us-east-1                |
   +---------------------------+
   ```

**When to Use Each:**

| Type | Model ID | Use Case | IAM Complexity |
|------|----------|----------|----------------|
| **Direct Model** | `amazon.nova-pro-v1:0` | Standard deployments, single region | Simple (one region) |
| **Inference Profile** | `us.amazon.nova-pro-v1:0` | Cross-region load balancing, high availability | Complex (multiple regions) |

**For Alex**: Always use direct model ID. Inference profiles are only needed for advanced multi-region deployments.

**Debugging Steps:**

1. Check CloudWatch logs for the actual error message
2. Look for the resource ARN in the error - what region does it show?
3. Compare to your `BEDROCK_REGION` environment variable
4. If they don't match → you're using an inference profile
5. Check `terraform/6_agents/terraform.tfvars` for the model ID
6. Update to direct model ID and `terraform apply`

### 6. **Testing Approach**

Each agent directory has two test files:
- `test_simple.py` - Local testing with mocks (uses `MOCK_LAMBDAS=true`)
- `test_full.py` - AWS deployment testing (actual Lambda invocations)

Students should:
1. Test locally first with `test_simple.py`
2. Deploy with terraform/packaging
3. Test deployment with `test_full.py`

### 6. **Help Students Help Themselves**

Encourage students to:
- Read error messages carefully (especially CloudWatch logs)
- Check AWS Console to verify resources exist
- Use `terraform output` to see deployed resource details
- Test incrementally (don't deploy everything at once)
- Keep AWS costs in mind (remind them to destroy when not actively working)

---

## Terraform Strategy

### Independent Directory Architecture

Each terraform directory (2_sagemaker, 3_ingestion, etc.) is **independent** with:
- Its own local state file (`terraform.tfstate`)
- Its own `terraform.tfvars` configuration
- No dependencies on other terraform directories

**This is intentional** for educational purposes:
- Students can deploy incrementally, guide by guide
- State files are local (simpler than remote S3 state)
- Each part can be destroyed independently
- No complex state bucket setup needed
- Infrastructure can be destroyed step by step

### Critical Requirements

**⚠️ Students MUST configure `terraform.tfvars` in each directory before running terraform apply**

Common pattern is to use the Cursor File Explorer to copy terraform.tfvars.example to terraform.tfvars and then change the variables in each directory.

If `terraform.tfvars` is missing or misconfigured:
- Terraform will use default values (often wrong)
- Resources may fail to create with cryptic errors
- Cross-service connections will break

### Terraform State Management

- State files are `.gitignored` automatically
- Local state means no S3 bucket needed
- Students can `terraform destroy` each directory independently
- If a student loses state, they may need to import existing resources or recreate

## Agent strategy - background on OpenAI Agents SDK

Each Agent subdirectory has a common structure with idiomatic patterns.

1. `lambda_handler.py` for the lambda function and running the agent
2. `agent.py` for the Agent creation and code
3. `templates.py` for prompts

Alex uses OpenAI Agents SDK. Be sure to always use the latest, idiomatic APIs for OpenAI Agents SDK, recognizing that it is a new framework. While this is already installed in all uv projects, do note that the correct package name is `openai-agents` not `agents`. So if ever creating a new project, you would do `uv add openai-agents` followed by this import statement in the code `from agents import Agent, Runner, trace`.

Alex makes standard use of LiteLLM to connect to Bedrock:

`model = LitellmModel(model=f"bedrock/{model_id}")`

Structured outputs and Tool calling is frequently used, but due to a current limitation with LiteLLM and Bedrock, the same Agent cannot use both Structured Outputs and Tool calling. So each Agent implementation either uses Structured Outputs OR uses Tools, never both.

This is the standard idiomatic approach used in lambda_handler:

```python
    # Create agent - imported from agents.py
    model, tools, task = create_agent(job_id, portfolio_data, user_preferences, db)
    
    # Run agent
    with trace("Retirement Agent"):
        agent = Agent(
            name="Retirement Specialist",
            instructions=RETIREMENT_INSTRUCTIONS,
            model=model,
            tools=tools
        )
        
        result = await Runner.run(
            agent,
            input=task,
            max_turns=20
        )

        response = result.final_output
```

In cases where a Tool needs to know which user is logged in to make the right database call, we use a standard, idomatic approach for passing context in to the tool which works very well and is recommended by OpenAI Agents SDK. 

```python

with trace("Reporter Agent"):
        agent = Agent[ReporterContext](  # Specify the context type
            name="Report Writer", instructions=REPORTER_INSTRUCTIONS, model=model, tools=tools
        )

        result = await Runner.run(
            agent,
            input=task,
            context=context,  # Pass the context
            max_turns=10,
        )

        response = result.final_output

```
And later:
```python
@function_tool
async def get_market_insights(
    wrapper: RunContextWrapper[ReporterContext], symbols: List[str]
) -> str:
...
```

IMPORTANT: when using Bedrock through LiteLLM, LiteLLM needs this environment variable set:   
`os.environ["AWS_REGION_NAME"] = bedrock_region`  
This is confusing as other services sometimes expect `"AWS_REGION"` or `"DEFAULT_AWS_REGION"`. But LiteLLM needs `AWS_REGION_NAME` as documented here: https://docs.litellm.ai/docs/providers/bedrock.


---

## Common Issues and Troubleshooting

The most common issues relate to AWS region choices! Check environment variables, terraform settings (everything should propagate from tfvars).

### Issue 1: `package_docker.py` Fails

**Symptoms**: Script fails with uv warning about nested projects and perhaps an error message

**Root Cause (common)**: Docker Desktop is not running or a Docker mounts denied issue

**Diagnosis**:
1. Ask: "Is Docker Desktop running?"
2. Check: Can they run `docker ps` successfully?
3. Recent fix: The script now gives better error messages, but older versions were misleading

**Solution**: Start Docker Desktop, wait for it to fully initialize, then retry

**If the issue is a Mounts Denied error**: It fails to mount the /tmp directory into Docker as it doesn't have access to it. Going to Docker Desktop app, and adding the directory mentioned in the error to the shared paths (Settings -> Resources -> File Sharing) solved the problem for a student.

**Not the solution**: Changing uv project configurations (this is a red herring)

### Issue 2: Bedrock Authorization Errors

**Symptoms**: "Access denied" or "not authorized to perform: bedrock:InvokeModel" errors

**Root Cause**: Using inference profile instead of direct model ID, or IAM permissions issue

**Diagnosis**:
1. Check the error message - which **region** appears in the resource ARN?
2. Check Lambda environment: `aws lambda get-function-configuration --function-name alex-XXX --query 'Environment.Variables.[BEDROCK_MODEL_ID, BEDROCK_REGION]'`
3. Does `BEDROCK_MODEL_ID` start with `us.` or `eu.`? → That's an inference profile (wrong)
4. Does the error show a different region than your `BEDROCK_REGION`? → Inference profile is routing cross-region
5. Check `terraform/6_agents/terraform.tfvars` - what's the value of `bedrock_model_id`?

**Common Error Pattern:**
```
Error resource: arn:aws:bedrock:us-west-2::foundation-model/amazon.nova-pro-v1:0
Your BEDROCK_REGION=us-east-1
```
→ This means an inference profile is routing to us-west-2 but your IAM only allows us-east-1

**Solution**:
1. Edit `terraform/6_agents/terraform.tfvars`:
   ```hcl
   bedrock_model_id = "amazon.nova-pro-v1:0"  # Remove us. or eu. prefix
   bedrock_region = "us-east-1"
   ```

2. Apply the changes:
   ```bash
   cd terraform/6_agents
   terraform apply
   ```

3. Verify the fix:
   ```bash
   aws lambda get-function-configuration \
     --function-name alex-retirement \
     --query 'Environment.Variables.BEDROCK_MODEL_ID' \
     --output text
   ```
   Should output: `amazon.nova-pro-v1:0` (no region prefix)

4. Test the agent:
   ```bash
   cd backend/retirement
   uv run test_full.py
   ```

**Note**: Model access is now automatic for all serverless Bedrock models. There is no "request access" step.

### Issue 3: Terraform Apply Fails

**Symptoms**: Resources fail to create, dependency errors, ARN not found

**Root Cause**: `terraform.tfvars` not configured, or values from previous guides not set

**Diagnosis**:
1. Does `terraform.tfvars` exist in this directory?
2. Are all required variables set (check `terraform.tfvars.example`)?
3. For later guides: Do they have output values from earlier guides?
4. Run `terraform output` in previous directories to get required ARNs

**Solution**:
1. Copy `terraform.tfvars.example` to `terraform.tfvars`
2. Fill in all required values
3. Get ARNs from previous terraform outputs: `cd terraform/X_previous && terraform output`
4. Update `.env` file with values for Python scripts

### Issue 4: Lambda Function Failures

**Symptoms**: 500 errors, timeout errors, "Module not found" errors

**Root Cause**: Package not built correctly, environment variables missing, or IAM permissions

**Diagnosis**:
1. Check CloudWatch logs: `aws logs tail /aws/lambda/alex-{agent-name} --follow`
2. Check Lambda environment variables in AWS Console
3. Check IAM role has required permissions
4. Was the Lambda package built with Docker for linux/amd64?

**Solution**:
1. For packaging: Re-run `package_docker.py` with Docker running
2. For env vars: Verify in Lambda console or `terraform.tfvars`
3. For permissions: Check IAM role policy in terraform

### Issue 5: Aurora Database Connection Fails

**Symptoms**: "Cluster not found", "Secret not found", Data API errors

**Root Cause**: Database not fully initialized, wrong ARNs, or Data API not enabled

**Diagnosis**:
1. Check cluster status: `aws rds describe-db-clusters`
2. Verify Data API is enabled (should show `EnableHttpEndpoint: true`)
3. Check ARNs in environment variables match actual resources
4. Database may still be initializing (takes 10-15 minutes)

**Solution**:
1. Wait for cluster to reach "available" status
2. Verify Data API is enabled in RDS console
3. Run `terraform output` in `5_database` to get correct ARNs
4. Update environment variables with actual ARNs

---

## Technical Architecture Quick Reference

### Core Services by Guide

**Guides 1-2**: Foundations
- IAM permissions
- SageMaker Serverless endpoint (embeddings)

**Guide 3**: Vector Storage
- S3 Vectors bucket and index
- Lambda ingest function
- API Gateway with API key

**Guide 4**: Research Agent
- App Runner service (Researcher)
- ECR repository
- EventBridge scheduler (optional)

**Guide 5**: Database
- Aurora Serverless v2 PostgreSQL
- Data API enabled
- Secrets Manager for credentials
- Database schema and seed data - **IMPORTANT** be sure to read the database schema

**Guide 6**: Agent Orchestra (The Big One)
- 5 Lambda functions: Planner, Tagger, Reporter, Charter, Retirement
- Each lambda function is implemented using OpenAI Agents SDK with simple, idiomatic code. Review an existing implementation for details.
- SQS queue for orchestration
- S3 bucket for Lambda packages (>50MB)
- Cross-service IAM permissions

**Guide 7**: Frontend
- NextJS static site on S3
- CloudFront CDN
- API Gateway + Lambda backend
- Clerk authentication

**Guide 8**: Enterprise
- CloudWatch dashboards
- Alarms and monitoring
- LangFuse observability
- Enhanced logging

### Agent Collaboration Pattern

```
User Request → SQS Queue → Planner (Orchestrator)
                            ├─→ Tagger (if needed)
                            ├─→ Reporter ──┐
                            ├─→ Charter ───┼─→ Results → Database
                            └─→ Retirement ┘
```

### Cost Management

**Cost optimization**:
- Destroy Aurora when not actively working (biggest savings)
- Use `terraform destroy` in each directory
- Monitor costs in AWS Cost Explorer

### Cleanup Process

```bash
# Destroy in reverse order (optional, but cleaner)
cd terraform/8_enterprise && terraform destroy
cd terraform/7_frontend && terraform destroy
cd terraform/6_agents && terraform destroy
cd terraform/5_database && terraform destroy  # Biggest cost savings
cd terraform/4_researcher && terraform destroy
cd terraform/3_ingestion && terraform destroy
cd terraform/2_sagemaker && terraform destroy
```

---

## Key Files Students Modify

### Configuration Files
- `.env` - Root environment variables (add values as guides progress)
- `frontend/.env.local` - Frontend Clerk configuration
- `terraform/*/terraform.tfvars` - Each terraform directory (copy from .example)

### Code Students May Need to Update
- `backend/researcher/server.py` - Region and model configuration (Guide 4) - but this should come from variables and shouldn't need code changes
- Agent templates in `backend/*/templates.py` - For customization
- Frontend pages for UI modifications

---

## Getting Help

### For Students

If you're stuck:

1. **Check the guide carefully** - Most steps have troubleshooting sections
2. **Review error messages** - Look at CloudWatch logs, not just terminal output
3. **Verify prerequisites** - Is Docker running? Are permissions set? Is terraform.tfvars configured?
4. **Contact the instructor**:
   - **Post a question in Udemy** - Include your guide number, error message, and what you've tried
   - **Email Ed Donner**: ed@edwarddonner.com

When asking for help, include:
- Which guide/day you're on
- Exact error message (copy/paste, don't paraphrase)
- What command you ran
- Relevant CloudWatch logs if available
- What you've already tried

### For Claude Code (AI Assistant)

When helping students:

0. **Prepare** - Read all the guides to be fully briefed.
1. **Establish context** - Which guide? What's the goal?
2. **Get error details** - Actual messages, logs, console output
3. **Diagnose first** - Don't write code before understanding the problem
4. **Think incrementally** - One change at a time
5. **Verify understanding** - Explain what you think is wrong before fixing
6. **Keep it simple** - Avoid over-engineering solutions

**Remember**: Students are learning. The goal is to help them understand what went wrong and how to fix it, not just to make the error go away.

---

### Course Context
- Instructor: Ed Donner
- Platform: Udemy
- Course: AI in Production
- Project: "Alex" - Capstone for Weeks 3-4

---

*This guide was created to help AI assistants (like Claude Code) effectively support students through the Alex project. Last updated: October 2025*
