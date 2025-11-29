"""
Report Writer Agent Lambda Handler
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

from agents import Agent, Runner, trace
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from litellm.exceptions import RateLimitError
from judge import evaluate

GUARD_AGAINST_SCORE = 0.3  # Guard against score being too low

try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    pass

# Import database package
from src import Database

from templates import REPORTER_INSTRUCTIONS
from agent import create_agent, ReporterContext
from observability import observe

logger = logging.getLogger()
logger.setLevel(logging.INFO)


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
        agent = Agent[ReporterContext](  # Specify the context type
            name="Report Writer", instructions=REPORTER_INSTRUCTIONS, model=model, tools=tools
        )

        result = await Runner.run(
            agent,
            input=task,
            context=context,  # Pass the context
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


def lambda_handler(event, context):
    """
    Lambda handler expecting job_id, portfolio_data, and user_data in event.

    Expected event:
    {
        "job_id": "uuid",
        "portfolio_data": {...},
        "user_data": {...}
    }
    """
    # Wrap entire handler with observability context
    with observe() as observability:
        try:
            logger.info(f"Reporter Lambda invoked with event: {json.dumps(event)[:500]}")

            # Parse event
            if isinstance(event, str):
                event = json.loads(event)

            job_id = event.get("job_id")
            if not job_id:
                return {"statusCode": 400, "body": json.dumps({"error": "job_id is required"})}

            # Initialize database
            db = Database()

            portfolio_data = event.get("portfolio_data")
            if not portfolio_data:
                # Try to load from database
                try:
                    job = db.jobs.find_by_id(job_id)
                    if job:
                        user_id = job["clerk_user_id"]

                        if observability:
                            observability.create_event(
                                name="Reporter Started!", status_message="OK"
                            )
                        user = db.users.find_by_clerk_id(user_id)
                        accounts = db.accounts.find_by_user(user_id)

                        portfolio_data = {"user_id": user_id, "job_id": job_id, "accounts": []}

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
                    else:
                        return {
                            "statusCode": 404,
                            "body": json.dumps({"error": f"Job {job_id} not found"}),
                        }
                except Exception as e:
                    logger.error(f"Could not load portfolio from database: {e}")
                    return {
                        "statusCode": 400,
                        "body": json.dumps({"error": "No portfolio data provided"}),
                    }

            user_data = event.get("user_data", {})
            if not user_data:
                # Try to load from database
                try:
                    job = db.jobs.find_by_id(job_id)
                    if job and job.get("clerk_user_id"):
                        status = f"Job ID: {job_id} Clerk User ID: {job['clerk_user_id']}"
                        if observability:
                            observability.create_event(
                                name="Reporter about to run", status_message=status
                            )
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
                except Exception as e:
                    logger.warning(f"Could not load user data: {e}. Using defaults.")
                    user_data = {"years_until_retirement": 30, "target_retirement_income": 80000}

            # Run the agent
            result = asyncio.run(
                run_reporter_agent(job_id, portfolio_data, user_data, db, observability)
            )

            logger.info(f"Reporter completed for job {job_id}")

            return {"statusCode": 200, "body": json.dumps(result)}

        except Exception as e:
            logger.error(f"Error in reporter: {e}", exc_info=True)
            return {"statusCode": 500, "body": json.dumps({"success": False, "error": str(e)})}


# For local testing
if __name__ == "__main__":
    test_event = {
        "job_id": "550e8400-e29b-41d4-a716-446655440002",
        "portfolio_data": {
            "accounts": [
                {
                    "name": "401(k)",
                    "cash_balance": 5000,
                    "positions": [
                        {
                            "symbol": "SPY",
                            "quantity": 100,
                            "instrument": {
                                "name": "SPDR S&P 500 ETF",
                                "current_price": 450,
                                "asset_class": "equity",
                            },
                        }
                    ],
                }
            ]
        },
        "user_data": {"years_until_retirement": 25, "target_retirement_income": 75000},
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
