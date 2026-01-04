# Guide 8: Enterprise Grade - Scalability, Security, Monitoring, Guardrails & Observability

Welcome to the final guide in the Alex Financial Advisor deployment series! In this guide, we'll transform our application into a production-ready, enterprise-grade system by implementing best practices for scalability, security, monitoring, guardrails, explainability, and observability.

By the end of this guide, your Alex Financial Advisor will be:

- **Scalable**: Ready to handle enterprise-level traffic
- **Secure**: Protected with multiple layers of security
- **Monitored**: Full visibility into system health and performance
- **Guarded**: Protected against AI hallucinations and errors
- **Explainable**: Transparent AI decision-making
- **Observable**: Complete tracing of all agent interactions

## REMINDER - MAJOR TIP!!

There's a file `gameplan.md` in the project root that describes the entire Alex project to an AI Agent, so that you can ask questions and get help. There's also an identical `CLAUDE.md` and `AGENTS.md` file. If you need help, simply start your favorite AI Agent, and give it this instruction:

> I am a student on the course AI in Production. We are in the course repo. Read the file `gameplan.md` for a briefing on the project. Read this file completely and read all the linked guides carefully. Do not start any work apart from reading and checking directory structure. When you have completed all reading, let me know if you have questions before we get started.

After answering questions, say exactly which guide you're on and any issues. Be careful to validate every suggestion; always ask for the root cause and evidence of problems. LLMs have a tendency to jump to conclusions, but they often correct themselves when they need to provide evidence.

## Section 1: Scalability

Our serverless architecture is already designed for automatic scaling, but let's explore how to configure it for enterprise-level traffic.

### Understanding Serverless Scalability

The beauty of our serverless architecture is that AWS automatically scales components based on demand:

1. **Lambda Functions** scale automatically:

   - Concurrent executions: Default 1,000 (can be increased to 10,000+)
   - Each agent can handle multiple requests simultaneously
   - No server management required

2. **Aurora Serverless v2** scales automatically:

   - From 0.5 to 1 ACU (Aurora Capacity Units) by default
   - Can scale up to 128 ACUs for high traffic
   - Scales in ~15 seconds based on load

3. **API Gateway** handles millions of requests:

   - Default throttle: 10,000 requests/second
   - Burst: 5,000 requests
   - Can be increased via AWS support

4. **SQS** provides unlimited throughput:
   - Standard queues: Nearly unlimited TPS
   - FIFO queues: 300 messages/second (can batch to 3,000)

### Configuring for Higher Scale

To prepare for enterprise traffic, you can adjust these settings in the Terraform configurations:

**In `terraform/5_database/main.tf`:**

```hcl
resource "aws_rds_cluster" "aurora" {
  # Increase max capacity for high traffic
  serverlessv2_scaling_configuration {
    max_capacity = 16  # Increase from 1 to 16 ACUs
    min_capacity = 0.5 # Keep minimum low for cost efficiency
  }
}
```

**In `terraform/6_agents/main.tf`:**

```hcl
resource "aws_lambda_function" "planner" {
  # Increase memory for faster processing
  memory_size = 10240  # Increase from 3072 to 10GB
  timeout     = 900    # Keep at 15 minutes max

  # Add reserved concurrent executions for guaranteed capacity
  reserved_concurrent_executions = 100  # Guarantee 100 concurrent
}
```

**In `terraform/7_frontend/main.tf`:**

```hcl
resource "aws_apigatewayv2_stage" "api" {
  # Configure throttling for protection
  default_route_settings {
    throttle_rate_limit  = 10000  # Requests per second
    throttle_burst_limit = 5000   # Burst capacity
  }
}
```

### Load Testing Your Application

Before going to production, test your scalability:

**For macOS/Linux:**

```bash
# Install Apache Bench
apt-get install apache2-utils  # Ubuntu/Debian
brew install apache2-utils     # macOS

# Test API endpoint (replace with your API URL)
ab -n 1000 -c 50 -H "Authorization: Bearer YOUR_TOKEN" \
   https://your-api.execute-api.region.amazonaws.com/api/user
```

**For Windows:**

