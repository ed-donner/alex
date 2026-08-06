"""
Charter Agent - Cloud Run HTTP Server
Generates portfolio visualization data
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
from templates import CHARTER_INSTRUCTIONS
from agent import create_agent
from observability import observe

# Load .env file from project root
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path, override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Alex Charter Service",
    description="Portfolio visualization generation agent",
    version="1.0.0"
)

# Initialize database
db = Database()


@retry(
    retry=retry_if_exception_type(RateLimitError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    before_sleep=lambda retry_state: logger.info(f"Charter: Rate limit hit, retrying in {retry_state.next_action.sleep} seconds...")
)
async def run_charter_agent(job_id: str, portfolio_data: Dict[str, Any], db=None) -> Dict[str, Any]:
    """Run the charter agent to generate visualization data."""
    
    # Create agent without tools - will output JSON
    model, task = create_agent(job_id, portfolio_data, db)
    
    # Run agent - no tools, no context
    with trace("Charter Agent"):
        agent = Agent(
            name="Chart Maker",
            instructions=CHARTER_INSTRUCTIONS,
            model=model
        )
        
        result = await Runner.run(
            agent,
            input=task,
            max_turns=5  # Reduced since we expect one-shot JSON response
        )
        
        # Extract and parse JSON from the output
        output = result.final_output
        logger.info(f"Charter: Agent completed, output length: {len(output) if output else 0}")
        
        # Parse the JSON output
        charts_data = None
        charts_saved = False
        
        if output:
            # Try to find JSON in the output
            start_idx = output.find('{')
            end_idx = output.rfind('}')
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = output[start_idx:end_idx + 1]
                logger.info(f"Charter: Extracted JSON substring, length: {len(json_str)}")
                
                try:
                    parsed_data = json.loads(json_str)
                    charts = parsed_data.get('charts', [])
                    logger.info(f"Charter: Successfully parsed JSON, found {len(charts)} charts")
                    
                    if charts:
                        # Build the charts_payload with chart keys as top-level keys
                        charts_data = {}
                        for chart in charts:
                            chart_key = chart.get('key', f"chart_{len(charts_data) + 1}")
                            chart_copy = {k: v for k, v in chart.items() if k != 'key'}
                            charts_data[chart_key] = chart_copy
                        
                        logger.info(f"Charter: Created charts_data with keys: {list(charts_data.keys())}")
                        
                        # Save to database
                        if db and charts_data:
                            try:
                                success = db.jobs.update_charts(job_id, charts_data)
                                charts_saved = bool(success)
                                logger.info(f"Charter: Database update returned: {success}")
                            except Exception as e:
                                logger.error(f"Charter: Database error: {e}")
                    else:
                        logger.warning("Charter: No charts found in parsed JSON")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Charter: Failed to parse JSON: {e}")
            else:
                logger.error(f"Charter: No JSON structure found in output")
        
        return {
            'success': charts_saved,
            'message': f'Generated {len(charts_data) if charts_data else 0} charts' if charts_saved else 'Failed to generate charts',
            'charts_generated': len(charts_data) if charts_data else 0,
            'chart_keys': list(charts_data.keys()) if charts_data else []
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
        "service": "Alex Charter",
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
        logger.info(f"Charter: Received job request: {request.job_id}")
        
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

            logger.info(f"Charter: Loaded {len(portfolio_data['accounts'])} accounts with positions")
        
        # Run the agent
        with observe():
            result = await run_charter_agent(request.job_id, portfolio_data, db)
        
        logger.info(f"Charter completed for job {request.job_id}: {result}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Charter: Error processing job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

