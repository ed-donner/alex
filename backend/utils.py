import boto3
import json
import os
import time
from boto3.session import Session
from bedrock_agentcore_starter_toolkit import Runtime

def sleep_time_10():
    return 10


def setup_cognito_user_pool():
    boto_session = Session()
    region = boto_session.region_name
    
    # Initialize Cognito client
    cognito_client = boto3.client('cognito-idp', region_name=region)
    
    try:
        # Create User Pool
        user_pool_response = cognito_client.create_user_pool(
            PoolName='MCPServerPool',
            Policies={
                'PasswordPolicy': {
                    'MinimumLength': 8
                }
            }
        )
        pool_id = user_pool_response['UserPool']['Id']
        
        # Create App Client
        app_client_response = cognito_client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName='MCPServerPoolClient',
            GenerateSecret=False,
            ExplicitAuthFlows=[
                'ALLOW_USER_PASSWORD_AUTH',
                'ALLOW_REFRESH_TOKEN_AUTH'
            ]
        )
        client_id = app_client_response['UserPoolClient']['ClientId']
        
        # Create User
        cognito_client.admin_create_user(
            UserPoolId=pool_id,
            Username='testuser',
            TemporaryPassword='Temp123!',
            MessageAction='SUPPRESS'
        )
        
        # Set Permanent Password
        cognito_client.admin_set_user_password(
            UserPoolId=pool_id,
            Username='testuser',
            Password='MyPassword123!',
            Permanent=True
        )
        
        # Authenticate User and get Access Token
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': 'testuser',
                'PASSWORD': 'MyPassword123!'
            }
        )
        bearer_token = auth_response['AuthenticationResult']['AccessToken']
        
        # Output the required values
        print(f"Pool id: {pool_id}")
        print(f"Discovery URL: https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration")
        print(f"Client ID: {client_id}")
        print(f"Bearer Token: {bearer_token}")
        
        # Return values if needed for further processing
        return {
            'pool_id': pool_id,
            'client_id': client_id,
            'bearer_token': bearer_token,
            'discovery_url':f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
        }
        
    except Exception as e:
        print(f"Error: {e}")
        return None