```powershell
# Install Apache Bench via XAMPP or use PowerShell's Invoke-WebRequest
# Option 1: Download XAMPP which includes Apache Bench
# Visit: https://www.apachefriends.org/download.html

# Option 2: Use PowerShell for simple load testing
$headers = @{"Authorization" = "Bearer YOUR_TOKEN"}
$url = "https://your-api.execute-api.region.amazonaws.com/api/user"

# Run 100 requests sequentially
1..100 | ForEach-Object {
    Invoke-WebRequest -Uri $url -Headers $headers -Method GET
    Write-Host "Request $_ completed"
}

# For concurrent requests, consider using a tool like JMeter (cross-platform)
# Download from: https://jmeter.apache.org/download_jmeter.cgi
```

### Cost Optimization at Scale

Monitor and optimize costs as you scale:

1. **Use AWS Cost Explorer** to track spending
2. **Set up billing alerts** for unexpected costs
3. **Optimize CloudFront caching** - While CloudFront automatically caches static content from your S3 bucket, you can improve performance and reduce costs by configuring cache behaviors. Set longer TTLs (Time To Live) for assets that change infrequently (like images, CSS, JS files) using Cache-Control headers. This reduces origin requests to S3, lowering data transfer costs and improving response times.
4. **Consider Step Functions** for complex orchestrations at scale

## Section 2: Security

Our application already implements multiple security best practices. Let's review them and explore additional enterprise security features.

### Current Security Implementation

#### 1. **IAM Least Privilege Access**

Each Lambda function has minimal required permissions:

```hcl
# In terraform/6_agents/main.tf
resource "aws_iam_role_policy" "planner_policy" {
  policy = jsonencode({
    Statement = [
      {
        Effect = "Allow"
        Action = ["rds-data:ExecuteStatement", "rds-data:BatchExecuteStatement"]
        Resource = "arn:aws:rds-db:*:*:cluster:alex-database"
      },
      {
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = [
          "arn:aws:lambda:*:*:function:alex-tagger",
          "arn:aws:lambda:*:*:function:alex-reporter",
          "arn:aws:lambda:*:*:function:alex-charter",
          "arn:aws:lambda:*:*:function:alex-retirement"
        ]
      }
    ]
  })
}
```

#### 2. **JWT Authentication with Clerk**

All API calls require valid JWT tokens:

- Tokens expire after 1 hour
- **JWKS endpoint for key rotation** - Clerk automatically rotates signing keys for security. The JWKS (JSON Web Key Set) endpoint provides the current public keys used to verify JWT signatures. This means even if a key is compromised, it will be automatically rotated, and your application fetches the new keys without any code changes.
- **User context validated on every request** - Every API call includes a JWT token that is cryptographically verified using Clerk's public keys. This ensures the user is who they claim to be, their session is still valid, and the token hasn't been tampered with. Invalid or expired tokens are rejected before any business logic executes.

#### 3. **API Gateway Throttling**

**Protection against DDoS and abuse** - DDoS (Distributed Denial of Service) attacks attempt to overwhelm your application by flooding it with requests from multiple sources. API Gateway's throttling limits the number of requests per second, automatically rejecting excess traffic. This protects your Lambda functions from being overwhelmed and prevents runaway costs from malicious traffic:

```hcl
throttle_rate_limit  = 100   # 100 requests per second per user
throttle_burst_limit = 200   # Burst capacity
```

#### 4. **CORS Controls**

Strict CORS configuration:

- **Origin validation** - Only allows requests from your specific frontend domain, preventing malicious websites from making API calls on behalf of your users
- **Credentials not allowed with wildcard origins** - Prevents credential theft by ensuring authentication cookies/tokens are only sent to explicitly trusted origins, not to any website
- **Preflight caching for performance** - Browser caches CORS preflight responses, reducing the number of OPTIONS requests and improving API response times

#### 5. **XSS Protection**

**Cross-Site Scripting (XSS) prevention** - XSS attacks inject malicious scripts into your web pages that execute in users' browsers, potentially stealing credentials or personal data. Content Security Policy (CSP) headers tell the browser which sources of content are trusted, blocking any unauthorized scripts from executing:

```javascript
// In frontend pages
<meta
  httpEquiv="Content-Security-Policy"
  content="default-src 'self'; script-src 'self' 'unsafe-inline' https://clerk.com; style-src 'self' 'unsafe-inline';"
/>
```

#### 6. **Secrets Management**

Using AWS Secrets Manager:

