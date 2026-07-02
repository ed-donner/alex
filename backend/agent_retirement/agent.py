"""
Retirement Specialist Agent - provides retirement planning analysis and projections using Bedrock AgentCore.
"""

import os
import json
import logging
import asyncio
import random
from typing import Dict, Any
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

from strands import Agent
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Add current directory to Python path for src imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))

# Import database package
from src import Database

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get configuration
model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-west-2")

db = Database()

# Retirement instructions
RETIREMENT_INSTRUCTIONS = """You are a retirement planning specialist with expertise in portfolio analysis, Monte Carlo simulations, and retirement readiness assessments.

Your task is to analyze portfolio data and user retirement goals to provide comprehensive retirement planning analysis and actionable recommendations.

Key responsibilities:
1. Assess current retirement readiness based on portfolio value and goals
2. Analyze Monte Carlo simulation results to provide probability-based insights
3. Evaluate asset allocation for retirement timeline appropriateness
4. Provide specific, actionable recommendations to improve retirement outcomes
5. Address key risks like sequence of returns, inflation, and longevity

Important guidelines:
- Use specific numbers and percentages in your analysis
- Provide clear success/failure probabilities based on simulations
- Give actionable recommendations with timelines
- Address risk mitigation strategies
- Use markdown formatting for clear structure
- Be realistic about retirement challenges while remaining constructive
"""

def get_user_preferences(job_id: str) -> Dict[str, Any]:
    """Load user preferences from database."""
    try:
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

def calculate_portfolio_value(portfolio_data: Dict[str, Any]) -> float:
    """Calculate current portfolio value."""
    total_value = 0.0

    for account in portfolio_data.get("accounts", []):
        cash = float(account.get("cash_balance", 0))
        total_value += cash

        for position in account.get("positions", []):
            quantity = float(position.get("quantity", 0))
            instrument = position.get("instrument", {})
            price = float(instrument.get("current_price", 100))
            total_value += quantity * price

    return total_value

def calculate_asset_allocation(portfolio_data: Dict[str, Any]) -> Dict[str, float]:
    """Calculate asset allocation percentages."""
    total_equity = 0.0
    total_bonds = 0.0
    total_real_estate = 0.0
    total_commodities = 0.0
    total_cash = 0.0
    total_value = 0.0

    for account in portfolio_data.get("accounts", []):
        cash = float(account.get("cash_balance", 0))
        total_cash += cash
        total_value += cash

        for position in account.get("positions", []):
            quantity = float(position.get("quantity", 0))
            instrument = position.get("instrument", {})
            price = float(instrument.get("current_price", 100))
            value = quantity * price
            total_value += value

            # Get asset class allocation
            asset_allocation = instrument.get("allocation_asset_class", {})
            if asset_allocation:
                total_equity += value * asset_allocation.get("equity", 0) / 100
                total_bonds += value * asset_allocation.get("fixed_income", 0) / 100
                total_real_estate += value * asset_allocation.get("real_estate", 0) / 100
                total_commodities += value * asset_allocation.get("commodities", 0) / 100

    if total_value == 0:
        return {"equity": 0, "bonds": 0, "real_estate": 0, "commodities": 0, "cash": 0}

    return {
        "equity": total_equity / total_value,
        "bonds": total_bonds / total_value,
        "real_estate": total_real_estate / total_value,
        "commodities": total_commodities / total_value,
        "cash": total_cash / total_value,
    }

