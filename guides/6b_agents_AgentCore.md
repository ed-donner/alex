# Guide: Deploying Agent Core Agents

Bedrock Agent Core agents are developed under their respective `agent_{agentname}` directories. 
This is an alternative agent development on the newly released Bedrock Agentcore framework and can work alongside the existing App Runner-based agents.

The primary implementation file for each agent resides in the `agent_{agentname}/agent.py` directory. Each agent's main functionality is encapsulated within a class that is registered as an entry point using the `@app.entrypoint` decorator, where `app` is an instance of `BedrockAgentCoreApp()`.

For more details on the Bedrock AgentCore framework and its capabilities, refer to the [official AWS Bedrock AgentCore documentation](https://docs.aws.amazon.com/bedrock-agentcore/).

These agents leverage the Bedrock Agentcore framework and are tested locally using the following commands:


- **Unit Tests**: Run `uv run test_simple.py` within each agent's directory to validate individual functionality.
- **Integration Tests**: Use `backend/test_full_agentcore.py` to test all agents together and ensure seamless integration.

This guide explains how to deploy these agents using Terraform and helper scripts provided in the `6_agentcore` directory.

## Directory Structure

The `6_agentcore` directory contains the following key files:

- **`deploy_agents.py`**: Script to deploy individual or all Agent Core agents.
- **`destroy_agents.py`**: Script to destroy deployed agents.
- **`cleanup_agents.py`**: Script to clean up resources related to agents.
- **`main.tf`**: Terraform configuration file for defining infrastructure.
- **`variables.tf`**: File defining input variables for Terraform.
- **`outputs.tf`**: File defining output values for Terraform.
- **`terraform.tfvars`**: File for specifying variable values.
- **`test_agent_lifecycle.py`**: Test script for validating the lifecycle of agents.



## Test Agents Locally

Let's test each agent locally, starting with the simplest. .

**In directory**: 
- `backend/agent_tagger`
- `backend/agent_reporter`
- `backend/agent_charter`
- `backend/agent_retirement`
- `backend/agent_planner`

```bash
uv run test_simple.py
```

**Expected output**: You will see printed results indicating the success of the tests, along with any relevant output data.

## Deployment Steps

### 1. Environment Setup

Ensure the following environment variables are set in your `.env` file:

- `DEFAULT_AWS_REGION`: AWS region for deployment (e.g., `us-east-1`).
- `BEDROCK_MODEL_ID`: Bedrock model to use.

### 2. Initialize Terraform

Navigate to the `6_agentcore` directory and initialize Terraform:

```bash
cd terraform/6_agentcore
terraform init
```

### 3. Deploy Infrastructure

Review and apply the Terraform configuration:

```bash
terraform plan
terraform apply
```

### 4. Deploy Agents

Use the `deploy_agents.py` script to deploy specific agents. For example, to deploy the `planner` agent:

```bash
python deploy_agents.py planner
```

To deploy all agents:

```bash
python deploy_agents.py all
```

The following agents are supported:

- `planner`
- `tagger`
- `reporter`
- `charter`
- `retirement`

### 5. Verify Deployment

Check the AWS Management Console to verify that the agents have been deployed successfully. The ARN of each deployed agent is saved in AWS Systems Manager Parameter Store under the path `/agents/{agent_name}_agent_arn`.

## Helper Scripts

- **`deploy_agents.py`**: Automates the deployment of agents by setting up IAM roles, copying necessary files, and launching the agents.
- **`destroy_agents.py`**: Destroys deployed agents and cleans up associated resources.
- **`cleanup_agents.py`**: Removes temporary files and directories created during deployment.

## Testing

Run the `test_agent_lifecycle.py` script to validate the lifecycle of deployed agents:

```bash
python test_agent_lifecycle.py
```

## Cleanup

To destroy the infrastructure and clean up resources, use the following commands:

```bash
terraform destroy
python destroy_agents.py
```

## SQS Orchestrator Lambda

The `sqs_orchestrator` Lambda function acts as a bridge between SQS messages and the Agent Core agents. It is designed to process incoming SQS messages and invoke the appropriate Agent Core agent, such as the `planner` agent. It is deployed within the `6_agentcore` Terraform configuration.

### Key Features

- **Message Handling**: Processes SQS messages containing job details.
- **Agent Invocation**: Uses the Bedrock AgentCore API to invoke agents with the provided payload.
- **Error Handling**: Handles errors such as token limits and logs detailed information for debugging.
- **Integration with SSM**: Retrieves agent ARNs from AWS Systems Manager Parameter Store.

### Workflow

1. **Receive SQS Message**: The Lambda function is triggered by an SQS event.
2. **Extract Job ID**: Parses the `job_id` from the message body.
3. **Invoke Agent**: Calls the AgentCore API with the job details.
4. **Log Results**: Logs success or failure for each job.

### Local Testing

You can test the Lambda function locally using the provided `__main__` block in `lambda_handler.py`. For example:

```python
python lambda_handler.py
```

This will simulate an SQS event and invoke the Lambda function with a test payload.
