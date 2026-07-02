"""
Chart Maker Agent using Bedrock AgentCore.

This agent analyzes portfolio data and generates visualization charts in JSON format.
"""

import json
import logging
import os
import uuid
from typing import Dict, Any, List

from utils import load_env_from_ssm

# Load environment variables from SSM at startup
import sys
sys.path.append('/opt/python')  # Add common layer path if available


load_env_from_ssm()
print("✅ Loaded environment variables from SSM")

from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

logger = logging.getLogger(__name__)

def analyze_portfolio(portfolio_data: Dict[str, Any]) -> str:
    """
    Analyze the portfolio to understand its composition and calculate key metrics.
    Returns detailed breakdown of positions, accounts, and calculated allocations.
    """
    result = []
    total_value = 0.0
    position_values = {}
    account_totals = {}

    # Calculate position values and totals
    for account in portfolio_data.get("accounts", []):
        account_name = account.get("account_name", account.get("name", "Unknown"))  # Support both field names for backward compatibility
        account_type = account.get("type", "unknown")
        # Handle None or missing cash_balance
        cash_balance = account.get("cash_balance")
        if cash_balance is None or cash_balance == "":
            cash = 0.0
        else:
            cash = float(cash_balance)

        if account_name not in account_totals:
            account_totals[account_name] = {"value": 0, "type": account_type, "positions": []}

        account_totals[account_name]["value"] += cash
        total_value += cash

        for position in account.get("positions", []):
            symbol = position.get("symbol")
            quantity = float(position.get("quantity", 0))
            instrument = position.get("instrument", {})
            # Handle None or missing current_price
            current_price = instrument.get("current_price")
            if current_price is None or current_price == "":
                price = 1.0  # Default price if not available
                logger.warning(f"Charter: No price for {symbol}, using default of 1.0")
            else:
                price = float(current_price)
            value = quantity * price

            position_values[symbol] = position_values.get(symbol, 0) + value
            account_totals[account_name]["value"] += value
            account_totals[account_name]["positions"].append(
                {"symbol": symbol, "value": value, "instrument": instrument}
            )
            total_value += value

    # Build analysis summary
    result.append("Portfolio Analysis:")
    result.append(f"Total Value: ${total_value:,.2f}")
    result.append(f"Number of Accounts: {len(account_totals)}")
    result.append(f"Number of Positions: {len(position_values)}")

    result.append("\nAccount Breakdown:")
    for name, data in account_totals.items():
        pct = (data["value"] / total_value * 100) if total_value > 0 else 0
        result.append(f"  {name} ({data['type']}): ${data['value']:,.2f} ({pct:.1f}%)")

    result.append("\nTop Holdings by Value:")
    sorted_positions = sorted(position_values.items(), key=lambda x: x[1], reverse=True)[:10]
    for symbol, value in sorted_positions:
        pct = (value / total_value * 100) if total_value > 0 else 0
        result.append(f"  {symbol}: ${value:,.2f} ({pct:.1f}%)")

    # Calculate aggregated allocations for the agent
    result.append("\nCalculated Allocations:")
    
    # Asset class aggregation
    asset_classes = {}
    regions = {}
    sectors = {}
    
    for account in portfolio_data.get("accounts", []):
        for position in account.get("positions", []):
            symbol = position.get("symbol")
            quantity = float(position.get("quantity", 0))
            instrument = position.get("instrument", {})
            # Handle None or missing current_price
            current_price = instrument.get("current_price")
            if current_price is None or current_price == "":
                price = 1.0  # Default price if not available
            else:
                price = float(current_price)
            value = quantity * price
            
            # Aggregate asset classes
            for asset_class, pct in instrument.get("allocation_asset_class", {}).items():
                asset_value = value * (pct / 100)
                asset_classes[asset_class] = asset_classes.get(asset_class, 0) + asset_value
            
            # Aggregate regions
            for region, pct in instrument.get("allocation_regions", {}).items():
                region_value = value * (pct / 100)
                regions[region] = regions.get(region, 0) + region_value
            
            # Aggregate sectors
            for sector, pct in instrument.get("allocation_sectors", {}).items():
                sector_value = value * (pct / 100)
                sectors[sector] = sectors.get(sector, 0) + sector_value
    
    # Add cash to asset classes
    total_cash = sum(
        float(acc.get("cash_balance")) if acc.get("cash_balance") is not None else 0
        for acc in portfolio_data.get("accounts", [])
    )
    if total_cash > 0:
        asset_classes["cash"] = asset_classes.get("cash", 0) + total_cash
    
    result.append("\nAsset Classes:")
    for asset_class, value in sorted(asset_classes.items(), key=lambda x: x[1], reverse=True):
        result.append(f"  {asset_class}: ${value:,.2f}")
    
    result.append("\nGeographic Regions:")
    for region, value in sorted(regions.items(), key=lambda x: x[1], reverse=True):
        result.append(f"  {region}: ${value:,.2f}")
    
    result.append("\nSectors:")
    for sector, value in sorted(sectors.items(), key=lambda x: x[1], reverse=True)[:10]:
        result.append(f"  {sector}: ${value:,.2f}")

    return "\n".join(result)

