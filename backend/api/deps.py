"""
Shared dependencies and service instances for Alex API routers.
"""

import os
import logging
import boto3
from dotenv import load_dotenv
from fastapi import Depends
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials
from src import Database

# Load environment variables
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global database instance
db = Database()

# SQS client for job queueing
sqs_client = boto3.client("sqs", region_name=os.getenv("DEFAULT_AWS_REGION", "us-east-1"))
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")

# Clerk authentication setup
clerk_config = ClerkConfig(jwks_url=os.getenv("CLERK_JWKS_URL"))
clerk_guard = ClerkHTTPBearer(clerk_config)


async def get_current_user_id(creds: HTTPAuthorizationCredentials = Depends(clerk_guard)) -> str:
    """Extract user ID from validated Clerk token"""
    user_id = creds.decoded["sub"]
    logger.info(f"Authenticated user: {user_id}")
    return user_id
