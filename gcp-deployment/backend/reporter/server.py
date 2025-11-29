"""
Reporter Agent - Cloud Run HTTP Server
Generates portfolio analysis reports
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

from judge import evaluate
from src import Database
from templates import REPORTER_INSTRUCTIONS
from agent import create_agent, ReporterContext
from observability import observe

# Load .env file from project root
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path, override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GUARD_AGAINST_SCORE = 0.3  # Guard against score being too low

# Initialize FastAPI app
app = FastAPI(
    title="Alex Reporter Service",
    description="Portfolio analysis report generation agent",
    version="1.0.0"
)

# Initialize database
db = Database()


@retry(
    retry=retry_if_exception_type(RateLimitError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    before_sleep=lambda retry_state: logger.info(
        f"Reporter: Rate limit hit, retrying in {retry_state.next_action.sleep} seconds..."
    ),
)
async def run_reporter_agent(
    job_id: str,
    portfolio_data: Dict[str, Any],
    user_data: Dict[str, Any],
    db=None,
    observability=None,
) -> Dict[str, Any]:
    """Run the reporter agent to generate analysis."""

    # Create agent with tools and context
    model, tools, task, context = create_agent(job_id, portfolio_data, user_data, db)

    # Run agent with context
    with trace("Reporter Agent"):
        agent = Agent[ReporterContext](
            name="Report Writer", instructions=REPORTER_INSTRUCTIONS, model=model, tools=tools
        )

        result = await Runner.run(
            agent,
            input=task,
            context=context,
            max_turns=10,
        )

        response = result.final_output

        if observability:
            with observability.start_as_current_span(name="judge") as span:
                evaluation = await evaluate(REPORTER_INSTRUCTIONS, task, response)
                score = evaluation.score / 100
                comment = evaluation.feedback
                span.score(name="Judge", value=score, data_type="NUMERIC", comment=comment)
                observation = f"Score: {score} - Feedback: {comment}"
                observability.create_event(name="Judge Event", status_message=observation)
                if score < GUARD_AGAINST_SCORE:
                    logger.error(f"Reporter score is too low: {score}")
                    response = "I'm sorry, I'm not able to generate a report for you. Please try again later."

        # Save the report to database
        report_payload = {
            "content": response,
            "generated_at": datetime.utcnow().isoformat(),
            "agent": "reporter",
        }

        success = db.jobs.update_report(job_id, report_payload)

        if not success:
            logger.error(f"Failed to save report for job {job_id}")

        return {
            "success": success,
            "message": "Report generated and stored"
            if success
            else "Report generated but failed to save",
            "final_output": result.final_output,
        }


# Request/Response models
class JobRequest(BaseModel):
    """Request to process a job"""
    job_id: str
    portfolio_data: Dict[str, Any] = None
    user_data: Dict[str, Any] = None


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Alex Reporter",
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
        "portfolio_data": {...},  # Optional, will load from DB if not provided
        "user_data": {...}         # Optional, will load from DB if not provided
    }
    """
    try:
        logger.info(f"Reporter: Received job request: {request.job_id}")
        
        # Load portfolio_data from database if not provided
        portfolio_data = request.portfolio_data
        if not portfolio_data:
            job = db.jobs.find_by_id(request.job_id)
            if not job:
                raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")
            
            user_id = job["clerk_user_id"]
            user = db.users.find_by_clerk_id(user_id)
            accounts = db.accounts.find_by_user(user_id)

            portfolio_data = {"user_id": user_id, "job_id": request.job_id, "accounts": []}

            for account in accounts:
                positions = db.positions.find_by_account(account["id"])
                account_data = {
                    "id": account["id"],
                    "name": account["account_name"],
                    "type": account.get("account_type", "investment"),
                    "cash_balance": float(account.get("cash_balance", 0)),
                    "positions": [],
                }

                for position in positions:
                    instrument = db.instruments.find_by_symbol(position["symbol"])
                    if instrument:
                        account_data["positions"].append(
                            {
                                "symbol": position["symbol"],
                                "quantity": float(position["quantity"]),
                                "instrument": instrument,
                            }
                        )

                portfolio_data["accounts"].append(account_data)
        
        # Load user_data from database if not provided
        user_data = request.user_data
        if not user_data:
            job = db.jobs.find_by_id(request.job_id)
            if job and job.get("clerk_user_id"):
                user = db.users.find_by_clerk_id(job["clerk_user_id"])
                if user:
                    user_data = {
                        "years_until_retirement": user.get("years_until_retirement", 30),
                        "target_retirement_income": float(
                            user.get("target_retirement_income", 80000)
                        ),
                    }
                else:
                    user_data = {
                        "years_until_retirement": 30,
                        "target_retirement_income": 80000,
                    }
            else:
                user_data = {"years_until_retirement": 30, "target_retirement_income": 80000}
        
        # Run the agent
        with observe() as observability:
            result = await run_reporter_agent(request.job_id, portfolio_data, user_data, db, observability)
        
        logger.info(f"Reporter completed for job {request.job_id}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reporter: Error processing job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

