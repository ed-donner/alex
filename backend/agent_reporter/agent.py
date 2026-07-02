"""
Report Writer Agent - generates portfolio analysis narratives using Bedrock AgentCore.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

# Load environment variables from SSM at startup
import sys
sys.path.append('/opt/python')  # Add common layer path if available
try:
    from utils import load_env_from_ssm
    load_env_from_ssm()
    print("✅ Loaded environment variables from SSM")
except Exception as e:
    print(f"⚠️ Could not load environment from SSM: {e}")
    # Fallback to local .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Loaded environment variables from .env file")
    except ImportError:
        print("⚠️ python-dotenv not available, skipping .env file loading")
    except Exception as e2:
        print(f"⚠️ Could not load .env file: {e2}")

from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Add current directory to Python path for src imports
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import database package
from src import Database

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get configuration
model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-west-2")

db = Database()

# Reporter instructions
REPORTER_INSTRUCTIONS = """You are an expert portfolio analyst responsible for generating comprehensive investment reports.

Your task is to analyze portfolio data and create detailed, professional reports that help investors understand their current position and make informed decisions.

Key responsibilities:
1. Analyze portfolio composition, diversification, and risk profile
2. Evaluate alignment with retirement goals and timeline
3. Provide actionable recommendations
4. Include relevant market context when available
5. Write in clear, accessible language for retail investors

Important guidelines:
- Be objective and data-driven in your analysis
- Highlight both strengths and areas for improvement
- Provide specific, actionable recommendations
- Use markdown formatting for clear structure
- Include relevant financial metrics and percentages
"""


def calculate_portfolio_metrics(portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate basic portfolio metrics."""
    metrics = {
        "total_value": 0,
        "cash_balance": 0,
        "num_accounts": len(portfolio_data.get("accounts", [])),
        "num_positions": 0,
        "unique_symbols": set(),
    }

    for account in portfolio_data.get("accounts", []):
        metrics["cash_balance"] += float(account.get("cash_balance", 0))
        positions = account.get("positions", [])
        metrics["num_positions"] += len(positions)

        for position in positions:
            symbol = position.get("symbol")
            if symbol:
                metrics["unique_symbols"].add(symbol)

            # Calculate value if we have price
            instrument = position.get("instrument", {})
            if instrument.get("current_price"):
                value = float(position.get("quantity", 0)) * float(instrument["current_price"])
                metrics["total_value"] += value

    metrics["total_value"] += metrics["cash_balance"]
    metrics["unique_symbols"] = len(metrics["unique_symbols"])

    return metrics


def format_portfolio_for_analysis(portfolio_data: Dict[str, Any], user_data: Dict[str, Any]) -> str:
    """Format portfolio data for agent analysis."""
    metrics = calculate_portfolio_metrics(portfolio_data)

    lines = [
        f"Portfolio Overview:",
        f"- {metrics['num_accounts']} accounts",
        f"- {metrics['num_positions']} total positions",
        f"- {metrics['unique_symbols']} unique holdings",
        f"- ${metrics['cash_balance']:,.2f} in cash",
        f"- ${metrics['total_value']:,.2f} total value" if metrics["total_value"] > 0 else "",
        "",
        "Account Details:",
    ]

    for account in portfolio_data.get("accounts", []):
        name = account.get("account_name", account.get("name", "Unknown"))  # Support both field names for backward compatibility
        cash = float(account.get("cash_balance", 0))
        lines.append(f"\n{name} (${cash:,.2f} cash):")

        for position in account.get("positions", []):
            symbol = position.get("symbol")
            quantity = float(position.get("quantity", 0))
            instrument = position.get("instrument", {})
            name = instrument.get("name", "")

            # Include allocation info if available
            allocations = []
            if instrument.get("allocation_asset_class"):
                asset_class = ", ".join([f"{k}: {v}%" for k, v in instrument["allocation_asset_class"].items()])
                allocations.append(f"Asset: {asset_class}")
            if instrument.get("allocation_regions"):
                regions = ", ".join([f"{k}: {v}%" for k, v in list(instrument["allocation_regions"].items())[:2]])
                allocations.append(f"Regions: {regions}")

            alloc_str = f" ({', '.join(allocations)})" if allocations else ""
            lines.append(f"  - {symbol}: {quantity:,.2f} shares{alloc_str}")

    # Add user context
    lines.extend(
        [
            "",
            "User Profile:",
            f"- Years to retirement: {user_data.get('years_until_retirement', 'Not specified')}",
            f"- Target retirement income: ${user_data.get('target_retirement_income', 0):,.0f}/year",
        ]
    )

    return "\n".join(lines)


