"""
Financial Planner Orchestrator Agent - AgentCore Implementation

This agent coordinates portfolio analysis across specialized agents using
the invoke_agent_with_boto3 pattern for orchestration.

Version: Updated 2025-10-28
"""

import json
import os
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

# Load environment variables from SSM at startup
# import sys
# sys.path.append('/opt/python')  # Add common layer path if available
from utils import load_env_from_ssm
load_env_from_ssm()
    # Fallback to local .env file
print(f"🔍 DEBUG: Starting imports after environment loading")
from strands import Agent, tool

from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
# Import parent directory utils
import sys
import os

# Add current directory to Python path for src imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

print(f"🔍 DEBUG: About to import tools")
from tools import get_agent_arn, invoke_agent_with_boto3
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))

print(f"🔍 DEBUG: About to import Database")
from src import Database

print(f"🔍 DEBUG: About to import job_progress")
# Add job progress tracking
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))



def add_job_progress(db, job_id, message, agent=None, details=None):
    print(f"🔍 DEBUG: Adding job progress: job_id={job_id}, message={message}, agent={agent}, details={details}")


def load_portfolio_summary(job_id: str, db: Database) -> Dict[str, Any]:
    """Load basic portfolio summary statistics."""
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
        
        raise

print(f"✅ DEBUG: load_portfolio_summary function defined")

print(f"🔍 DEBUG: About to define @tool decorated functions")

@tool
async def invoke_reporter_agent(job_id: str) -> str:
    """
    Invoke the Report Writer agent to generate portfolio analysis narrative.
    
    Args:
        job_id: The job ID for the analysis
        
    Returns:
        Analysis result message
    """
    try:
        # Get database instance
        print(f"🔍 DEBUG: invoke_reporter_agent called with job_id: {job_id}")
        db = Database()
        
        agent_arn = get_agent_arn("reporter")
        if not agent_arn:
            add_job_progress(db, job_id, "Error: Could not find Reporter agent ARN", "planner")
            return "Error: Could not find Reporter agent ARN"

        session_id = f"planner-{job_id}-{int(datetime.now().timestamp())}"
        
        # Load portfolio data to pass to reporter agent
        try:
            job = db.jobs.find_by_id(job_id)
            if job and job.get("clerk_user_id"):
                user_id = job["clerk_user_id"]
                accounts = db.accounts.find_by_user(user_id)
                
                portfolio_data = {"accounts": []}
                for account in accounts:
                    positions = db.positions.find_by_account(account["id"])
                    account_data = {
                        "id": account["id"],
                        "name": account.get("account_name", ""),
                        "cash_balance": float(account.get("cash_balance", 0)),
                        "positions": []
                    }
                    
                    for position in positions:
                        instrument = db.instruments.find_by_symbol(position["symbol"])
                        position_data = {
                            "symbol": position["symbol"],
                            "quantity": float(position["quantity"]),
                            "instrument": instrument or {}
                        }
                        account_data["positions"].append(position_data)
                    
                    portfolio_data["accounts"].append(account_data)
                
                payload = {"job_id": job_id, "portfolio_data": portfolio_data}
            else:
                payload = {"job_id": job_id}
        except Exception as e:
            payload = {"job_id": job_id}

        start_ts = datetime.now()
        add_job_progress(db, job_id, f"Invoking Reporter agent", "planner")
        result = await invoke_agent_with_boto3(agent_arn, session_id, payload)
        duration = (datetime.now() - start_ts).total_seconds()

        preview = (result or "").strip()
        if len(preview) > 300:
            preview = preview[:300] + "..."
        add_job_progress(db, job_id, f"Reporter completed in {duration:.1f}s", "planner")

        return f"Reporter agent completed: {result}"

    except Exception as e:
        db = Database()
        # Check if this is a MaxTokensReachedException
        if 'max_tokens' in str(e).lower() or 'maxtokensreachedException' in str(e) or e.__class__.__name__ == 'MaxTokensReachedException':
            add_job_progress(db, job_id, f"Reporter stopped: Reached maximum token limit", "planner")
            return f"Reporter agent stopped due to max tokens limit: {str(e)}"
        else:
            add_job_progress(db, job_id, f"Reporter failed: {str(e)}", "planner")
            return f"Reporter agent failed: {str(e)}"

print(f"✅ DEBUG: invoke_reporter_agent function defined")