- Database credentials never in code
- Automatic rotation capability
- Encrypted at rest with KMS

**To view your secrets:** Navigate to AWS Console → Secrets Manager → Select your region (us-east-1) → You'll see secrets like `alex-database-secret` containing your Aurora credentials

### Additional Enterprise Security Features

To further enhance security, consider implementing:

#### 1. **AWS WAF (Web Application Firewall)**

**AWS WAF** provides an additional layer of security by filtering malicious web traffic before it reaches your application. It protects against common attacks like SQL injection, cross-site scripting, and bot traffic. WAF uses rules to inspect incoming requests and can block, allow, or count requests based on conditions you define. While powerful, WAF is a paid add-on service with costs based on the number of rules and requests processed.

Add to `terraform/7_frontend/main.tf`:

```hcl
resource "aws_wafv2_web_acl" "api_protection" {
  name  = "alex-api-waf"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "RateLimitRule"
    priority = 1

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }

    action {
      block {}
    }
  }

  rule {
    name     = "SQLiRule"
    priority = 2

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesSQLiRuleSet"
      }
    }

    override_action {
      none {}
    }
  }
}
```

#### 2. **VPC Endpoints for Private Communication**

**VPC Endpoints** allow your Lambda functions to communicate with AWS services without traffic leaving the AWS network. This improves security by avoiding the public internet, reduces data transfer costs, and provides better performance with lower latency. While VPC endpoints are free to create, you pay for data processing (typically $0.01 per GB). This is especially valuable for high-security environments where data should never traverse the public internet.

Keep traffic within AWS network:

```hcl
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.region.s3"
}
```

#### 3. **AWS GuardDuty for Threat Detection**

**AWS GuardDuty** is a managed threat detection service that continuously monitors your AWS accounts and workloads for malicious activity. It uses machine learning to analyze VPC Flow Logs, CloudTrail events, and DNS logs to identify threats like cryptocurrency mining, credential compromise, and unusual API calls. GuardDuty requires no infrastructure to manage but is a paid service (approximately $1 per GB of logs analyzed). It's particularly valuable for detecting sophisticated attacks that might bypass other security layers.

```hcl
resource "aws_guardduty_detector" "main" {
  enable = true
  finding_publishing_frequency = "FIFTEEN_MINUTES"
}
```

#### 4. **Parameter Validation**

Add to Lambda functions:

```python
from pydantic import validator
import re

class PositionCreate(BaseModel):
    symbol: str

    @validator('symbol')
    def validate_symbol(cls, v):
        if not re.match(r'^[A-Z]{1,5}$', v):
            raise ValueError('Invalid symbol format')
        return v
```

## Section 3: Monitoring

Let's enhance our logging and create comprehensive CloudWatch dashboards to monitor our application.

### Enhanced Logging Implementation

First, let's ensure our agents and API have comprehensive logging:

**For the API (backend/api/main.py):**

```python
import logging
import json
from datetime import datetime

# Configure structured logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class StructuredLogger:
    @staticmethod
    def log_event(event_type, user_id=None, details=None):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "details": details
        }
        logger.info(json.dumps(log_entry))

# Add to endpoints
@app.post("/api/analyze")
async def trigger_analysis(user=Depends(clerk_guard)):
    StructuredLogger.log_event(
        "ANALYSIS_TRIGGERED",
        user_id=user.clerk_user_id,
        details={"accounts": user_id}
    )
    # ... rest of endpoint
```

**For agents (example in `backend/planner/lambda_handler.py`):**

```python
import logging
import json
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

async def run_orchestrator(job_id: str) -> None:
    start_time = datetime.now(timezone.utc)

    # Fetch the job once so we can log who triggered the run
    job = db.jobs.find_by_id(job_id)
    if not job:
        logger.error(f"Planner: Job {job_id} not found.")
        return
    user_id = job["clerk_user_id"]

    logger.info(json.dumps({
        "event": "PLANNER_STARTED",
        "job_id": job_id,
        "user_id": user_id,
        "timestamp": start_time.isoformat(),
    }))

    # ... perform tagging, price refresh, and build planner task ...

    for agent_name in ["reporter", "charter", "retirement"]:
        logger.info(json.dumps({
            "event": "AGENT_INVOKED",
            "agent": agent_name,
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

    # ... run the planner agent with Runner.run(...) ...

    end_time = datetime.now(timezone.utc)
    logger.info(json.dumps({
        "event": "PLANNER_COMPLETED",
        "job_id": job_id,
        "duration_seconds": (end_time - start_time).total_seconds(),
        "status": "success",
        "timestamp": end_time.isoformat(),
    }))
```