def create_charter_task(portfolio_analysis: str, portfolio_data: dict) -> str:
    """Generate the task prompt for the Charter agent."""
    return f"""Analyze this investment portfolio and create 4-6 visualization charts.

{portfolio_analysis}

Create charts based on this portfolio data. Calculate aggregated values from the positions shown above.

OUTPUT ONLY THE JSON OBJECT with 4-6 charts - no other text."""

CHARTER_INSTRUCTIONS = """You are a Chart Maker Agent that creates visualization data for investment portfolios.

Your task is to analyze the portfolio and output a JSON object containing 4-6 charts that tell a compelling story about the portfolio.

You must output ONLY valid JSON in the exact format shown below. Do not include any text before or after the JSON.

REQUIRED JSON FORMAT:
{
  "charts": [
    {
      "key": "asset_class_distribution",
      "title": "Asset Class Distribution",
      "type": "pie",
      "description": "Shows the distribution of asset classes in the portfolio",
      "data": [
        {"name": "Equity", "value": 146365.00, "color": "#3B82F6"},
        {"name": "Fixed Income", "value": 29000.00, "color": "#10B981"},
        {"name": "Real Estate", "value": 14500.00, "color": "#F59E0B"},
        {"name": "Cash", "value": 5000.00, "color": "#EF4444"}
      ]
    }
  ]
}

IMPORTANT RULES:
1. Output ONLY the JSON object, nothing else
2. Each chart must have: key, title, type, description, and data array
3. Chart types: 'pie', 'bar', 'donut', or 'horizontalBar'
4. Values must be dollar amounts (not percentages - Recharts calculates those)
5. Colors must be hex format like '#3B82F6'
6. Create 4-6 different charts from different perspectives

CHART IDEAS TO IMPLEMENT:
- Asset class distribution (equity vs bonds vs alternatives)
- Geographic exposure (North America, Europe, Asia, etc.)
- Sector breakdown (Technology, Healthcare, Financials, etc.)
- Account type allocation (401k, IRA, Taxable, etc.)
- Top holdings concentration (largest 5-10 positions)
- Tax efficiency (tax-advantaged vs taxable accounts)

Remember: Output ONLY the JSON object. No explanations, no text before or after."""

def create_agent_and_run(job_id: str, portfolio_data: Dict[str, Any], user_id: str = None) -> str:
    """
    Create and run the charter agent to generate visualization charts.
    
    Args:
        job_id: Job identifier
        portfolio_data: Portfolio information
        user_id: User identifier (optional)
        
    Returns:
        JSON string with chart data
    """
    logger.info(f"Charter Agent: Starting analysis for job {job_id}")
    
    # Initialize model
    model_id = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")
    region = os.getenv("BEDROCK_REGION", "us-west-2")
    
    logger.info(f"Charter Agent: Using model {model_id} in region {region}")
    
    model = BedrockModel(
        model_id=model_id
    )
    
    # Analyze portfolio
    portfolio_analysis = analyze_portfolio(portfolio_data)
    logger.info(f"Charter Agent: Portfolio analysis completed")
    
    # Create agent
    agent = Agent(
        name="Chart Maker",
        system_prompt=CHARTER_INSTRUCTIONS,
        model=model
    )
    
    # Create task
    task = create_charter_task(portfolio_analysis, portfolio_data)
    logger.info(f"Charter Agent: Task created, length: {len(task)} characters")
    
    # Run agent
    try:
        response = agent(task)
        
        # Extract text from AgentResult if needed
        if hasattr(response, 'text'):
            response_text = response.text
        else:
            response_text = str(response)
            
        logger.info(f"Charter Agent: Generated response, length: {len(response_text) if response_text else 0}")
        
        if response_text:
            # Extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx + 1]
                
                # Validate JSON
                try:
                    parsed_data = json.loads(json_str)
                    charts = parsed_data.get('charts', [])
                    logger.info(f"Charter Agent: Successfully parsed JSON with {len(charts)} charts")
                    return json_str
                except json.JSONDecodeError as e:
                    logger.error(f"Charter Agent: Failed to parse JSON: {e}")
                    return json.dumps({"error": "Failed to parse chart data"})
            else:
                logger.error("Charter Agent: No JSON structure found in response")
                return json.dumps({"error": "No chart data generated"})
        else:
            logger.error("Charter Agent: Empty response")
            return json.dumps({"error": "Empty response from agent"})
            
    except Exception as e:
        logger.error(f"Charter Agent: Error during execution: {e}")
        return json.dumps({"error": f"Agent execution failed: {str(e)}"})