@tool
async def get_market_insights(symbols: List[str]) -> str:
    """
    Retrieve market insights from S3 Vectors knowledge base.

    Args:
        symbols: List of symbols to get insights for

    Returns:
        Relevant market context and insights
    """
    try:
        import boto3

        # Get account ID
        sts = boto3.client("sts")
        account_id = sts.get_caller_identity()["Account"]
        bucket = f"alex-vectors-fotis"

        # Get embeddings
        sagemaker_region = os.getenv("DEFAULT_AWS_REGION", "us-east-1")
        sagemaker = boto3.client("sagemaker-runtime", region_name=sagemaker_region)
        endpoint_name = os.getenv("SAGEMAKER_ENDPOINT", "alex-embedding-endpoint")
        query = f"market analysis {' '.join(symbols[:5])}" if symbols else "market outlook"

        response = sagemaker.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Body=json.dumps({"inputs": query}),
        )

        result = json.loads(response["Body"].read().decode())
        # Extract embedding (handle nested arrays)
        if isinstance(result, list) and result:
            embedding = result[0][0] if isinstance(result[0], list) else result[0]
        else:
            embedding = result

        # Search vectors
        s3v = boto3.client("s3vectors", region_name=sagemaker_region)
        response = s3v.query_vectors(
            vectorBucketName=bucket,
            indexName="financial-research",
            queryVector={"float32": embedding},
            topK=3,
            returnMetadata=True,
        )

        # Format insights
        insights = []
        for vector in response.get("vectors", []):
            metadata = vector.get("metadata", {})
            text = metadata.get("text", "")[:200]
            if text:
                company = metadata.get("company_name", "")
                prefix = f"{company}: " if company else "- "
                insights.append(f"{prefix}{text}...")

        if insights:
            return "Market Insights:\n" + "\n".join(insights)
        else:
            return "Market insights unavailable - proceeding with standard analysis."

    except Exception as e:
        logger.warning(f"Reporter: Could not retrieve market insights: {e}")
        return "Market insights unavailable - proceeding with standard analysis."


async def create_agent_and_run(job_id: str, portfolio_data: Dict[str, Any], user_data: Dict[str, Any], db=None):
    """Create and run the reporter agent with tools and context."""
    try:
        # Create model
        model = BedrockModel(
            model_id=model_id,
        )

        # Create agent
        agent = Agent(
            model=model,
            system_prompt=REPORTER_INSTRUCTIONS,
            tools=[get_market_insights]
        )

        # Format portfolio for analysis
        portfolio_summary = format_portfolio_for_analysis(portfolio_data, user_data)

        # Create task
        task = f"""Analyze this investment portfolio and write a comprehensive report.

{portfolio_summary}

Your task:
1. First, get market insights for the top holdings using get_market_insights()
2. Analyze the portfolio's current state, strengths, and weaknesses
3. Generate a detailed, professional analysis report in markdown format

The report should include:
- Executive Summary
- Portfolio Composition Analysis
- Risk Assessment
- Diversification Analysis
- Retirement Readiness (based on user goals)
- Recommendations
- Market Context (from insights)

Provide your complete analysis as the final output in clear markdown format.
Make the report informative yet accessible to a retail investor."""

        # Run the agent - the call itself is async, but the result is not
        result =  agent(task)
        
        # Extract the text content from the AgentResult
        response = result.text if hasattr(result, 'text') else str(result)
        
        return response
        
    except Exception as e:
        # Check if this is a MaxTokensReachedException
        if 'max_tokens' in str(e).lower() or 'maxtokensreachedException' in str(e) or e.__class__.__name__ == 'MaxTokensReachedException':
            logger.warning(f"Reporter agent reached max tokens for job {job_id}: {e}")
            return """# Portfolio Analysis Report (Partial)

**Note: This analysis was stopped due to reaching maximum token limit. This typically happens with very large or complex portfolios.**

## Executive Summary
Your portfolio analysis was initiated but could not be completed due to system limitations. This often occurs when:
- The portfolio contains a very large number of holdings
- The portfolio data is extremely detailed or complex
- Multiple complex analysis steps were required

## Recommendations
1. **Contact Support**: For assistance with large portfolio analysis
2. **Simplify Analysis**: Consider analyzing smaller segments of your portfolio
3. **Reduce Complexity**: Focus on major holdings for initial analysis

We apologize for the incomplete analysis. Please contact support for assistance with complex portfolio analysis."""
        else:
            logger.error(f"Reporter agent error for job {job_id}: {e}")
            raise