### Deploying and Verifying Logging Changes

After adding structured logging code (as I have already done for you in `backend/planner/lambda_handler.py`), you need to deploy the changes and verify them.

1.  **Package the new code:**

```bash
# Navigate to the backend directory
cd backend

# Run the packaging script
uv run package_docker.py
```

2.  **Deploy the new package to AWS:**

```bash
# From the same backend directory
uv run deploy_all_lambdas.py
```

3.  **Trigger a new analysis:** Go to your CloudFront website and start a new portfolio analysi, then verify the cloudwatch log.

### Creating CloudWatch Dashboards

From the terraform directory, from 8_enterprise:

Copy terraform.tfvars.example to terraform.tfvars and update the values, as usual.

Then:

`terraform init`

`terraform apply`

And follow the instructions to bring up your new CloudWatch dashboards for Bedrock & SageMaker, and Agent activity.

#### 3. **SQS Queue Monitoring**

Navigate to SQS console to view:

- Messages in flight
- Message age
- Throughput metrics
- **Dead Letter Queue (DLQ) monitoring** - Failed messages automatically move to the DLQ after multiple processing attempts. Monitor the DLQ for patterns in failures to identify systematic issues. Set up CloudWatch alarms when messages appear in the DLQ to investigate problems quickly.

### Setting Up CloudWatch Alarms

To create alarms for critical metrics, use the AWS Console:

1. **Sign in to AWS Console** as the root user (or an IAM user with CloudWatch permissions)
2. **Navigate to CloudWatch** → Select "Alarms" from the left sidebar → Click "Create alarm"
3. **Select metric** → Choose "Lambda" → "By Function Name" → Select your function (e.g., alex-api)
4. **Configure the alarm:**
   - Metric: Errors
   - Statistic: Sum
   - Period: 5 minutes
   - Threshold: Greater than 5
5. **Set notification** → Create new SNS topic → Enter your email → Confirm subscription via email
6. **Name your alarm** (e.g., "alex-api-errors") and create it

Repeat this process for other critical metrics like Duration, Throttles, and Concurrent Executions.

### Cost Monitoring

**You already have AWS billing alerts configured from earlier guides!** As a reminder, regularly check your spending:

1. **Navigate to AWS Console** → Billing Dashboard (top-right account menu)
2. **Review your current month's charges** - Check the "Bills" section
3. **Monitor your configured budget alerts** - You should have alerts at 50%, 80%, and 100% of your budget
4. **Use Cost Explorer** for detailed analysis - Filter by service to see where costs are accumulating

**Check costs frequently** during development and especially after deploying new features. Lambda and API Gateway costs can surprise you with high traffic!

## Section 4: Guardrails

**Guardrails are essential safety mechanisms for AI systems.** While advanced agent frameworks often include sophisticated guardrail features, at their core, guardrails are simply validation checks you implement in code - tests that run before or after your agents execute to ensure outputs are safe and correct. The best guardrails are implemented directly in your code where you have full control over the validation logic.

Let's implement validation and safety checks to prevent AI errors from affecting users.

### Charter Agent Output Validation

Add this validation code to `backend/charter/agent.py` to ensure well-formed JSON output:

```python
import json
import logging
from typing import Dict, Any

logger = logging.getLogger()

def validate_chart_data(chart_json: str) -> tuple[bool, str, Dict[Any, Any]]:
    """
    Validates that charter agent output is well-formed JSON with expected structure.
    Returns (is_valid, error_message, parsed_data)
    """
    try:
        # Parse JSON
        data = json.loads(chart_json)

        # Validate expected structure
        required_keys = ["charts"]
        if not all(key in data for key in required_keys):
            return False, f"Missing required keys. Expected: {required_keys}", {}

        # Validate charts array
        if not isinstance(data["charts"], list):
            return False, "Charts must be an array", {}

        # Validate each chart
        for i, chart in enumerate(data["charts"]):
            if "type" not in chart:
                return False, f"Chart {i} missing 'type' field", {}

            if "data" not in chart:
                return False, f"Chart {i} missing 'data' field", {}

            # Validate chart data is array
            if not isinstance(chart["data"], list):
                return False, f"Chart {i} data must be an array", {}

            # Validate data points have required fields based on chart type
            if chart["type"] == "pie":
                for point in chart["data"]:
                    if "name" not in point or "value" not in point:
                        return False, f"Pie chart data points must have 'name' and 'value'", {}
            elif chart["type"] == "bar":
                for point in chart["data"]:
                    if "category" not in point:
                        return False, f"Bar chart data points must have 'category'", {}

        return True, "", data

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from charter agent: {e}")
        return False, f"Invalid JSON: {e}", {}
    except Exception as e:
        logger.error(f"Unexpected error validating chart data: {e}")
        return False, f"Validation error: {e}", {}

# Use in your charter agent:
async def run_charter_agent(job_id: str, task: str) -> str:
    # ... existing agent code ...

    result = await Runner.run(agent, input=task, max_turns=10)

    # Validate output
    is_valid, error_msg, parsed_data = validate_chart_data(result.final_output)

    if not is_valid:
        logger.error(f"Charter agent produced invalid output for job {job_id}: {error_msg}")
        # Return safe fallback
        return json.dumps({
            "charts": [],
            "error": "Unable to generate charts at this time"
        })

    return json.dumps(parsed_data)
```

### Input Validation Guardrails

Add to all agents to prevent prompt injection:

```python
def sanitize_user_input(text: str) -> str:
    """Remove potential prompt injection attempts"""
    # Remove common injection patterns
    dangerous_patterns = [
        "ignore previous instructions",
        "disregard all prior",
        "forget everything",
        "new instructions:",
        "system:",
        "assistant:"
    ]

    text_lower = text.lower()
    for pattern in dangerous_patterns:
        if pattern in text_lower:
            logger.warning(f"Potential prompt injection detected: {pattern}")
            return "[INVALID INPUT DETECTED]"

    return text

# Use when processing user data
user_goals = sanitize_user_input(user.retirement_goals or "")
```

### Response Size Limits

Prevent runaway token usage:

```python
def truncate_response(text: str, max_length: int = 50000) -> str:
    """Ensure responses don't exceed reasonable size"""
    if len(text) > max_length:
        logger.warning(f"Response truncated from {len(text)} to {max_length} characters")
        return text[:max_length] + "\n\n[Response truncated due to length]"
    return text
```

### Retry Logic with Exponential Backoff

Add resilience to agent invocations using the **tenacity** library, which we already use for handling rate limit errors:

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import asyncio
from typing import Optional

# Define custom exceptions for retryable errors
class AgentTemporaryError(Exception):
    """Temporary error that should trigger retry"""
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((AgentTemporaryError, TimeoutError))
)
async def invoke_agent_with_retry(
    agent_name: str,
    payload: dict
) -> dict:
    """Invoke agent with automatic retry using tenacity"""
    try:
        response = await lambda_client.invoke(
            FunctionName=f"alex-{agent_name}",
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )

        result = json.loads(response['Payload'].read())

        # Check for retryable errors in response
        if result.get('error_type') == 'RATE_LIMIT':
            raise AgentTemporaryError(f"Rate limit hit for {agent_name}")

        return result

    except Exception as e:
        logger.warning(f"Agent {agent_name} invocation failed: {e}")
        # Determine if error is retryable
        if "throttled" in str(e).lower() or "timeout" in str(e).lower():
            raise AgentTemporaryError(f"Temporary error: {e}")
        raise  # Non-retryable error
```

**Note:** We already have tenacity configured for handling rate limit errors in our agents. This pattern extends it to handle other temporary failures with exponential backoff.

## Section 5: Explainability

Modern LLMs and agentic systems provide unprecedented transparency compared to traditional black-box AI. Let's implement explainability features to help users understand AI decision-making.

### The Evolution of Explainable AI

In the early days of deep learning, neural networks were often criticized as "black boxes" - systems that produced outputs without clear reasoning. This was a serious concern in regulated industries like finance and healthcare.

Modern Large Language Models (LLMs) and agentic systems address this concern through:

1. **Natural language explanations** - AI can explain its reasoning in plain English
2. **Chain-of-thought reasoning** - Step-by-step problem solving that's auditable
3. **Structured outputs** - Predictable, parseable responses with clear logic
4. **Prompt transparency** - The instructions given to AI are visible and modifiable

### Implementing Explainability in the Tagger Agent

Let's modify the Tagger agent to include rationale for its decisions.

In `backend/tagger/agent.py`, update the Pydantic object:

`InstrumentClassification`

so that in contains a rationale field. Be sure to have this field **before** the actual classification, so that the model needs to reason about what its doing rather than coming up with an explanation after the fact:

```python
class InstrumentClassification(BaseModel):
    """Structured output for instrument classification"""

    # ...
    rationale: str = Field(description="Detailed explanation of why these classifications were chosen, including specific factors considered")
    # ...
