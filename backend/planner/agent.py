"""
Financial Planner Orchestrator Agent - coordinates portfolio analysis across specialized agents.
"""

import os
import json
import boto3
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from agents import function_tool, RunContextWrapper
from agents.extensions.models.litellm_model import LitellmModel

logger = logging.getLogger()

# Initialize Lambda client
lambda_client = boto3.client("lambda")

# Lambda function names from environment
TAGGER_FUNCTION = os.getenv("TAGGER_FUNCTION", "alex-tagger")
REPORTER_FUNCTION = os.getenv("REPORTER_FUNCTION", "alex-reporter")
CHARTER_FUNCTION = os.getenv("CHARTER_FUNCTION", "alex-charter")
RETIREMENT_FUNCTION = os.getenv("RETIREMENT_FUNCTION", "alex-retirement")
MOCK_LAMBDAS = os.getenv("MOCK_LAMBDAS", "false").lower() == "true"


@dataclass
class PlannerContext:
    """Context for planner agent tools."""
    job_id: str


async def invoke_lambda_agent(
    agent_name: str, function_name: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Invoke a Lambda function for an agent."""

    # For local testing with mocked agents
    if MOCK_LAMBDAS:
        logger.info(f"[MOCK] Would invoke {agent_name} with payload: {json.dumps(payload)[:200]}")
        return {"success": True, "message": f"[Mock] {agent_name} completed", "mock": True}

    try:
        logger.info(f"Invoking {agent_name} Lambda: {function_name}")

        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        result = json.loads(response["Payload"].read())

        # Unwrap Lambda response if it has the standard format
        if isinstance(result, dict) and "statusCode" in result and "body" in result:
            if isinstance(result["body"], str):
                try:
                    result = json.loads(result["body"])
                except json.JSONDecodeError:
                    result = {"message": result["body"]}
            else:
                result = result["body"]

        logger.info(f"{agent_name} completed successfully")
        return result

    except Exception as e:
        logger.error(f"Error invoking {agent_name}: {e}")
        return {"error": str(e)}


def handle_missing_instruments(job_id: str, db) -> None:
    """
    Check for and tag any instruments missing allocation data.
    This is done automatically before the agent runs.
    """
    logger.info("Planner: Checking for instruments missing allocation data...")

    # Get job and portfolio data
    job = db.jobs.find_by_id(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return

    user_id = job["clerk_user_id"]
    accounts = db.accounts.find_by_user(user_id)

    missing = []
    for account in accounts:
        positions = db.positions.find_by_account(account["id"])
        for position in positions:
            instrument = db.instruments.find_by_symbol(position["symbol"])
            if instrument:
                has_allocations = bool(
                    instrument.get("allocation_regions")
                    and instrument.get("allocation_sectors")
                    and instrument.get("allocation_asset_class")
                )
                if not has_allocations:
                    missing.append(
                        {"symbol": position["symbol"], "name": instrument.get("name", "")}
                    )
            else:
                missing.append({"symbol": position["symbol"], "name": ""})

    if missing:
        logger.info(
            f"Planner: Found {len(missing)} instruments needing classification: {[m['symbol'] for m in missing]}"
        )

        try:
            response = lambda_client.invoke(
                FunctionName=TAGGER_FUNCTION,
                InvocationType="RequestResponse",
                Payload=json.dumps({"instruments": missing, "job_id": job_id}),
            )

            result = json.loads(response["Payload"].read())

            if isinstance(result, dict) and "statusCode" in result:
                if result["statusCode"] == 200:
                    logger.info(
                        f"Planner: InstrumentTagger completed - Tagged {len(missing)} instruments"
                    )
                else:
                    logger.error(
                        f"Planner: InstrumentTagger failed with status {result['statusCode']}"
                    )

        except Exception as e:
            logger.error(f"Planner: Error tagging instruments: {e}")
    else:
        logger.info("Planner: All instruments have allocation data")


def load_portfolio_summary(job_id: str, db) -> Dict[str, Any]:
    """Load basic portfolio summary statistics only."""
    try:
        job = db.jobs.find_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        user_id = job["clerk_user_id"]
        user = db.users.find_by_clerk_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        accounts = db.accounts.find_by_user(user_id)
        
        # Calculate simple summary statistics
        total_value = 0.0
        total_positions = 0
        total_cash = 0.0
        
        for account in accounts:
            total_cash += float(account.get("cash_balance", 0))
            positions = db.positions.find_by_account(account["id"])
            total_positions += len(positions)
            
            # Add position values
            for position in positions:
                instrument = db.instruments.find_by_symbol(position["symbol"])
                if instrument and instrument.get("current_price"):
                    price = float(instrument["current_price"])
                    quantity = float(position["quantity"])
                    total_value += price * quantity
        
        total_value += total_cash
        
        # Return only summary statistics
        return {
            "total_value": total_value,
            "num_accounts": len(accounts),
            "num_positions": total_positions,
            "years_until_retirement": user.get("years_until_retirement", 30),
            "target_retirement_income": float(user.get("target_retirement_income", 80000))
        }

    except Exception as e:
        logger.error(f"Error loading portfolio summary: {e}")
        raise


async def invoke_reporter_internal(job_id: str) -> str:
    """
    Invoke the Report Writer Lambda to generate portfolio analysis narrative.

    Args:
        job_id: The job ID for the analysis

    Returns:
        Confirmation message
    """
    result = await invoke_lambda_agent("Reporter", REPORTER_FUNCTION, {"job_id": job_id})

    if "error" in result:
        return f"Reporter agent failed: {result['error']}"

    return "Reporter agent completed successfully. Portfolio analysis narrative has been generated and saved."


async def invoke_charter_internal(job_id: str) -> str:
    """
    Invoke the Chart Maker Lambda to create portfolio visualizations.

    Args:
        job_id: The job ID for the analysis

    Returns:
        Confirmation message
    """
    result = await invoke_lambda_agent(
        "Charter", CHARTER_FUNCTION, {"job_id": job_id}
    )

    if "error" in result:
        return f"Charter agent failed: {result['error']}"

    return "Charter agent completed successfully. Portfolio visualizations have been created and saved."


async def invoke_retirement_internal(job_id: str) -> str:
    """
    Invoke the Retirement Specialist Lambda for retirement projections.

    Args:
        job_id: The job ID for the analysis

    Returns:
        Confirmation message
    """
    result = await invoke_lambda_agent("Retirement", RETIREMENT_FUNCTION, {"job_id": job_id})

    if "error" in result:
        return f"Retirement agent failed: {result['error']}"

    return "Retirement agent completed successfully. Retirement projections have been calculated and saved."



@function_tool
async def invoke_reporter(wrapper: RunContextWrapper[PlannerContext]) -> str:
    """Invoke the Report Writer agent to generate portfolio analysis narrative."""
    return await invoke_reporter_internal(wrapper.context.job_id)

@function_tool
async def invoke_charter(wrapper: RunContextWrapper[PlannerContext]) -> str:
    """Invoke the Chart Maker agent to create portfolio visualizations."""
    return await invoke_charter_internal(wrapper.context.job_id)

@function_tool
async def invoke_retirement(wrapper: RunContextWrapper[PlannerContext]) -> str:
    """Invoke the Retirement Specialist agent for retirement projections."""
    return await invoke_retirement_internal(wrapper.context.job_id)


def create_agent(job_id: str, portfolio_summary: Dict[str, Any], db):
    """Create the orchestrator agent with tools."""
    
    # Create context for tools
    context = PlannerContext(job_id=job_id)

    # Get model configuration
    model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
    # Set region for LiteLLM Bedrock calls
    bedrock_region = os.getenv("BEDROCK_REGION", "us-west-2")
    os.environ["AWS_REGION_NAME"] = bedrock_region

    model = LitellmModel(model=f"bedrock/{model_id}")

    tools = [
        invoke_reporter,
        invoke_charter,
        invoke_retirement,
    ]

    # Create minimal task context
    task = f"""Job {job_id} has {portfolio_summary['num_positions']} positions.
Retirement: {portfolio_summary['years_until_retirement']} years.

Call the appropriate agents."""

    return model, tools, task, context