def run_monte_carlo_simulation(
    current_value: float,
    years_until_retirement: int,
    target_annual_income: float,
    asset_allocation: Dict[str, float],
    num_simulations: int = 500,
) -> Dict[str, Any]:
    """Run Monte Carlo simulation for retirement planning."""

    # Historical return parameters (annualized)
    equity_return_mean = 0.07
    equity_return_std = 0.18
    bond_return_mean = 0.04
    bond_return_std = 0.05
    real_estate_return_mean = 0.06
    real_estate_return_std = 0.12

    successful_scenarios = 0
    final_values = []
    years_lasted = []

    for _ in range(num_simulations):
        portfolio_value = current_value

        # Accumulation phase
        for _ in range(years_until_retirement):
            equity_return = random.gauss(equity_return_mean, equity_return_std)
            bond_return = random.gauss(bond_return_mean, bond_return_std)
            real_estate_return = random.gauss(real_estate_return_mean, real_estate_return_std)

            portfolio_return = (
                asset_allocation["equity"] * equity_return
                + asset_allocation["bonds"] * bond_return
                + asset_allocation["real_estate"] * real_estate_return
                + asset_allocation["cash"] * 0.02
            )

            portfolio_value = portfolio_value * (1 + portfolio_return)
            portfolio_value += 10000  # Annual contribution

        # Retirement phase
        retirement_years = 30
        annual_withdrawal = target_annual_income
        years_income_lasted = 0

        for year in range(retirement_years):
            if portfolio_value <= 0:
                break

            # Inflation adjustment (3% per year)
            annual_withdrawal *= 1.03

            equity_return = random.gauss(equity_return_mean, equity_return_std)
            bond_return = random.gauss(bond_return_mean, bond_return_std)
            real_estate_return = random.gauss(real_estate_return_mean, real_estate_return_std)

            portfolio_return = (
                asset_allocation["equity"] * equity_return
                + asset_allocation["bonds"] * bond_return
                + asset_allocation["real_estate"] * real_estate_return
                + asset_allocation["cash"] * 0.02
            )

            portfolio_value = portfolio_value * (1 + portfolio_return) - annual_withdrawal

            if portfolio_value > 0:
                years_income_lasted += 1

        final_values.append(max(0, portfolio_value))
        years_lasted.append(years_income_lasted)

        if years_income_lasted >= retirement_years:
            successful_scenarios += 1

    # Calculate statistics
    final_values.sort()
    success_rate = (successful_scenarios / num_simulations) * 100

    # Calculate expected value at retirement
    expected_return = (
        asset_allocation["equity"] * equity_return_mean
        + asset_allocation["bonds"] * bond_return_mean
        + asset_allocation["real_estate"] * real_estate_return_mean
        + asset_allocation["cash"] * 0.02
    )
    expected_value_at_retirement = current_value
    for _ in range(years_until_retirement):
        expected_value_at_retirement *= 1 + expected_return
        expected_value_at_retirement += 10000

    return {
        "success_rate": round(success_rate, 1),
        "median_final_value": round(final_values[num_simulations // 2], 2),
        "percentile_10": round(final_values[num_simulations // 10], 2),
        "percentile_90": round(final_values[9 * num_simulations // 10], 2),
        "average_years_lasted": round(sum(years_lasted) / len(years_lasted), 1),
        "expected_value_at_retirement": round(expected_value_at_retirement, 2),
    }

def generate_projections(
    current_value: float,
    years_until_retirement: int,
    asset_allocation: Dict[str, float],
    current_age: int,
) -> list:
    """Generate simplified retirement projections."""

    # Expected returns
    expected_return = (
        asset_allocation["equity"] * 0.07
        + asset_allocation["bonds"] * 0.04
        + asset_allocation["real_estate"] * 0.06
        + asset_allocation["cash"] * 0.02
    )

    projections = []
    portfolio_value = current_value

    # Only show key milestones (every 5 years)
    milestone_years = list(range(0, years_until_retirement + 31, 5))

    for year in milestone_years:
        age = current_age + year

        if year <= years_until_retirement:
            # Calculate accumulation
            for _ in range(min(5, year)):
                portfolio_value *= 1 + expected_return
                portfolio_value += 10000
            phase = "accumulation"
            annual_income = 0
        else:
            # Calculate retirement withdrawals
            withdrawal_rate = 0.04
            annual_income = portfolio_value * withdrawal_rate
            years_in_retirement = min(5, year - years_until_retirement)
            for _ in range(years_in_retirement):
                portfolio_value = portfolio_value * (1 + expected_return) - annual_income
            phase = "retirement"

        if portfolio_value > 0:
            projections.append(
                {
                    "year": year,
                    "age": age,
                    "portfolio_value": round(portfolio_value, 2),
                    "annual_income": round(annual_income, 2),
                    "phase": phase,
                }
            )

    return projections

async def create_agent_and_run(job_id: str, portfolio_data: Dict[str, Any]) -> str:
    """Create and run the retirement agent."""

    # Get user preferences
    user_preferences = get_user_preferences(job_id)
    
    # Create model
    model = BedrockModel(
        model_id=model_id,
    )

    # Create agent (no tools needed)
    agent = Agent(
        model=model,
        system_prompt=RETIREMENT_INSTRUCTIONS
    )

    # Extract user preferences
    years_until_retirement = user_preferences.get("years_until_retirement", 30)
    target_income = user_preferences.get("target_retirement_income", 80000)
    current_age = user_preferences.get("current_age", 40)

    # Calculate portfolio metrics
    portfolio_value = calculate_portfolio_value(portfolio_data)
    allocation = calculate_asset_allocation(portfolio_data)

    # Run Monte Carlo simulation
    monte_carlo = run_monte_carlo_simulation(
        portfolio_value, years_until_retirement, target_income, allocation, num_simulations=500
    )

    # Generate projections
    projections = generate_projections(
        portfolio_value, years_until_retirement, allocation, current_age
    )

    # Format comprehensive context for the agent
    task = f"""
# Portfolio Analysis Context

## Current Situation
- Portfolio Value: ${portfolio_value:,.0f}
- Asset Allocation: {", ".join([f"{k.title()}: {v:.0%}" for k, v in allocation.items() if v > 0])}
- Years to Retirement: {years_until_retirement}
- Target Annual Income: ${target_income:,.0f}
- Current Age: {current_age}

## Monte Carlo Simulation Results (500 scenarios)
- Success Rate: {monte_carlo["success_rate"]}% (probability of sustaining retirement income for 30 years)
- Expected Portfolio Value at Retirement: ${monte_carlo["expected_value_at_retirement"]:,.0f}
- 10th Percentile Outcome: ${monte_carlo["percentile_10"]:,.0f} (worst case)
- Median Final Value: ${monte_carlo["median_final_value"]:,.0f}
- 90th Percentile Outcome: ${monte_carlo["percentile_90"]:,.0f} (best case)
- Average Years Portfolio Lasts: {monte_carlo["average_years_lasted"]} years

## Key Projections (Milestones)
"""

    for proj in projections[:6]:
        if proj["phase"] == "accumulation":
            task += f"- Age {proj['age']}: ${proj['portfolio_value']:,.0f} (building wealth)\n"
        else:
            task += f"- Age {proj['age']}: ${proj['portfolio_value']:,.0f} (annual income: ${proj['annual_income']:,.0f})\n"

    task += f"""

## Risk Factors to Consider
- Sequence of returns risk (poor returns early in retirement)
- Inflation impact (3% assumed)
- Healthcare costs in retirement
- Longevity risk (living beyond 30 years)
- Market volatility (equity standard deviation: 18%)

## Safe Withdrawal Rate Analysis
- 4% Rule: ${portfolio_value * 0.04:,.0f} initial annual income
- Target Income: ${target_income:,.0f}
- Gap: ${target_income - (portfolio_value * 0.04):,.0f}

Your task: Analyze this retirement readiness data and provide a comprehensive retirement analysis including:
1. Clear assessment of retirement readiness
2. Specific recommendations to improve success rate
3. Risk mitigation strategies
4. Action items with timeline

Provide your analysis in clear markdown format with specific numbers and actionable recommendations.
"""

    # Run the agent
    result = agent(task)
    
    # Extract the text content from the AgentResult
    response = result.text if hasattr(result, 'text') else str(result)
    
    return response

async def process_retirement_analysis(job_id: str, portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process and generate retirement analysis.
    
    Args:
        job_id: Unique job identifier
        portfolio_data: Portfolio data to analyze
        
    Returns:
        Processing results
    """
    try:
        # Run the agent
        logger.info(f"Generating retirement analysis for job {job_id}")
        response = await create_agent_and_run(job_id, portfolio_data)
        
        # Save the analysis to database
        retirement_payload = {
            'analysis': response,
            'generated_at': datetime.utcnow().isoformat(),
            'agent': 'retirement'
        }
        
        success = db.jobs.update_retirement(job_id, retirement_payload)
        
        if not success:
            logger.error(f"Failed to save retirement analysis for job {job_id}")
            # Add debugging - check if job exists
            job = db.jobs.find_by_id(job_id)
            if job:
                logger.error(f"Job exists but update failed. Job status: {job.get('status')}")
            else:
                logger.error(f"Job {job_id} does not exist in database")
        
        return {
            'success': success,
            'message': 'Retirement analysis completed' if success else 'Analysis completed but failed to save',
            'final_output': response
        }
        
    except Exception as e:
        logger.error(f"Error processing retirement analysis for {job_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'message': f"Failed to generate retirement analysis: {str(e)}"
        }

app = BedrockAgentCoreApp()

@app.entrypoint
def retirement_agent(payload):
    """Main entry point for the retirement agent."""
    try:
        logger.info(f"Retirement Agent invoked with payload: {json.dumps(payload)[:500]}")

        # Parse the payload
        job_id = payload.get("job_id")
        if not job_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'job_id is required'})
            }

        portfolio_data = payload.get("portfolio_data")

        # If no portfolio data provided, try to load from database
        if not portfolio_data:
            try:
                job = db.jobs.find_by_id(job_id)
                if job:
                    portfolio_data = job.get('request_payload', {}).get('portfolio_data', {})
                else:
                    return {
                        'statusCode': 404,
                        'body': json.dumps({'error': f'Job {job_id} not found'})
                    }
            except Exception as e:
                logger.error(f"Could not load portfolio from database: {e}")
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'No portfolio data provided'})
                }

        # Process the retirement analysis in a single async context
        result = asyncio.run(process_retirement_analysis(job_id, portfolio_data))

        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }

    except Exception as e:
        logger.error(f"Retirement agent error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

if __name__ == "__main__":
    app.run()
    # Simple test when run directly
    # async def test():
    #     payload = {
    #         "job_id": "test-retirement-123",
    #         "portfolio_data": {
    #             "accounts": [
    #                 {
    #                     "name": "401(k)",
    #                     "type": "retirement",
    #                     "cash_balance": 10000,
    #                     "positions": [
    #                         {
    #                             "symbol": "SPY",
    #                             "quantity": 100,
    #                             "instrument": {
    #                                 "name": "SPDR S&P 500 ETF",
    #                                 "current_price": 450,
    #                                 "allocation_asset_class": {"equity": 100}
    #                             }
    #                         }
    #                     ]
    #                 }
    #             ]
    #         }
    #     }
    #     result = await process_retirement_analysis(payload["job_id"], payload["portfolio_data"])
    #     print(json.dumps(result, indent=2))
    
    # asyncio.run(test())
