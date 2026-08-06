"""
Financial Planner Orchestrator Agent - coordinates portfolio analysis across specialized agents.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import id_token

# Add parent directories to Python path for imports
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from agents import function_tool, RunContextWrapper
from common.llm import get_litellm_model

logger = logging.getLogger()

# Cloud Run service URLs from environment (required)
TAGGER_SERVICE_URL = os.getenv("TAGGER_SERVICE_URL", "")
REPORTER_SERVICE_URL = os.getenv("REPORTER_SERVICE_URL", "")
CHARTER_SERVICE_URL = os.getenv("CHARTER_SERVICE_URL", "")
RETIREMENT_SERVICE_URL = os.getenv("RETIREMENT_SERVICE_URL", "")


@dataclass
class PlannerContext:
    """Context for planner agent tools."""
    job_id: str


async def invoke_cloud_run_agent(
    agent_name: str, service_url: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Invoke a Cloud Run agent service via HTTP."""
    
    if not service_url:
        raise ValueError(f"{agent_name} service URL not configured. Set {agent_name.upper()}_SERVICE_URL environment variable.")
    
    try:
        logger.info(f"Invoking {agent_name} Cloud Run service: {service_url}")
        
        # Get ID token for authentication (required for Cloud Run)
        auth_req = Request()
        token = id_token.fetch_id_token(auth_req, service_url)
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Make HTTP POST request
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                service_url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
        
        logger.info(f"{agent_name} completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error invoking {agent_name} Cloud Run service: {e}")
        return {"error": str(e)}


async def invoke_agent(agent_name: str, service_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke an agent service via Cloud Run."""
    if not service_url:
        raise ValueError(f"{agent_name} service URL not configured. Set {agent_name.upper()}_SERVICE_URL.")
    return await invoke_cloud_run_agent(agent_name, service_url, payload)


async def handle_missing_instruments(job_id: str, db) -> None:
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
            # Invoke Tagger agent via Cloud Run
            result = await invoke_agent("Tagger", TAGGER_SERVICE_URL, {"instruments": missing})

            if isinstance(result, dict):
                if result.get("success") or "error" not in result:
                    logger.info(
                        f"Planner: InstrumentTagger completed - Tagged {len(missing)} instruments"
                    )
                else:
                    logger.error(
                        f"Planner: InstrumentTagger failed: {result.get('error')}"
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
        # Handle None values - .get() only returns default if key doesn't exist, not if value is None
        years_until_retirement = user.get("years_until_retirement")
        if years_until_retirement is None:
            years_until_retirement = 30
        
        target_retirement_income = user.get("target_retirement_income")
        if target_retirement_income is None:
            target_retirement_income = 80000
        
        return {
            "total_value": total_value,
            "num_accounts": len(accounts),
            "num_positions": total_positions,
            "years_until_retirement": years_until_retirement,
            "target_retirement_income": float(target_retirement_income)
        }

    except Exception as e:
        logger.error(f"Error loading portfolio summary: {e}")
        raise


async def invoke_reporter_internal(job_id: str) -> str:
    """
    Invoke the Report Writer agent to generate portfolio analysis narrative.

    Args:
        job_id: The job ID for the analysis

    Returns:
        Confirmation message
    """
    result = await invoke_agent("Reporter", REPORTER_SERVICE_URL, {"job_id": job_id})

    if "error" in result:
        return f"Reporter agent failed: {result['error']}"

    return "Reporter agent completed successfully. Portfolio analysis narrative has been generated and saved."


async def invoke_charter_internal(job_id: str) -> str:
    """
    Invoke the Chart Maker agent to create portfolio visualizations.

    Args:
        job_id: The job ID for the analysis

    Returns:
        Confirmation message
    """
    result = await invoke_agent("Charter", CHARTER_SERVICE_URL, {"job_id": job_id})

    if "error" in result:
        return f"Charter agent failed: {result['error']}"

    return "Charter agent completed successfully. Portfolio visualizations have been created and saved."


async def invoke_retirement_internal(job_id: str) -> str:
    """
    Invoke the Retirement Specialist agent for retirement projections.

    Args:
        job_id: The job ID for the analysis

    Returns:
        Confirmation message
    """
    result = await invoke_agent("Retirement", RETIREMENT_SERVICE_URL, {"job_id": job_id})

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

    model_override = os.getenv("PLANNER_MODEL")
    model = get_litellm_model(model_override)

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