@tool
async def invoke_charter_agent(job_id: str) -> str:
    """
    Invoke the Chart Maker agent to create portfolio visualizations.
    
    Args:
        job_id: The job ID for the analysis
        
    Returns:
        Chart creation result message
    """
    try:
        print(f"🔍 DEBUG: invoke_charter_agent called with job_id: {job_id}")
        # Get database instance  
        db = Database()
        
        agent_arn = get_agent_arn("charter")
        if not agent_arn:
            add_job_progress(db, job_id, "Error: Could not find Charter agent ARN", "planner")
            return "Error: Could not find Charter agent ARN"

        session_id = f"planner-{job_id}-{int(datetime.now().timestamp())}"
        # Charter benefits from portfolio_data; planner can optionally load it later
        payload = {"job_id": job_id}

        start_ts = datetime.now()
        add_job_progress(db, job_id, f"Invoking Charter agent", "planner")
        result = await invoke_agent_with_boto3(agent_arn, session_id, payload)
        duration = (datetime.now() - start_ts).total_seconds()

        preview = (result or "").strip()
        if len(preview) > 300:
            preview = preview[:300] + "..."
        add_job_progress(db, job_id, f"Charter completed in {duration:.1f}s", "planner")

        return f"Charter agent completed: {result}"

    except Exception as e:
        db = Database()
        # Check if this is a MaxTokensReachedException
        if 'max_tokens' in str(e).lower() or 'maxtokensreachedException' in str(e) or e.__class__.__name__ == 'MaxTokensReachedException':
            add_job_progress(db, job_id, f"Charter stopped: Reached maximum token limit", "planner")
            return f"Charter agent stopped due to max tokens limit: {str(e)}"
        else:
            add_job_progress(db, job_id, f"Charter failed: {str(e)}", "planner")
            return f"Charter agent failed: {str(e)}"

print(f"✅ DEBUG: invoke_charter_agent function defined")

@tool
async def invoke_retirement_agent(job_id: str) -> str:
    """
    Invoke the Retirement Specialist agent for retirement projections.
    
    Args:
        job_id: The job ID for the analysis
        
    Returns:
        Retirement analysis result message
    """
    try:
        print(f"🔍 DEBUG: invoke_retirement_agent called with job_id: {job_id}")
        # Get database instance
        db = Database()
        
        agent_arn = get_agent_arn("retirement")
        if not agent_arn:
            add_job_progress(db, job_id, "Error: Could not find Retirement agent ARN", "planner")
            return "Error: Could not find Retirement agent ARN"

        session_id = f"planner-{job_id}-{int(datetime.now().timestamp())}"
        payload = {"job_id": job_id}

        start_ts = datetime.now()
        add_job_progress(db, job_id, f"Invoking Retirement agent", "planner")
        result = await invoke_agent_with_boto3(agent_arn, session_id, payload)
        duration = (datetime.now() - start_ts).total_seconds()

        preview = (result or "").strip()
        if len(preview) > 300:
            preview = preview[:300] + "..."
        add_job_progress(db, job_id, f"Retirement completed in {duration:.1f}s", "planner")

        return f"Retirement agent completed: {result}"

    except Exception as e:
        db = Database()
        # Check if this is a MaxTokensReachedException
        if 'max_tokens' in str(e).lower() or 'maxtokensreachedException' in str(e) or e.__class__.__name__ == 'MaxTokensReachedException':
            add_job_progress(db, job_id, f"Retirement stopped: Reached maximum token limit", "planner")
            return f"Retirement agent stopped due to max tokens limit: {str(e)}"
        else:
            add_job_progress(db, job_id, f"Retirement failed: {str(e)}", "planner")
            return f"Retirement agent failed: {str(e)}"

print(f"✅ DEBUG: invoke_retirement_agent function defined")

@tool
async def invoke_tagger_agent(instruments: list) -> str:
    """
    Invoke the Tagger agent to classify financial instruments.
    
    Args:
        instruments: List of instruments to classify
        
    Returns:
        Classification result message
    """
    try:
        print(f"🔍 DEBUG: invoke_tagger_agent called with {len(instruments)} instruments")
        
        agent_arn = get_agent_arn("tagger")
        if not agent_arn:
            return "Error: Could not find Tagger agent ARN"

        session_id = f"planner-tagger-{int(datetime.now().timestamp())}"
        payload = {"instruments": instruments}

        start_ts = datetime.now()
        result = await invoke_agent_with_boto3(agent_arn, session_id, payload)
        duration = (datetime.now() - start_ts).total_seconds()

        preview = (result or "").strip()
        if len(preview) > 300:
            preview = preview[:300] + "..."

        return f"Tagger agent completed: {result}"

    except Exception as e:
        # Check if this is a MaxTokensReachedException
        if 'max_tokens' in str(e).lower() or 'maxtokensreachedException' in str(e) or e.__class__.__name__ == 'MaxTokensReachedException':
            return f"Tagger agent stopped due to max tokens limit: {str(e)}"
        else:
            return f"Tagger agent failed: {str(e)}"

print(f"✅ DEBUG: invoke_tagger_agent function defined")