app = BedrockAgentCoreApp()


@app.entrypoint
async def chart_maker_agent(event):
        """Chart Maker Agent handler."""
        logger.info(f"Charter Agent: Received event with keys: {list(event.keys()) if isinstance(event, dict) else 'not a dict'}")
        
        # Extract required data
        job_id = event.get('job_id')
        portfolio_data = event.get('portfolio_data')
        user_id = event.get('user_id')
        
        if not job_id:
            return json.dumps({"error": "job_id is required"})
        
        # If portfolio_data is not provided, load it from database
        if not portfolio_data:
            try:
                logger.info(f"Charter Agent: Loading portfolio data from database for job_id: {job_id}")
                
                # Import database
                from src import Database
                db = Database()
                logger.debug("Charter Agent: Database connection established")
                
                # Get job info
                job = db.jobs.find_by_id(job_id)
                if not job:
                    logger.error(f"Charter Agent: Job {job_id} not found in database")
                    return json.dumps({"error": f"Job {job_id} not found"})
                
                user_id = job["clerk_user_id"]
                logger.info(f"Charter Agent: Found job for user_id: {user_id}")
                
                # Load portfolio data from database
                accounts = db.accounts.find_by_user(user_id)
                logger.info(f"Charter Agent: Found {len(accounts)} accounts for user {user_id}")
                portfolio_data = {"accounts": []}
                
                total_positions = 0
                for account in accounts:
                    # Handle None cash_balance safely
                    cash_balance = account.get("cash_balance")
                    if cash_balance is None:
                        cash_balance = 0.0
                    else:
                        cash_balance = float(cash_balance)
                        
                    account_data = {
                        "id": account["id"],
                        "name": account.get("account_name", f"Account {account['id']}"),
                        "type": account.get("account_name", "unknown"),  # Use account_name as type since no type field exists
                        "cash_balance": cash_balance,
                        "positions": []
                    }
                    logger.debug(f"Charter Agent: Processing account '{account.get('account_name', f'Account {account['id']}')}' (ID: {account['id']})")
                    
                    # Get positions for this account
                    positions = db.positions.find_by_account(account["id"])
                    logger.debug(f"Charter Agent: Found {len(positions)} positions for account {account.get('account_name', f'Account {account['id']}')}'")
                    
                    for position in positions:
                        # Get instrument data
                        instrument = db.instruments.find_by_symbol(position["symbol"])
                        if instrument:
                            # Handle None values safely
                            quantity = position.get("quantity")
                            if quantity is None:
                                quantity = 0.0
                            else:
                                quantity = float(quantity)
                                
                            current_price = instrument.get("current_price")
                            if current_price is None:
                                current_price = 0.0
                            else:
                                current_price = float(current_price)
                                
                            position_data = {
                                "symbol": position["symbol"],
                                "quantity": quantity,
                                "instrument": {
                                    "symbol": instrument["symbol"],
                                    "name": instrument.get("name", position["symbol"]),
                                    "current_price": current_price,
                                    "allocation_asset_class": instrument.get("allocation_asset_class", {}),
                                    "allocation_regions": instrument.get("allocation_regions", {}),
                                    "allocation_sectors": instrument.get("allocation_sectors", {})
                                }
                            }
                            account_data["positions"].append(position_data)
                            total_positions += 1
                            logger.debug(f"Charter Agent: Added position {position['symbol']} (qty: {position['quantity']}) to account {account.get('account_name', f'Account {account['id']}')}'")
                        else:
                            logger.warning(f"Charter Agent: Instrument not found for symbol {position['symbol']}")
                    
                    portfolio_data["accounts"].append(account_data)
                
                logger.info(f"Charter Agent: Loaded portfolio data with {len(portfolio_data['accounts'])} accounts and {total_positions} total positions")
                
            except Exception as e:
                logger.error(f"Charter Agent: Error loading portfolio data: {e}")
                return json.dumps({"error": f"Error loading portfolio data: {str(e)}"})
        
        # Run the agent
        result = create_agent_and_run(job_id, portfolio_data, user_id)
        
        # Save chart data to database
        try:
            logger.info(f"Charter Agent: Starting database save process for job_id: {job_id}")
            if result and not result.startswith('{"error"'):
                logger.debug(f"Charter Agent: Parsing chart result (length: {len(result)} chars)")
                # Parse the JSON result
                chart_json = json.loads(result)
                charts = chart_json.get('charts', [])
                logger.info(f"Charter Agent: Found {len(charts)} charts in result")
                
                if charts:
                    # Import database
                    from src import Database
                    db = Database()
                    logger.debug("Charter Agent: Database connection established for saving")
                    
                    # Convert charts array to dictionary with chart keys as top-level keys
                    charts_data = {}
                    for i, chart in enumerate(charts):
                        chart_key = chart.get('key', f"chart_{len(charts_data) + 1}")
                        # Remove the 'key' from the chart data since it's now the dict key
                        chart_copy = {k: v for k, v in chart.items() if k != 'key'}
                        charts_data[chart_key] = chart_copy
                        logger.debug(f"Charter Agent: Processed chart {i+1}/{len(charts)}: '{chart_key}' (type: {chart_copy.get('type', 'unknown')})")
                    
                    logger.info(f"Charter Agent: Attempting to save {len(charts_data)} charts to database for job_id: {job_id}")
                    logger.debug(f"Charter Agent: Chart data structure prepared with keys: {list(charts_data.keys())}")
                    logger.debug(f"Charter Agent: Job ID type: {type(job_id)}, value: {job_id}")
                    
                    # Save to database with detailed error handling
                    try:
                        success = db.jobs.update_charts(job_id, charts_data)
                        logger.debug(f"Charter Agent: update_charts returned: {success} (type: {type(success)})")
                    except Exception as db_error:
                        logger.error(f"Charter Agent: Database update_charts failed with error: {db_error}")
                        logger.error(f"Charter Agent: Error type: {type(db_error).__name__}")
                        success = False
                    
                    if success:
                        logger.info(f"Charter Agent: ✅ Successfully saved {len(charts_data)} charts to database")
                        logger.info(f"Charter Agent: Chart keys saved: {list(charts_data.keys())}")
                        # Log details about each chart saved
                        for key, chart in charts_data.items():
                            chart_type = chart.get('type', 'unknown')
                            data_points = len(chart.get('data', [])) if isinstance(chart.get('data'), list) else 0
                            logger.debug(f"Charter Agent: Saved chart '{key}': type={chart_type}, data_points={data_points}")
                    else:
                        logger.error("Charter Agent: ❌ Database update returned false - save operation failed")
                        logger.error(f"Charter Agent: Failed to save charts for job_id: {job_id}")
                    
                    logger.info(f"Charter Agent: Database save operation completed. Success: {success}")
                    
                    if success:
                        return json.dumps({
                            "success": True,
                            "message": f"Generated and saved {len(charts_data)} charts",
                            "charts_generated": len(charts_data),
                            "chart_keys": list(charts_data.keys())
                        })
                    else:
                        logger.error("Charter Agent: Failed to save charts to database")
                        return json.dumps({"error": "Failed to save charts to database"})
                else:
                    logger.warning("Charter Agent: No charts found in result - charts array was empty")
                    logger.debug(f"Charter Agent: Full result structure: {json.dumps(chart_json, indent=2)[:500]}...")
                    return json.dumps({"error": "No charts generated"})
            else:
                logger.error(f"Charter Agent: Invalid result format or error result detected")
                logger.error(f"Charter Agent: Result preview: {result[:200] if result else 'None'}")
                logger.debug(f"Charter Agent: Full result: {result}")
                return result  # Return original error
                
        except json.JSONDecodeError as e:
            logger.error(f"Charter Agent: JSON parsing error when saving to database: {e}")
            logger.error(f"Charter Agent: Invalid JSON result: {result[:500] if result else 'None'}")
            return json.dumps({"error": f"Invalid JSON format in chart result: {str(e)}"})
        except Exception as e:
            logger.error(f"Charter Agent: Unexpected error during database save operation: {e}")
            logger.error(f"Charter Agent: Error type: {type(e).__name__}")
            logger.debug(f"Charter Agent: Result that caused error: {result[:500] if result else 'None'}")
            return json.dumps({"error": f"Error saving charts: {str(e)}"})

if __name__ == "__main__":
   app.run()