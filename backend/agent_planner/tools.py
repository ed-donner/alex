"""
Utility tools for the Financial Planner Orchestrator Agent
"""

import os
import logging
import boto3
import json

logger = logging.getLogger(__name__)

def get_env_var(key: str, default: str = "") -> str:
    """Get environment variable at runtime for AgentCore compatibility."""
    return os.environ.get(key, default)

def get_agent_arn(agent_name: str) -> str:
    """Get AgentCore runtime ARN for an agent from SSM Parameter Store.

    Primary path: /agents/{name}_agent_arn (set by terraform/deploy script)
    Fallback path: /alex/agents/{name}
    """
    region = os.environ.get("DEFAULT_AWS_REGION") or os.environ.get("AWS_REGION")
    ssm = boto3.client('ssm', region_name=region) if region else boto3.client('ssm')
    paths = [
        f"/agents/{agent_name}_agent_arn",
        f"/alex/agents/{agent_name}",
    ]
    for name in paths:
        try:
            resp = ssm.get_parameter(Name=name)
            value = resp['Parameter']['Value']
            if value:
                logger.info(f"Resolved {agent_name} runtime ARN from SSM: {name}")
                return value
        except Exception:
            continue
    logger.error(f"Could not resolve runtime ARN for agent '{agent_name}' from SSM. Tried: {paths}")
    return ""

async def invoke_agent_with_boto3(agent_runtime_arn: str, session_id: str, payload: dict) -> str:
    """Invoke an AgentCore agent runtime with a JSON payload.

    Uses the bedrock-agentcore InvokeAgentRuntime API which expects:
      - agentRuntimeArn: the runtime ARN
      - payload: JSON string passed through to the agent's @app.entrypoint
    """
    region = os.environ.get("DEFAULT_AWS_REGION") or os.environ.get("AWS_REGION")
    client = boto3.client('bedrock-agentcore', region_name=region) if region else boto3.client('bedrock-agentcore')

    try:
        # Always include session id for tracing if provided
        if session_id and 'session_id' not in payload:
            payload = {**payload, 'session_id': session_id}

        resp = client.invoke_agent_runtime(
            agentRuntimeArn=agent_runtime_arn,
            payload=json.dumps(payload)
        )

        # Handle StreamingBody response properly
        # Check for 'response' field first (bedrock-agentcore format), then 'body' field
        response_body = None
        if isinstance(resp, dict):
            if 'response' in resp:
                response_body = resp['response']
            elif 'body' in resp:
                response_body = resp['body']
        
        if response_body:
            # Check if body is a StreamingBody (from botocore.response)
            if hasattr(response_body, 'read'):
                # Read the streaming body
                body_content = response_body.read()
                if isinstance(body_content, bytes):
                    body_content = body_content.decode('utf-8')
                logger.info(f"AgentCore response body: {body_content}")
                return body_content
            elif isinstance(response_body, (bytes, bytearray)):
                body_content = response_body.decode('utf-8')
                logger.info(f"AgentCore response body: {body_content}")
                return body_content
            elif isinstance(response_body, str):
                logger.info(f"AgentCore response body: {response_body}")
                return response_body
            else:
                # Try to JSON serialize other response types
                logger.info(f"AgentCore response body type: {type(response_body)}")
                return json.dumps(response_body, default=str)
        
        # If no body field, try to handle the whole response
        logger.info(f"AgentCore response type: {type(resp)}, content: {resp}")
        return json.dumps(resp, default=str)

    except Exception as e:
        logger.error(f"Error invoking agent runtime {agent_runtime_arn}: {e}")
        return f"Error invoking agent: {str(e)}"