print(f"🔍 DEBUG: About to define handle_missing_instruments function")

async def handle_missing_instruments(job_id: str, db: Database) -> None:
    """
    Check for and tag any instruments missing allocation data.
    This is done automatically before the agent runs.
    """
    # Get job and portfolio data
    job = db.jobs.find_by_id(job_id)
    if not job:
        return

    user_id = job["clerk_user_id"]
    accounts = db.accounts.find_by_user(user_id)

    missing = []
    for account in accounts:
        positions = db.positions.find_by_account(account["id"])

        for position in positions:
            symbol = position["symbol"]
            instrument = db.instruments.find_by_symbol(symbol)
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
        # Use the tagger tool to classify missing instruments
        tagger_result = await invoke_tagger_agent(missing)

print(f"✅ DEBUG: handle_missing_instruments function defined")

print(f"🔍 DEBUG: About to define create_agent_and_run function")

def create_agent_and_run(job_id: str) -> str:
    """
    Create and run the orchestrator agent for portfolio analysis coordination.
    
    Args:
        job_id: The portfolio analysis job ID
        
    Returns:
        Final orchestration result
    """
    try:
        db = Database()
        db.jobs.update_status(job_id, 'running')
        load_env_from_ssm()
      
        handle_missing_instruments(job_id, db)
        portfolio_summary = load_portfolio_summary(job_id, db)
      
        # Get model configuration and create model
        model_id = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-3-haiku-20240307-v1:0")
        print(f"🤖 DEBUG: Using Bedrock model_id={model_id} for job {job_id}")
        print(f"🔧 DEBUG: Creating BedrockModel instance for job {job_id}")
        model = BedrockModel(model_id=model_id)
        print(f"✅ DEBUG: BedrockModel created successfully for job {job_id}")

        # Deterministic kickoff: invoke core agents based on summary, independent of LLM tool-calling
        print(f"🎯 DEBUG: Starting deterministic kickoff of downstream agents for job {job_id}")
        try:
            # Always reporter if positions > 0
            if portfolio_summary.get('num_positions', 0) > 0:
                print(f"📊 DEBUG: Invoking Reporter agent (positions > 0) for job {job_id}")
                invoke_reporter_agent(job_id)
                print(f"✅ DEBUG: Reporter agent completed for job {job_id}")
            else:
                print(f"⏭️ DEBUG: Skipping Reporter agent (no positions) for job {job_id}")

            # Charter if at least 2 positions
            if portfolio_summary.get('num_positions', 0) >= 2:
                print(f"📋 DEBUG: Invoking Charter agent (positions >= 2) for job {job_id}")
                invoke_charter_agent(job_id)
                print(f"✅ DEBUG: Charter agent completed for job {job_id}")
            else:
                print(f"⏭️ DEBUG: Skipping Charter agent (positions < 2) for job {job_id}")

            # Retirement if years_until_retirement > 0
            if portfolio_summary.get('years_until_retirement', 0) > 0:
                print(f"🏖️ DEBUG: Invoking Retirement agent (years_until_retirement > 0) for job {job_id}")
                invoke_retirement_agent(job_id)
                print(f"✅ DEBUG: Retirement agent completed for job {job_id}")
            else:
                print(f"⏭️ DEBUG: Skipping Retirement agent (years_until_retirement <= 0) for job {job_id}")
                
            print(f"🎉 DEBUG: All deterministic agents completed for job {job_id}")
        except Exception as e:
            print(f"❌ DEBUG: Error during deterministic kickoff for job {job_id}: {e}")

        # Create the orchestrator agent instructions (still run LLM to summarize)
        instructions = f"""You are the Financial Planner Orchestrator. Your job is to coordinate portfolio analysis by calling specialized agents.

Portfolio Summary:
- Total positions: {portfolio_summary['num_positions']}
- Number of accounts: {portfolio_summary['num_accounts']}
- Years until retirement: {portfolio_summary['years_until_retirement']}
- Total portfolio value: ${portfolio_summary['total_value']:,.2f}

Your available tools:
1. invoke_reporter_agent: Generate comprehensive portfolio analysis narrative
2. invoke_charter_agent: Create portfolio visualization charts
3. invoke_retirement_agent: Calculate retirement projections and scenarios
4. invoke_tagger_agent: Classify financial instruments (usually done automatically)

Orchestration Steps:
1. Always call invoke_reporter_agent first if there are positions > 0
2. Call invoke_charter_agent if there are positions >= 2 (charts need multiple data points)
3. Call invoke_retirement_agent if retirement planning is needed (years_until_retirement > 0)
4. Coordinate the analysis and provide a final summary

Call each agent with the job_id: {job_id}

Begin the orchestration process now."""

        # Create agent
        agent = Agent(
            model=model,
            system_prompt=instructions,
            tools=[
                invoke_reporter_agent,
                invoke_charter_agent,
                invoke_retirement_agent,
                invoke_tagger_agent,
            ],
        )

    # Create task and run (optional summarization)
        task = f"Begin comprehensive portfolio analysis orchestration for job {job_id}"
        print(f"Planner: Starting agent orchestration run...")
        result = agent(task)
        print(f"Planner: Agent orchestration run completed")

        # Extract the text content from the AgentResult
        response = result.text if hasattr(result, 'text') else str(result)
        print(
            "Planner: Final orchestrator response (truncated): "
            f"'{(response or '')[:300]}{'...' if response and len(response)>300 else ''}'"
        )

        # Mark job as completed after all agents finish
        db.jobs.update_status(job_id, "completed")
        print(f"Planner: Job {job_id} completed successfully")

        return response

    except Exception as e:
        print(f"Error in orchestration: {e}")
        
        # Check if this is a MaxTokensReachedException
        if 'max_tokens' in str(e).lower() or 'maxtokensreachedException' in str(e) or e.__class__.__name__ == 'MaxTokensReachedException':
            print(f"❌ MaxTokensReachedException caught for job {job_id}: {e}")
            if 'db' in locals():
                db.jobs.update_status(job_id, 'max_tokens_exceeded', error_message=f'Agent reached max tokens limit: {str(e)}')
                add_job_progress(db, job_id, f"Analysis stopped: Agent reached maximum token limit. This happens when the portfolio is very large or complex.", "planner")
            
            # Return a graceful response instead of failing completely
            return f"Analysis partially completed but was stopped due to reaching maximum token limit. Please try running a more focused analysis or contact support for assistance with large portfolios."
        else:
            if 'db' in locals():
                db.jobs.update_status(job_id, 'failed', error_message=str(e))
            raise

