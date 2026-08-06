"""
Planner Agent - Cloud Run HTTP Server
Orchestrates portfolio analysis across specialized agents
"""

import os
import sys
import json
import base64
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, UTC

# Add parent directories to Python path for imports
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from dotenv import load_dotenv
from agents import Agent, Runner, trace
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from litellm.exceptions import RateLimitError

# Load .env file from project root
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path, override=True)

# Import database package
from src import Database

# Import from common module (now in path)
from common.llm import get_litellm_model

from templates import ORCHESTRATOR_INSTRUCTIONS
from agent import create_agent, handle_missing_instruments, load_portfolio_summary
from market import update_instrument_prices
from observability import observe

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Alex Planner Service",
    description="Orchestrator agent for portfolio analysis",
    version="1.0.0"
)

# Initialize database
db = Database()


@retry(
    retry=retry_if_exception_type(RateLimitError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    before_sleep=lambda retry_state: logger.info(f"Planner: Rate limit hit, retrying in {retry_state.next_action.sleep} seconds...")
)
async def run_orchestrator(job_id: str) -> None:
    """Run the orchestrator agent to coordinate portfolio analysis."""
    try:
        # Update job status to running
        db.jobs.update_status(job_id, 'running')
        
        # Handle missing instruments first (non-agent pre-processing)
        await asyncio.to_thread(handle_missing_instruments, job_id, db)

        # Update instrument prices after tagging
        await asyncio.to_thread(update_instrument_prices, job_id, db)

        # Load portfolio summary
        portfolio_summary = await asyncio.to_thread(load_portfolio_summary, job_id, db)

        # Create and run the orchestrator agent
        model, tools, task, context = create_agent(job_id, portfolio_summary, db)

        with trace("Planner Orchestrator"):
            agent = Agent[type(context)](
                name="Financial Planner Orchestrator",
                instructions=ORCHESTRATOR_INSTRUCTIONS,
                model=model,
                tools=tools
            )

            result = await Runner.run(
                agent,
                input=task,
                context=context,
                max_turns=20
            )

        # Update job status to completed
        db.jobs.update_status(job_id, 'completed')
        logger.info(f"Planner: Orchestration completed for job {job_id}")

    except Exception as e:
        logger.error(f"Planner: Error in orchestration: {e}", exc_info=True)
        db.jobs.update_status(job_id, 'failed')
        raise


# Request/Response models
class JobRequest(BaseModel):
    """Request to process a job"""
    job_id: str


class PubSubMessage(BaseModel):
    """Pub/Sub push message format"""
    message: Dict[str, Any]
    subscription: str


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Alex Planner",
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/health")
async def health():
    """Health check endpoint (alternative)"""
    return {"status": "healthy"}


@app.post("/")
async def handle_job(request: JobRequest):
    """
    Handle job processing request (direct invocation).
    
    Used for:
    - Direct HTTP calls from other services
    - Testing
    
    Request body: {"job_id": "uuid-string"}
    
    Note: job_id must be a valid UUID and the job must exist in the database.
    """
    try:
        logger.info(f"Planner: Received direct job request: {request.job_id}")
        
        # Validate that job exists before processing
        job = db.jobs.find_by_id(request.job_id)
        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Job {request.job_id} not found in database. Create the job first via the API."
            )
        
        await run_orchestrator(request.job_id)
        return {
            "success": True,
            "message": f"Analysis completed for job {request.job_id}",
            "job_id": request.job_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Planner: Error processing job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pubsub")
async def handle_pubsub_push(request: Request):
    """
    Handle Pub/Sub push subscription.
    
    Expected format:
    {
        "message": {
            "data": "base64_encoded_json",
            "attributes": {}
        },
        "subscription": "projects/.../subscriptions/..."
    }
    """
    try:
        body = await request.json()
        message = body.get('message', {})
        
        # Decode base64 message data
        message_data = message.get('data', '')
        if not message_data:
            raise HTTPException(status_code=400, detail="No data in Pub/Sub message")
        
        decoded_data = base64.b64decode(message_data).decode('utf-8')
        payload = json.loads(decoded_data)
        job_id = payload.get('job_id')
        
        if not job_id:
            raise HTTPException(status_code=400, detail="No job_id in message payload")
        
        logger.info(f"Planner: Received Pub/Sub message for job: {job_id}")
        
        # Run orchestrator
        await run_orchestrator(job_id)
        
        return {
            "success": True,
            "message": f"Analysis completed for job {job_id}",
            "job_id": job_id
        }
    except json.JSONDecodeError as e:
        logger.error(f"Planner: Error decoding Pub/Sub message: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON in message: {e}")
    except Exception as e:
        logger.error(f"Planner: Error processing Pub/Sub message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