```

Then update the function `classify_instrument` so that it records the rationale.  
Change this:  

`   return result.final_output_as(InstrumentClassification)`

To:

```python

    classification = result.final_output_as(InstrumentClassification)
    full_json = classification.model_dump_json()
    logger.info(f"Classification rationale: {classification.rationale} Full object: {full_json}")
    return classification
```

### Adding Explainability to Portfolio Recommendations

For the Reporter agent, include reasoning in recommendations - something like:

```python
# In templates.py
ANALYSIS_INSTRUCTIONS_WITH_EXPLANATION = """
When providing recommendations, always:
1. Start with your reasoning process
2. List specific factors you considered
3. Explain why certain recommendations were prioritized
4. Include any assumptions made
5. Note any limitations or caveats

Format each recommendation as:
**Recommendation:** [The action to take]
**Reasoning:** [Why this recommendation was made]
**Impact:** [Expected outcome if implemented]
**Priority:** [High/Medium/Low based on user goals]
"""
```

### Audit Trail for Compliance

Create a comprehensive audit log for all AI decisions:

```python
class AuditLogger:
    @staticmethod
    def log_ai_decision(
        agent_name: str,
        job_id: str,
        input_data: dict,
        output_data: dict,
        model_used: str,
        duration_ms: int
    ):
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": agent_name,
            "job_id": job_id,
            "model": model_used,
            "input_hash": hashlib.sha256(
                json.dumps(input_data, sort_keys=True).encode()
            ).hexdigest(),
            "output_summary": {
                "type": type(output_data).__name__,
                "size_bytes": len(json.dumps(output_data))
            },
            "duration_ms": duration_ms,
            "compliance_check": "PASS"  # Add actual compliance logic
        }

        # Store in CloudWatch for long-term retention
        logger.info(json.dumps(audit_entry))

        # Could also store in DynamoDB for querying
        return audit_entry
```

## Section 6: Observability with LangFuse

LangFuse provides comprehensive tracing for LLM applications, giving you visibility into agent interactions, token usage, and performance metrics. We've integrated LangFuse throughout all our agents using a clean context manager pattern.

### Our Implementation Approach

We've implemented a reusable observability pattern that:

- Works transparently - agents function normally without LangFuse credentials
- Uses a context manager for automatic trace flushing
- Instruments the OpenAI Agents SDK via Pydantic Logfire
- Provides comprehensive logging at every step

### Setting Up LangFuse Account

**Step 1: Create Your LangFuse Account**

1. Go to https://cloud.langfuse.com
2. Sign up for a free account
3. Create an organization (required for the first time)
4. Create a new project called "alex-financial-advisor"
5. Navigate to Settings → API Keys
6. Create a new API key pair
7. Copy your Public Key and Secret Key (you'll need these for configuration)

**Step 2: Configure Your Environment**

Add your LangFuse credentials to `terraform/6_agents/terraform.tfvars`:

```hcl
# LangFuse observability (optional but recommended)
langfuse_public_key = "pk-lf-xxxxxxxxxx"
langfuse_secret_key = "sk-lf-xxxxxxxxxx"
langfuse_host       = "https://cloud.langfuse.com"

# Required for trace export (even with Bedrock)
openai_api_key = "sk-xxxxxxxxxx"  # Your OpenAI key
```

**Important**: The `openai_api_key` is required for LangFuse traces to export properly, even though we're using Bedrock models. This is a quirk of the OpenTelemetry integration.

### How Our Integration Works

Each agent includes an `observability.py` module that provides a context manager for LangFuse integration:

```python
from observability import observe