print(f"✅ DEBUG: create_agent_and_run function defined")

print(f"🔍 DEBUG: About to instantiate BedrockAgentCoreApp()")

app = BedrockAgentCoreApp()

print(f"🔍 DEBUG: About to define @app.entrypoint function")

def create_basic_agent() -> Agent:
    """Create a basic agent with simple functionality"""
    system_prompt = """You are a helpful assistant. Answer questions clearly and concisely."""

    return Agent(
        system_prompt=system_prompt,
        name="BasicAgent"
    )


# @app.entrypoint
async def invokeme(payload=None):
    """Main entrypoint for the agent"""
    try:
        # Get the query from payload
        query = payload.get("prompt", "Hello, how are you?") if payload else "Hello, how are you?"

        # Create and use the agent
        agent = create_basic_agent()
        response = agent(query)

        return {
            "status": "success",
            "response": response.message['content'][0]['text']
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.entrypoint
async def planner_agent(payload):
    """Main entry point for the planner orchestrator agent."""
    try:
        print(f"🚀 DEBUG: planner_agent entry point called")
        print("new")
        # Parse the payload
        job_id = payload.get("job_id")
        if not job_id:
            print(f"❌ DEBUG: No job_id in payload")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'job_id is required'})
            }

        print(f"✅ DEBUG: Found job_id: {job_id}")
        print(f"🔄 About to call create_agent_and_run for job: {job_id}")

        print(f"🔍 DEBUG: About to await create_agent_and_run")
        # Process the orchestration in a single async context

        
        result = create_agent_and_run(job_id)
            

        print(f"✅ DEBUG: create_agent_and_run completed successfully")

        final_result = {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'message': f'Orchestration completed for job {job_id}',
                'final_output': result
            })
        }
        
        print(f"🎉 DEBUG: Returning success result")
        return final_result

    except Exception as e:
        print(f"❌ DEBUG: Exception in planner_agent: {e}")
        
        # Check if this is a MaxTokensReachedException
        if 'max_tokens' in str(e).lower() or 'maxtokensreachedException' in str(e) or e.__class__.__name__ == 'MaxTokensReachedException':
            return {
                'statusCode': 200,  # Return success with explanation
                'body': json.dumps({
                    'success': False,
                    'max_tokens_exceeded': True,
                    'message': f'Analysis stopped due to maximum token limit reached for job {payload.get("job_id", "unknown")}',
                    'error': str(e),
                    'recommendation': 'Try reducing the complexity of your portfolio or contact support for assistance with large portfolios.'
                })
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': str(e)})
            }

print(f"🔍 DEBUG: About to check if __name__ == '__main__'")

if __name__ == "__main__":
    print(f"✅ DEBUG: Agent module loaded successfully, ready for AgentCore invocation")
    app.run()
    print(f"🔍  app.run() completed ")
