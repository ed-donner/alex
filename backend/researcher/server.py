"""
Alex Researcher Service - Investment Advice Agent
"""

import os
import logging
from datetime import datetime, UTC
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from agents import Agent, Runner
from agents.extensions.models.litellm_model import LitellmModel

# Suppress LiteLLM warnings about optional dependencies
logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)

# Import from our modules
from context import get_agent_instructions, DEFAULT_RESEARCH_PROMPT
from mcp_servers import create_playwright_mcp_server
from tools import ingest_financial_document

# Load environment
load_dotenv(override=True)

app = FastAPI(title="Alex Researcher Service")


# Request model
class ResearchRequest(BaseModel):
    topic: Optional[str] = None  # Optional - if not provided, agent picks a topic


async def run_research_agent(topic: str = None) -> str:
    """Run the research agent to generate investment advice."""

    # Prepare the user query
    if topic:
        query = f"Research this investment topic: {topic}"
    else:
        query = DEFAULT_RESEARCH_PROMPT

    # Configure Bedrock model with us-west-2 region
    # Using OpenAI's new OSS 120B model available on Bedrock
    # Set ALL region environment variables to ensure us-west-2 is used
    os.environ["AWS_REGION_NAME"] = "us-west-2"  # LiteLLM's preferred variable
    os.environ["AWS_REGION"] = "us-west-2"       # Boto3 standard
    os.environ["AWS_DEFAULT_REGION"] = "us-west-2"  # Fallback

    # Use converse route - required for OpenAI OSS models
    model = LitellmModel(model="bedrock/converse/openai.gpt-oss-120b-1:0")

    # Create and run the agent with MCP server
    async with create_playwright_mcp_server(timeout_seconds=60) as playwright_mcp:
        agent = Agent(
            name="Alex Investment Researcher",
            instructions=get_agent_instructions(),
            model=model,
            tools=[ingest_financial_document],
            mcp_servers=[playwright_mcp],
        )

        result = await Runner.run(agent, input=query, max_turns=10)

    return result.final_output


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Alex Researcher",
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.post("/research")
async def research(request: ResearchRequest) -> str:
    """
    Generate investment research and advice.

    The agent will:
    1. Browse current financial websites for data
    2. Analyze the information found
    3. Store the analysis in the knowledge base

    If no topic is provided, the agent will pick a trending topic.
    """
    try:
        response = await run_research_agent(request.topic)
        return response
    except Exception as e:
        print(f"Error in research endpoint: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/research/auto")
async def research_auto():
    """
    Automated research endpoint for scheduled runs.
    Picks a trending topic automatically and generates research.
    Used by EventBridge Scheduler for periodic research updates.
    """
    try:
        # Always use agent's choice for automated runs
        response = await run_research_agent(topic=None)
        return {
            "status": "success",
            "timestamp": datetime.now(UTC).isoformat(),
            "message": "Automated research completed",
            "preview": response[:200] + "..." if len(response) > 200 else response,
        }
    except Exception as e:
        print(f"Error in automated research: {e}")
        return {"status": "error", "timestamp": datetime.now(UTC).isoformat(), "error": str(e)}


@app.get("/health")
async def health():
    """Detailed health check."""
    # Debug container detection
    container_indicators = {
        "dockerenv": os.path.exists("/.dockerenv"),
        "containerenv": os.path.exists("/run/.containerenv"),
        "aws_execution_env": os.environ.get("AWS_EXECUTION_ENV", ""),
        "ecs_container_metadata": os.environ.get("ECS_CONTAINER_METADATA_URI", ""),
        "kubernetes_service": os.environ.get("KUBERNETES_SERVICE_HOST", ""),
    }

    return {
        "service": "Alex Researcher",
        "status": "healthy",
        "alex_api_configured": bool(os.getenv("ALEX_API_ENDPOINT") and os.getenv("ALEX_API_KEY")),
        "timestamp": datetime.now(UTC).isoformat(),
        "debug_container": container_indicators,
        "aws_region": os.environ.get("AWS_DEFAULT_REGION", "not set"),
        "bedrock_model": "bedrock/converse/openai.gpt-oss-120b-1:0"
    }


@app.get("/test-bedrock")
async def test_bedrock():
    """Test Bedrock connection directly."""
    try:
        import boto3
        
        # Set ALL region environment variables
        os.environ["AWS_REGION_NAME"] = "us-west-2"
        os.environ["AWS_REGION"] = "us-west-2"
        os.environ["AWS_DEFAULT_REGION"] = "us-west-2"
        
        # Debug: Check what region boto3 is actually using
        session = boto3.Session()
        actual_region = session.region_name
        
        # Try to create Bedrock client explicitly in us-west-2
        client = boto3.client('bedrock-runtime', region_name='us-west-2')
        
        # Debug: Try to list models to verify connection
        try:
            bedrock_client = boto3.client('bedrock', region_name='us-west-2')
            models = bedrock_client.list_foundation_models()
            openai_models = [m['modelId'] for m in models['modelSummaries'] if 'openai' in m['modelId'].lower()]
        except Exception as list_error:
            openai_models = f"Error listing: {str(list_error)}"
        
        # Try basic model invocation with converse route
        model = LitellmModel(model="bedrock/converse/openai.gpt-oss-120b-1:0")
        
        agent = Agent(
            name="Test Agent",
            instructions="You are a helpful assistant. Be very brief.",
            model=model
        )
        
        result = await Runner.run(agent, input="Say hello in 5 words or less", max_turns=1)
        
        return {
            "status": "success",
            "model": "bedrock/converse/openai.gpt-oss-120b-1:0",
            "region": "us-west-2",
            "response": result.final_output,
            "debug": {
                "boto3_session_region": actual_region,
                "available_openai_models": openai_models
            }
        }
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "debug": {
                "boto3_session_region": session.region_name if 'session' in locals() else "unknown",
                "env_vars": {
                    "AWS_REGION_NAME": os.environ.get("AWS_REGION_NAME"),
                    "AWS_REGION": os.environ.get("AWS_REGION"),
                    "AWS_DEFAULT_REGION": os.environ.get("AWS_DEFAULT_REGION")
                }
            }
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
