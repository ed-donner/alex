"""
Chart Maker Agent - creates visualization data for portfolio analysis.
"""

import os
import logging
from typing import Dict, Any

from agents.extensions.models.litellm_model import LitellmModel

from templates import CHARTER_INSTRUCTIONS, create_charter_task

logger = logging.getLogger()


def create_model():
    """Create the configured model, defaulting to Bedrock unless OpenAI is selected."""
    model_provider = os.getenv("MODEL_PROVIDER", "bedrock").lower()
    if model_provider == "openai":
        model_id = os.getenv("OPENAI_MODEL_ID", "gpt-4.1-mini")
        logger.info(f"Charter: Using OpenAI model {model_id}")
        return model_id

    model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
    bedrock_region = os.getenv("BEDROCK_REGION", "us-west-2")
    os.environ["AWS_REGION_NAME"] = bedrock_region
    os.environ["AWS_REGION"] = bedrock_region
    os.environ["AWS_DEFAULT_REGION"] = bedrock_region
    logger.info(f"Charter: Using Bedrock model {model_id} in {bedrock_region}")
    return LitellmModel(model=f"bedrock/{model_id}")


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
        account_name = account.get("name", "Unknown")
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
                logger.warning(f"Charter: No price for {symbol}, using default of 1.0")
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


def create_agent(job_id: str, portfolio_data: Dict[str, Any], db=None):
    """Create the charter agent without tools - will output JSON directly."""
    
    logger.info(f"Charter: Job ID: {job_id}")
    
    model = create_model()
    
    # Analyze the portfolio upfront
    portfolio_analysis = analyze_portfolio(portfolio_data)
    logger.info(f"Charter: Portfolio analysis generated, length: {len(portfolio_analysis)}")
    
    # Create the task using template
    task = create_charter_task(portfolio_analysis, portfolio_data)
    
    logger.info(f"Charter: Task created, length: {len(task)} characters")
    
    # Return model and task (no tools or context needed)
    return model, task