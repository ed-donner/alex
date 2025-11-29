"""
Retirement Agent - Cloud Run HTTP Server
Generates retirement projections
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, UTC

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from agents import Agent, Runner, trace
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from litellm.exceptions import RateLimitError

# Add parent directories to Python path for imports
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from src import Database
from templates import RETIREMENT_INSTRUCTIONS
from agent import create_agent
from observability import observe

# Load .env file from project root
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path, override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentTemporaryError(Exception):
    """Temporary error that should trigger retry"""
    pass


def get_user_preferences(job_id: str) -> Dict[str, Any]:
    """Load user preferences from database."""
    try:
        db = Database()
        
        # Get the job to find the user
        job = db.jobs.find_by_id(job_id)
        if job and job.get('clerk_user_id'):
            # Get user preferences
            user = db.users.find_by_clerk_id(job['clerk_user_id'])
            if user:
                return {
                    'years_until_retirement': user.get('years_until_retirement', 30),
                    'target_retirement_income': float(user.get('target_retirement_income', 80000)),
                    'current_age': 40  # Default for now
                }
    except Exception as e:
        logger.warning(f"Could not load user data: {e}. Using defaults.")
    
    return {
        'years_until_retirement': 30,
        'target_retirement_income': 80000.0,
        'current_age': 40
    }


# Initialize FastAPI app
app = FastAPI(
    title="Alex Retirement Service",
    description="Retirement projection agent",
    version="1.0.0"
)

# Initialize database
db = Database()


@retry(
    retry=retry_if_exception_type((RateLimitError, AgentTemporaryError, TimeoutError, asyncio.TimeoutError)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    before_sleep=lambda retry_state: logger.info(f"Retirement: Temporary error, retrying in {retry_state.next_action.sleep} seconds...")
)
async def run_retirement_agent(job_id: str, portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run the retirement specialist agent."""
    
    # Get user preferences
    user_preferences = get_user_preferences(job_id)
    
    # Initialize database
    db = Database()
    
    # Create agent (simplified - no tools or context)
    model, tools, task = create_agent(job_id, portfolio_data, user_preferences, db)
    
    # Run agent (simplified - no context)
    with trace("Retirement Agent"):
        agent = Agent(
            name="Retirement Specialist",
            instructions=RETIREMENT_INSTRUCTIONS,
            model=model,
            tools=tools  # Empty list now
        )
        
        try:
            result = await Runner.run(
                agent,
                input=task,
                max_turns=20
            )
        except (TimeoutError, asyncio.TimeoutError) as e:
            logger.warning(f"Retirement agent timeout: {e}")
            raise AgentTemporaryError(f"Timeout during agent execution: {e}")
        except Exception as e:
            error_str = str(e).lower()
            if "timeout" in error_str or "throttled" in error_str:
                logger.warning(f"Retirement temporary error: {e}")
                raise AgentTemporaryError(f"Temporary error: {e}")
            raise  # Re-raise non-retryable errors
        
        # Save the analysis to database
        retirement_payload = {
            'analysis': result.final_output,
            'generated_at': datetime.utcnow().isoformat(),
            'agent': 'retirement'
        }
        
        success = db.jobs.update_retirement(job_id, retirement_payload)
        
        if not success:
            logger.error(f"Failed to save retirement analysis for job {job_id}")
        
        return {
            'success': success,
            'message': 'Retirement analysis completed' if success else 'Analysis completed but failed to save',
            'final_output': result.final_output
        }


# Request/Response models
class JobRequest(BaseModel):
    """Request to process a job"""
    job_id: str
    portfolio_data: Dict[str, Any] = None


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Alex Retirement",
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
    Handle job processing request.
    
    Request body:
    {
        "job_id": "uuid",
        "portfolio_data": {...}  # Optional, will load from DB if not provided
    }
    """
    try:
        logger.info(f"Retirement: Received job request: {request.job_id}")
        
        # Load portfolio_data from database if not provided
        portfolio_data = request.portfolio_data
        if not portfolio_data:
            job = db.jobs.find_by_id(request.job_id)
            if not job:
                raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")
            
            user_id = job['clerk_user_id']
            user = db.users.find_by_clerk_id(user_id)
            accounts = db.accounts.find_by_user(user_id)

            portfolio_data = {
                'user_id': user_id,
                'job_id': request.job_id,
                'years_until_retirement': user.get('years_until_retirement', 30) if user else 30,
                'accounts': []
            }

            for account in accounts:
                account_data = {
                    'id': account['id'],
                    'name': account['account_name'],
                    'type': account.get('account_type', 'investment'),
                    'cash_balance': float(account.get('cash_balance', 0)),
                    'positions': []
                }

                positions = db.positions.find_by_account(account['id'])
                for position in positions:
                    instrument = db.instruments.find_by_symbol(position['symbol'])
                    if instrument:
                        account_data['positions'].append({
                            'symbol': position['symbol'],
                            'quantity': float(position['quantity']),
                            'instrument': instrument
                        })

                portfolio_data['accounts'].append(account_data)

            logger.info(f"Retirement: Loaded {len(portfolio_data['accounts'])} accounts with positions")
        
        # Run the agent
        with observe():
            result = await run_retirement_agent(request.job_id, portfolio_data)
        
        logger.info(f"Retirement completed for job {request.job_id}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retirement: Error processing job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