def create_agentcore_role(agent_name, region="us-east-1"):
    iam_client = boto3.client('iam', region)
    agentcore_role_name = f'agentcore-{agent_name}-role'
    boto_session = Session(region_name=region)
    account_id = boto3.client("sts", region).get_caller_identity()["Account"]
    # Read optional environment variables for bucket/regions; fall back to wildcards when not provided
    vector_bucket = os.getenv("VECTOR_BUCKET", "*")
    bedrock_region = os.getenv("BEDROCK_REGION", region)
    sagemaker_endpoint = os.getenv("SAGEMAKER_ENDPOINT", "*")

    role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            # CloudWatch Logs
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": f"arn:aws:logs:{region}:{account_id}:*"
            },
            # SQS access for orchestrator
            {
                "Effect": "Allow",
                "Action": [
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes"
                ],
                "Resource": f"arn:aws:sqs:{region}:{account_id}:*"
            },
            # Lambda invocation for orchestrator to call other agents
            {
                "Effect": "Allow",
                "Action": [
                    "lambda:InvokeFunction"
                ],
                "Resource": f"arn:aws:lambda:{region}:{account_id}:function:alex-*"
            },
            # Aurora Data API access
            {
                "Effect": "Allow",
                "Action": [
                    "rds-data:ExecuteStatement",
                    "rds-data:BatchExecuteStatement",
                    "rds-data:BeginTransaction",
                    "rds-data:CommitTransaction",
                    "rds-data:RollbackTransaction"
                ],
                # Using wildcard to allow access to the data API resources; tighten if you have the ARN
                "Resource": "*"
            },
            # Secrets Manager for database credentials
            {
                "Effect": "Allow",
                "Action": [
                    "secretsmanager:GetSecretValue"
                ],
                "Resource": "*"
            },
            # S3 Vectors access for all agents
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:ListBucket"
                ],
                "Resource": [
                    f"arn:aws:s3:::{vector_bucket}",
                    f"arn:aws:s3:::{vector_bucket}/*"
                ]
            },
            # S3 Vectors API access for all agents
            {
                "Effect": "Allow",
                "Action": [
                    "s3vectors:QueryVectors",
                    "s3vectors:GetVectors"
                ],
                "Resource": f"arn:aws:s3vectors:{region}:{account_id}:bucket/{vector_bucket}/index/*"
            },
            # SageMaker endpoint access for reporter agent
            {
                "Effect": "Allow",
                "Action": [
                    "sagemaker:InvokeEndpoint"
                ],
                "Resource": f"arn:aws:sagemaker:{region}:{account_id}:endpoint/{sagemaker_endpoint}"
            },
            # Bedrock access for all agents (supports multiple regions for different models)
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                "Resource": "*"
                
            },
            # Bedrock AgentCore access for SQS orchestrator
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:InvokeAgentRuntime"
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:runtime/*"
                ]
            },
            # ECR image access (for pulling images if needed)
            {
                "Sid": "ECRImageAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:GetAuthorizationToken"
                ],
                "Resource": [
                    f"arn:aws:ecr:{region}:{account_id}:repository/*"
                ]
            },
            # ECR token access
            {
                "Sid": "ECRTokenAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken"
                ],
                "Resource": "*"
            },
            # X-Ray and CloudWatch metrics
            {
                "Effect": "Allow",
                "Action": [
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets"
                ],
                "Resource": ["*"]
            },
            {
                "Effect": "Allow",
                "Resource": "*",
                "Action": "cloudwatch:PutMetricData",
                "Condition": {
                    "StringEquals": {
                        "cloudwatch:namespace": "bedrock-agentcore"
                    }
                }
            },
            # Bedrock AgentCore workload identity access tokens
            {
                "Sid": "GetAgentAccessToken",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/{agent_name}-*"
                ]
            },
            # SSM Parameter Store access for agent ARNs and environment variables
            {
                "Sid": "SSMParameterStoreAccess",
                "Effect": "Allow",
                "Action": [
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:GetParametersByPath"
                ],
                "Resource": "*"
            }
        ]
    }
    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": f"{account_id}"
                    },
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                    }
                }
            }
        ]
    }

    assume_role_policy_document_json = json.dumps(
        assume_role_policy_document
    )
    role_policy_document = json.dumps(role_policy)
    # Create IAM Role for the Lambda function
    try:
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )

        # Pause to make sure role is created
        time.sleep(sleep_time_10())
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("Role already exists -- deleting and creating it again")
        policies = iam_client.list_role_policies(
            RoleName=agentcore_role_name,
            MaxItems=100
        )
        print("policies:", policies)
        for policy_name in policies['PolicyNames']:
            iam_client.delete_role_policy(
                RoleName=agentcore_role_name,
                PolicyName=policy_name
            )
        print(f"deleting {agentcore_role_name}")
        iam_client.delete_role(
            RoleName=agentcore_role_name
        )
        print(f"recreating {agentcore_role_name}")
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )

    # Attach the AWSLambdaBasicExecutionRole policy
    print(f"attaching role policy {agentcore_role_name}")
    try:
        iam_client.put_role_policy(
            PolicyDocument=role_policy_document,
            PolicyName="AgentCorePolicy",
            RoleName=agentcore_role_name
        )
    except Exception as e:
        print(e)

    return agentcore_iam_role


def check_status(agentcore_client, agent_arn):
    """Check the status of an agent using the AgentCore client"""
    try:
        status_response = agentcore_client.get_agent_runtime(agentRuntimeArn=agent_arn)
        status = status_response.get('status', 'UNKNOWN')
        end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']
        while status not in end_status:
            time.sleep(10)
            status_response = agentcore_client.get_agent_runtime(agentRuntimeArn=agent_arn)
            status = status_response.get('status', 'UNKNOWN')
            print(status)
        return status
    except Exception as e:
        print(f"Error checking agent status: {e}")
        return "ERROR"

def configureruntime(agent_name, agentcore_iam_role_arn, python_file_name):
    boto_session = Session(region_name=os.getenv("DEFAULT_AWS_REGION", "us-east-1"))
    region = boto_session.region_name

    agentcore_runtime = Runtime()

    response = agentcore_runtime.configure(
        entrypoint=python_file_name,
        execution_role=agentcore_iam_role_arn, #['Role']['Arn'],
        auto_create_ecr=True,
        requirements_file="requirements.txt",
        region=region,
        agent_name=agent_name
    )
    return response, agentcore_runtime



def save_env_to_ssm(env_file_path=None, prefix="/alex/env/", region=None):
    """
    Save all environment variables from .env file to AWS Systems Manager Parameter Store.
    
    Args:
        env_file_path: Path to .env file (defaults to .env in current directory)
        prefix: SSM parameter prefix (defaults to /alex/env/)
        region: AWS region (defaults to DEFAULT_AWS_REGION env var or us-east-1)
    
    Returns:
        dict: Summary of saved parameters
    """
    import os

    # Get SSM client
    ssm = boto3.client('ssm', region_name=region)
    
    saved_params = {}
    skipped_params = {}
    
    # Read .env file manually to get all key-value pairs
    with open("../../.env", 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
                
            # Parse key=value pairs
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                
                # Skip empty values
                if not value:
                    skipped_params[key] = "Empty value"
                    continue
                
                # Create SSM parameter name
                param_name = f"{prefix}{key}"
                
                try:
                    # Save to SSM Parameter Store as SecureString for sensitive data
                    ssm.put_parameter(
                        Name=param_name,
                        Value=value,
                        Type='SecureString',
                        Overwrite=True,
                        Description=f"Environment variable {key} from .env file"
                    )
                    saved_params[key] = param_name
                    print(f"✅ Saved {key} to SSM parameter: {param_name}")
                    
                except Exception as e:
                    skipped_params[key] = f"Error saving to SSM: {str(e)}"
                    print(f"❌ Failed to save {key}: {e}")
    
    summary = {
        "saved_count": len(saved_params),
        "skipped_count": len(skipped_params),
        "saved_parameters": saved_params,
        "skipped_parameters": skipped_params,
        "prefix": prefix,
        "region": region
    }
    
    print(f"\n📊 Summary: {len(saved_params)} parameters saved, {len(skipped_params)} skipped")
    return summary


def load_env_from_ssm(prefix="/alex/env/", region=None, set_env_vars=True):
    """
    Load environment variables from AWS Systems Manager Parameter Store.
    
    Args:
        prefix: SSM parameter prefix to search for (defaults to /alex/env/)
        region: AWS region (defaults to DEFAULT_AWS_REGION env var or us-east-1)
        set_env_vars: Whether to set the loaded values as environment variables
    
    Returns:
        dict: Dictionary of loaded environment variables
    """
    import os
    
    # Set default values
    if region is None:
        region = os.getenv("DEFAULT_AWS_REGION", "us-east-1")
    
    # Get SSM client
    ssm = boto3.client('ssm', region_name=region)
    
    loaded_env = {}
    
    try:
        # Get all parameters with the specified prefix
        paginator = ssm.get_paginator('get_parameters_by_path')
        
        for page in paginator.paginate(
            Path=prefix,
            Recursive=True,
            WithDecryption=True  # Decrypt SecureString parameters
        ):
            for param in page['Parameters']:
                # Extract the environment variable name from the parameter name
                env_var_name = param['Name'][len(prefix):]
                env_var_value = param['Value']
                
                loaded_env[env_var_name] = env_var_value
                
                # Set as environment variable if requested
                if set_env_vars:
                    os.environ[env_var_name] = env_var_value
                
                print(f"✅ Loaded {env_var_name} from SSM parameter: {param['Name']}")
        
        print(f"\n📊 Loaded {len(loaded_env)} environment variables from SSM")
        return loaded_env
        
    except Exception as e:
        print(f"❌ Error loading environment variables from SSM: {e}")
        return {}


def load_env_for_agent(agent_name, prefix="/alex/env/", region=None):
    """
    Convenience function for agents to load environment variables from SSM.
    Automatically sets them as environment variables.
    
    Args:
        agent_name: Name of the agent (for logging purposes)
        prefix: SSM parameter prefix (defaults to /alex/env/)
        region: AWS region (defaults to DEFAULT_AWS_REGION env var or us-east-1)
    
    Returns:
        dict: Dictionary of loaded environment variables
    """
    print(f"🔧 Loading environment variables for agent: {agent_name}")
    return load_env_from_ssm(prefix=prefix, region=region, set_env_vars=True)