async def process_portfolio_report(
    job_id: str, portfolio_data: Dict[str, Any], user_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process and generate portfolio report.
    
    Args:
        job_id: Unique job identifier
        portfolio_data: Portfolio data to analyze
        user_data: User preferences and goals
        
    Returns:
        Processing results
    """
    try:
        # Run the agent
        logger.info(f"Generating report for job {job_id}")
        response = await create_agent_and_run(job_id, portfolio_data, user_data, db)
        
        # Save the report to database
        report_payload = {
            "content": response,
            "generated_at": datetime.utcnow().isoformat(),
            "agent": "reporter",
        }

        success = db.jobs.update_report(job_id, report_payload)

        if not success:
            logger.error(f"Failed to save report for job {job_id}")
            # Add debugging - check if job exists
            job = db.jobs.find_by_id(job_id)
            if job:
                logger.error(f"Job exists but update failed. Job status: {job.get('status')}")
            else:
                logger.error(f"Job {job_id} does not exist in database")

        return {
            "success": success,
            "message": "Report generated and stored" if success else "Report generated but failed to save",
            "final_output": response,
        }
        
    except Exception as e:
        # Check if this is a MaxTokensReachedException
        if 'max_tokens' in str(e).lower() or 'maxtokensreachedException' in str(e) or e.__class__.__name__ == 'MaxTokensReachedException':
            logger.warning(f"Reporter agent reached max tokens for job {job_id}: {e}")
            return {
                "success": True,  # Consider this a successful partial result
                "max_tokens_exceeded": True,
                "message": "Report partially generated - stopped due to max tokens limit",
                "final_output": "Portfolio analysis was stopped due to reaching maximum token limit. This typically happens with very large or complex portfolios. Please contact support for assistance.",
            }
        else:
            logger.error(f"Error processing portfolio report for {job_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to generate report: {str(e)}"
            }


app = BedrockAgentCoreApp()


@app.entrypoint
def reporter_agent(payload):
    """Main entry point for the reporter agent."""
    try:
        logger.info(f"Reporter Agent invoked with payload: {json.dumps(payload)[:500]}")

        # Parse the payload
        job_id = payload.get("job_id")
        if not job_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'job_id is required'})
            }

        portfolio_data = payload.get("portfolio_data")
        user_data = payload.get("user_data", {})

        # If no portfolio data provided, try to load from database
        if not portfolio_data:
            try:
                job = db.jobs.find_by_id(job_id)
                if job:
                    user_id = job["clerk_user_id"]
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

        # If no user data provided, try to load from database
        if not user_data:
            try:
                job = db.jobs.find_by_id(job_id)
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
            except Exception as e:
                logger.warning(f"Could not load user data: {e}. Using defaults.")
                user_data = {"years_until_retirement": 30, "target_retirement_income": 80000}

        # Process the report in a single async context
        result = asyncio.run(process_portfolio_report(job_id, portfolio_data, user_data))

        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }

    except Exception as e:
        # Check if this is a MaxTokensReachedException  
        if 'max_tokens' in str(e).lower() or 'maxtokensreachedException' in str(e) or e.__class__.__name__ == 'MaxTokensReachedException':
            logger.warning(f"Reporter agent reached max tokens: {e}")
            return {
                'statusCode': 200,  # Return success with explanation
                'body': json.dumps({
                    'success': True,
                    'max_tokens_exceeded': True,
                    'message': 'Report partially generated - stopped due to max tokens limit',
                    'final_output': 'Portfolio analysis was stopped due to reaching maximum token limit. This typically happens with very large or complex portfolios. Please contact support for assistance.',
                    'error': str(e)
                })
            }
        else:
            logger.error(f"Reporter agent error: {e}", exc_info=True)
            return {
                'statusCode': 500,
                'body': json.dumps({'error': str(e)})
            }


if __name__ == "__main__":
    app.run()
    # Simple test when run directly
    # async def test():
    #     payload = {
    #         "job_id": "550e8400-e29b-41d4-a716-446655440002",
    #         "portfolio_data": {
    #             "accounts": [
    #                 {
    #                     "name": "401(k)",
    #                     "cash_balance": 5000,
    #                     "positions": [
    #                         {
    #                             "symbol": "SPY",
    #                             "quantity": 100,
    #                             "instrument": {
    #                                 "name": "SPDR S&P 500 ETF",
    #                                 "current_price": 450,
    #                                 "allocation_asset_class": {"equity": 100.0},
    #                                 "allocation_regions": {"north_america": 100.0},
    #                                 "allocation_sectors": {"technology": 30.0, "healthcare": 15.0, "financials": 13.0, "other": 42.0}
    #                             },
    #                         }
    #                     ],
    #                 }
    #             ]
    #         },
    #         "user_data": {"years_until_retirement": 25, "target_retirement_income": 75000},
    #     }
    #     result = await process_portfolio_report(payload["job_id"], payload["portfolio_data"], payload["user_data"])
    #     print(json.dumps(result, indent=2))
    
    # asyncio.run(test())