def lambda_handler(event, context):
    # Wrap entire handler with observability context
    with observe():
        # Your lambda code here
        result = asyncio.run(run_agent(...))
        return {...}
    # Traces automatically flush here
```

The `observe()` context manager:

- Checks for LangFuse environment variables
- Sets up Pydantic Logfire to instrument OpenAI Agents SDK
- Configures the appropriate service name (e.g., 'alex_planner_agent')
- Handles authentication gracefully
- **Automatically flushes traces on exit** (critical for Lambda)

### Observing Your Agents

**Step 3: Deploy with Observability**

From the `backend` directory:

```bash
# Package all agents with observability
uv run deploy_all_lambdas.py --package
```

From the `terraform/6_agents` directory:

```bash
# Deploy infrastructure with LangFuse variables
terraform apply
```

From the `backend` directory:

```bash
# Watch agent logs in real-time
uv run watch_agents.py
```

Finally, from the `scripts` directory:

```bash
# Deploy the complete application
uv run deploy.py
```

**Step 4: View Traces in LangFuse Dashboard**

Once deployed and running, you have two options for viewing traces:

1. **LangFuse Dashboard** (https://cloud.langfuse.com) - Visit your project to see:
2. **OpenAI Traces Dashboard** - If you're using OpenAI models, you can also view traces at https://platform.openai.com/traces

In the LangFuse dashboard, you'll see:

1. **Agent Traces**

   - Each agent execution appears as a trace
   - Filter by service name: `alex_planner_agent`, `alex_reporter_agent`, etc.
   - See the complete flow of agent interactions
   - View token usage and costs

2. **Performance Metrics**

   - Response times for each agent
   - Token consumption patterns
   - Model performance comparison
   - Success/failure rates

3. **Debug Information**
   - Exact prompts sent to models
   - Complete responses received
   - Error messages and stack traces
   - Tool calls and their results

### Using the Watch Script

We've created a monitoring script to watch all agent logs in real-time:

```bash
# Run from backend directory
uv run watch_agents.py

# Options:
uv run watch_agents.py --lookback 10  # Look back 10 minutes
uv run watch_agents.py --interval 1   # Poll every 1 second
uv run watch_agents.py --region us-west-2  # Different region
```

The watch script shows:

- Color-coded output by agent (PLANNER=blue, REPORTER=green, etc.)
- LangFuse-related logs in purple
- Errors in red
- Real-time updates from all 5 agents simultaneously

### Troubleshooting Observability

**If traces aren't appearing in LangFuse:**

1. **Check environment variables are set:**

   ```bash
   aws lambda get-function-configuration --function-name alex-planner | grep LANGFUSE
   ```

2. **Verify OPENAI_API_KEY is set** (required for export):

   ```bash
   aws lambda get-function-configuration --function-name alex-planner | grep OPENAI_API_KEY
   ```

3. **Watch CloudWatch logs for LangFuse messages:**

   ```bash
   uv run watch_agents.py --lookback 5
   ```

   Look for messages like:

   - "🔍 Observability: Setting up LangFuse..."
   - "✅ Observability: Traces flushed successfully"
   - "❌ Observability: Failed to flush traces"

4. **Check LangFuse dashboard for any traces** - sometimes they take 30-60 seconds to appear

**Common Issues:**

- **No traces but logs show success**: Usually means OPENAI_API_KEY is missing
- **Auth check failed warning**: Normal if using free tier, traces still work
- **Missing required package error**: Re-run package_docker.py to ensure dependencies are included

## Conclusion: Your Enterprise-Grade AI System

🎉 **Congratulations!** You've successfully deployed an enterprise-grade agentic AI system!

### What You've Accomplished

You've built a production-ready financial advisory platform that is:

- **Scalable**: Serverless architecture automatically handles load from 1 to 1,000,000+ users
- **Secure**: Multi-layered security with IAM, JWT auth, API throttling, CORS, XSS protection, and secrets management
- **Robust & Monitored**: Comprehensive CloudWatch logging, dashboards, alarms, and SQS dead-letter queues for reliability
- **Guarded**: Input validation, output verification, retry logic, and graceful error handling protect against AI failures
- **Explainable**: AI decisions include rationale, audit trails track all operations, and reasoning is transparent
- **Observable**: Complete LangFuse integration provides traces, token usage, costs, and performance metrics for every AI interaction
