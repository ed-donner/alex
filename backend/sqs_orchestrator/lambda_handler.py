"""
SQS to AgentCore Bridge Lambda Function

This Lambda function receives SQS messages and invokes the AgentCore planner agent.
"""

import json
import logging
import boto3
import asyncio
import os
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize boto3 clients
ssm = boto3.client('ssm')

def get_planner_agent_arn() -> str:
    """Get the planner agent ARN from SSM Parameter Store."""
    try:
        response = ssm.get_parameter(Name='/agents/planner_agent_arn')
        return response['Parameter']['Value']
    except Exception as e:
        logger.error(f"Failed to get planner agent ARN: {e}")
        raise


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

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Handle SQS messages and invoke AgentCore planner agent.
    
    Expected SQS message body: {"job_id": "uuid"}
    """
    try:
        logger.info(f"SQS Orchestrator invoked with event: {json.dumps(event)}")
        
        # Get planner agent ARN
        planner_arn = get_planner_agent_arn()
        logger.info(f"Using planner agent ARN: {planner_arn}")
        
        successful_jobs = []
        failed_jobs = []
        
        # Process each SQS record
        for record in event.get('Records', []):
            try:
                # Parse job_id from SQS message
                message_body = record['body']
                logger.info(f"Processing message: {message_body}")
                
                # Parse JSON if needed
                if isinstance(message_body, str):
                    try:
                        body_data = json.loads(message_body)
                        job_id = body_data.get('job_id', message_body)
                    except json.JSONDecodeError:
                        job_id = message_body
                else:
                    job_id = message_body
                
                logger.info(f"Extracted job_id: {job_id}")
                
                # Create payload for AgentCore
                payload = {
                    "job_id": job_id
                }
                
                logger.info(f"Invoking planner agent for job: {job_id} with payload: {payload}")
                
                # Use asyncio to call the async function
                response = asyncio.run(invoke_agent_with_boto3(planner_arn, job_id, payload))
                
                # Check if response indicates max_tokens_exceeded
                try:
                    if isinstance(response, str):
                        response_data = json.loads(response)
                        if response_data.get('max_tokens_exceeded'):
                            logger.warning(f"Planner agent reached max tokens for job: {job_id}")
                            logger.info(f"Max tokens response: {response_data.get('message', 'No message')}")
                            successful_jobs.append({
                                'job_id': job_id,
                                'status': 'max_tokens_exceeded',
                                'message': response_data.get('message', 'Agent reached max tokens limit')
                            })
                            continue
                except (json.JSONDecodeError, TypeError):
                    # Response is not JSON or not a dict, proceed normally
                    pass
                
                logger.info(f"Planner agent invoked successfully for job: {job_id}")
                logger.info(f"Response: {response}")
                successful_jobs.append(job_id)
                
            except Exception as e:
                error_message = str(e)
                # Check if this is a max_tokens related error
                if 'max_tokens' in error_message.lower() or 'maxtokensreachedException' in error_message:
                    logger.warning(f"Max tokens reached for record {record.get('messageId', 'unknown')}: {e}")
                    successful_jobs.append({
                        'job_id': job_id if 'job_id' in locals() else 'unknown',
                        'status': 'max_tokens_exceeded', 
                        'message': f'Agent reached max tokens limit: {error_message}'
                    })
                else:
                    logger.error(f"Failed to process record {record.get('messageId', 'unknown')}: {e}")
                    failed_jobs.append({
                        'messageId': record.get('messageId', 'unknown'),
                        'error': error_message
                    })
        
        # Return results
        result = {
            'statusCode': 200 if not failed_jobs else 207,  # 207 = Multi-Status
            'body': json.dumps({
                'successful_jobs': successful_jobs,
                'failed_jobs': failed_jobs,
                'total_processed': len(event.get('Records', [])),
                'success_count': len(successful_jobs),
                'failure_count': len(failed_jobs)
            })
        }
        
        logger.info(f"SQS Orchestrator completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Fatal error in SQS Orchestrator: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'successful_jobs': [],
                'failed_jobs': []
            })
        }

# For local testing
if __name__ == "__main__":
    # Test with a sample SQS event
    test_event = {
        "Records": [
            {
                "messageId": "test-message-1",
                "body": '{"job_id": "test-job-uuid-123"}'
            }
        ]
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))