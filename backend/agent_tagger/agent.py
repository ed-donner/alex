
"""
InstrumentTagger Agent - Classifies financial instruments using OpenAI Agents SDK.
Simplified version for testing and direct usage.
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Any
from decimal import Decimal
from unittest import result

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

from pydantic import BaseModel, Field, field_validator, ConfigDict
from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from src.schemas import InstrumentCreate

from strands.models import BedrockModel

import sys
import os

# Add current directory to Python path for src imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
from src import Database

db = Database()


# from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Load environment variables


# Configure logging
logger = logging.getLogger(__name__)

model_id = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
# Get configuration
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", model_id)
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-west-2")

# Tagger instructions
TAGGER_INSTRUCTIONS = """You are an expert financial instrument classifier responsible for categorizing ETFs, stocks, and other securities.

Your task is to accurately classify financial instruments by providing:
1. Current market price per share in USD
2. Exact allocation percentages for:
   - Asset classes (equity, fixed_income, real_estate, commodities, cash, alternatives)
   - Regions (north_america, europe, asia, etc.)
   - Sectors (technology, healthcare, financials, etc.)

Important rules:
- Each allocation category MUST sum to exactly 100.0
- Use your knowledge of the instrument to provide accurate allocations
- For ETFs, consider the underlying holdings
- For individual stocks, allocate 100% to the appropriate categories
- Be precise with decimal values to ensure totals equal 100.0

Examples:
- SPY (S&P 500 ETF): 100% equity, 100% north_america, distributed across sectors based on S&P 500 composition
- BND (Bond ETF): 100% fixed_income, 100% north_america, split between treasury and corporate
- AAPL (Apple stock): 100% equity, 100% north_america, 100% technology
- VTI (Total Market): 100% equity, 100% north_america, diverse sector allocation
- VXUS (International): 100% equity, distributed across regions, diverse sectors

You must return your response as a structured InstrumentClassification object with all fields properly populated."""

CLASSIFICATION_PROMPT = """Classify the following financial instrument:

Symbol: {symbol}
Name: {name}
Type: {instrument_type}

Provide:
1. Current price per share in USD (approximate market price as of late 2024/early 2025)
2. Accurate allocation percentages for:
   - Asset classes (equity, fixed_income, real_estate, commodities, cash, alternatives)
   - Regions (north_america, europe, asia, latin_america, africa, middle_east, oceania, global, international)
   - Sectors (technology, healthcare, financials, consumer_discretionary, consumer_staples, industrials, materials, energy, utilities, real_estate, communication, treasury, corporate, mortgage, government_related, commodities, diversified, other)

Remember:
- Each category must sum to exactly 100.0%
- For stocks, typically 100% in one asset class, one region, one sector
- For ETFs, distribute based on underlying holdings
- For bonds/bond funds, use fixed_income asset class and appropriate sectors (treasury/corporate/mortgage/government_related)"""

# Pydantic models for structured data
class AllocationBreakdown(BaseModel):
    """Allocation percentages that must sum to 100"""
    model_config = ConfigDict(extra="forbid")
    
    equity: float = Field(default=0.0, ge=0, le=100, description="Equity percentage")
    fixed_income: float = Field(default=0.0, ge=0, le=100, description="Fixed income percentage")
    real_estate: float = Field(default=0.0, ge=0, le=100, description="Real estate percentage")
    commodities: float = Field(default=0.0, ge=0, le=100, description="Commodities percentage")
    cash: float = Field(default=0.0, ge=0, le=100, description="Cash percentage")
    alternatives: float = Field(default=0.0, ge=0, le=100, description="Alternatives percentage")

class RegionAllocation(BaseModel):
    """Regional allocation percentages"""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    
    north_america: float = Field(default=0.0, ge=0, le=100)
    europe: float = Field(default=0.0, ge=0, le=100)
    asia: float = Field(default=0.0, ge=0, le=100)
    latin_america: float = Field(default=0.0, ge=0, le=100)
    africa: float = Field(default=0.0, ge=0, le=100)
    middle_east: float = Field(default=0.0, ge=0, le=100)
    oceania: float = Field(default=0.0, ge=0, le=100)
    global_: float = Field(default=0.0, ge=0, le=100, alias="global", description="Global or diversified")
    international: float = Field(default=0.0, ge=0, le=100, description="International developed markets")

class SectorAllocation(BaseModel):
    """Sector allocation percentages"""
    model_config = ConfigDict(extra="forbid")
    
    technology: float = Field(default=0.0, ge=0, le=100)
    healthcare: float = Field(default=0.0, ge=0, le=100)
    financials: float = Field(default=0.0, ge=0, le=100)
    consumer_discretionary: float = Field(default=0.0, ge=0, le=100)
    consumer_staples: float = Field(default=0.0, ge=0, le=100)
    industrials: float = Field(default=0.0, ge=0, le=100)
    materials: float = Field(default=0.0, ge=0, le=100)
    energy: float = Field(default=0.0, ge=0, le=100)
    utilities: float = Field(default=0.0, ge=0, le=100)
    real_estate: float = Field(default=0.0, ge=0, le=100, description="Real estate sector")
    communication: float = Field(default=0.0, ge=0, le=100)
    treasury: float = Field(default=0.0, ge=0, le=100, description="Treasury bonds")
    corporate: float = Field(default=0.0, ge=0, le=100, description="Corporate bonds")
    mortgage: float = Field(default=0.0, ge=0, le=100, description="Mortgage-backed securities")
    government_related: float = Field(default=0.0, ge=0, le=100, description="Government-related bonds")
    commodities: float = Field(default=0.0, ge=0, le=100, description="Commodities")
    diversified: float = Field(default=0.0, ge=0, le=100, description="Diversified sectors")
    other: float = Field(default=0.0, ge=0, le=100, description="Other sectors")

class InstrumentClassification(BaseModel):
    """Structured output for instrument classification"""
    model_config = ConfigDict(extra="forbid")
    
    symbol: str = Field(description="Ticker symbol of the instrument")
    name: str = Field(description="Name of the instrument")
    instrument_type: str = Field(description="Type: etf, stock, mutual_fund, bond_fund, etc.")
    current_price: float = Field(description="Current price per share in USD", gt=0)
    
    # Separate allocation objects
    allocation_asset_class: AllocationBreakdown = Field(description="Asset class breakdown")
    allocation_regions: RegionAllocation = Field(description="Regional breakdown")
    allocation_sectors: SectorAllocation = Field(description="Sector breakdown")

    @field_validator("allocation_asset_class")
    def validate_asset_class_sum(cls, v: AllocationBreakdown):
        total = v.equity + v.fixed_income + v.real_estate + v.commodities + v.cash + v.alternatives
        if abs(total - 100.0) > 3:  # Allow small floating point errors
            raise ValueError(f"Asset class allocations must sum to 100.0, got {total}")
        return v

    @field_validator("allocation_regions")
    def validate_regions_sum(cls, v: RegionAllocation):
        total = (
            v.north_america + v.europe + v.asia + v.latin_america + v.africa + 
            v.middle_east + v.oceania + v.global_ + v.international
        )
        if abs(total - 100.0) > 3:
            raise ValueError(f"Regional allocations must sum to 100.0, got {total}")
        return v

    @field_validator("allocation_sectors")
    def validate_sectors_sum(cls, v: SectorAllocation):
        total = (
            v.technology + v.healthcare + v.financials + v.consumer_discretionary + 
            v.consumer_staples + v.industrials + v.materials + v.energy + v.utilities + 
            v.real_estate + v.communication + v.treasury + v.corporate + v.mortgage + 
            v.government_related + v.commodities + v.diversified + v.other
        )
        if abs(total - 100.0) > 3:
            raise ValueError(f"Sector allocations must sum to 100.0, got {total}")
        return v
    

def classification_to_db_format(classification: InstrumentClassification) -> InstrumentCreate:
    """
    Convert classification to database format.

    Args:
        classification: The AI classification

    Returns:
        Database-ready instrument data
    """
    # Convert allocation objects to dicts
    asset_class_dict = {
        "equity": classification.allocation_asset_class.equity,
        "fixed_income": classification.allocation_asset_class.fixed_income,
        "real_estate": classification.allocation_asset_class.real_estate,
        "commodities": classification.allocation_asset_class.commodities,
        "cash": classification.allocation_asset_class.cash,
        "alternatives": classification.allocation_asset_class.alternatives,
    }
    # Remove zero values
    asset_class_dict = {k: v for k, v in asset_class_dict.items() if v > 0}

    regions_dict = {
        "north_america": classification.allocation_regions.north_america,
        "europe": classification.allocation_regions.europe,
        "asia": classification.allocation_regions.asia,
        "latin_america": classification.allocation_regions.latin_america,
        "africa": classification.allocation_regions.africa,
        "middle_east": classification.allocation_regions.middle_east,
        "oceania": classification.allocation_regions.oceania,
        "global": classification.allocation_regions.global_,
        "international": classification.allocation_regions.international,
    }
    # Remove zero values
    regions_dict = {k: v for k, v in regions_dict.items() if v > 0}

    sectors_dict = {
        "technology": classification.allocation_sectors.technology,
        "healthcare": classification.allocation_sectors.healthcare,
        "financials": classification.allocation_sectors.financials,
        "consumer_discretionary": classification.allocation_sectors.consumer_discretionary,
        "consumer_staples": classification.allocation_sectors.consumer_staples,
        "industrials": classification.allocation_sectors.industrials,
        "materials": classification.allocation_sectors.materials,
        "energy": classification.allocation_sectors.energy,
        "utilities": classification.allocation_sectors.utilities,
        "real_estate": classification.allocation_sectors.real_estate,
        "communication": classification.allocation_sectors.communication,
        "treasury": classification.allocation_sectors.treasury,
        "corporate": classification.allocation_sectors.corporate,
        "mortgage": classification.allocation_sectors.mortgage,
        "government_related": classification.allocation_sectors.government_related,
        "commodities": classification.allocation_sectors.commodities,
        "diversified": classification.allocation_sectors.diversified,
        "other": classification.allocation_sectors.other,
    }
    # Remove zero values
    sectors_dict = {k: v for k, v in sectors_dict.items() if v > 0}

    return InstrumentCreate(
        symbol=classification.symbol,
        name=classification.name,
        instrument_type=classification.instrument_type,
        current_price=Decimal(
            str(classification.current_price)
        ),  # Use actual price from classification
        allocation_asset_class=asset_class_dict,
        allocation_regions=regions_dict,
        allocation_sectors=sectors_dict,
    )



async def tag_instruments(instruments: List[dict]) -> List[InstrumentClassification]:
    """
    Tag multiple instruments.
    
    Args:
        instruments: List of dicts with symbol, name, and optionally instrument_type
        
    Returns:
        List of classifications
    """
    results = []
    for i, instrument in enumerate(instruments):
        # Small delay between requests to avoid rate limits
        if i > 0:
            await asyncio.sleep(0.5)
            
        try:
            classification = await classify_instrument(
                symbol=instrument["symbol"],
                name=instrument.get("name", ""),
                instrument_type=instrument.get("instrument_type", "etf"),
            )
            logger.info(f"Successfully classified {instrument['symbol']}")
            results.append(classification)
        except Exception as e:
            logger.error(f"Failed to classify {instrument['symbol']}: {e}")
            continue
            
    return results


async def classify_instrument(
    symbol: str, name: str, instrument_type: str = "etf"
) -> InstrumentClassification:
    """
    Classify a financial instrument using OpenAI Agents SDK.

    Args:
        symbol: Ticker symbol
        name: Instrument name
        instrument_type: Type of instrument

    Returns:
        Complete classification with allocations
    """
    try:


        model = BedrockModel(
            model_id=model_id,
        )

        agent = Agent(
            model=model,
            system_prompt=TAGGER_INSTRUCTIONS
        )

        task = CLASSIFICATION_PROMPT.format(
            symbol=symbol, name=name, instrument_type=instrument_type
        )
        print("Generated task:", task)  

        response = agent.structured_output(InstrumentClassification, task)

        # The structured_output method returns the object directly
        return response

    except Exception as e:
        logger.error(f"Error classifying {symbol}: {e}")
        raise


def classification_to_dict(classification: InstrumentClassification) -> Dict[str, Any]:
    """
    Convert classification to dictionary format.
    
    Args:
        classification: The AI classification
        
    Returns:
        Dictionary representation
    """
    return {
        "symbol": classification.symbol,
        "name": classification.name,
        "instrument_type": classification.instrument_type,
        "current_price": classification.current_price,
        "allocation_asset_class": classification.allocation_asset_class.model_dump(),
        "allocation_regions": classification.allocation_regions.model_dump(),
        "allocation_sectors": classification.allocation_sectors.model_dump(),
    }



async def process_instruments(instruments: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Process and classify instruments asynchronously.
    
    Args:
        instruments: List of instruments to classify
        
    Returns:
        Processing results
    """
    # Run the classification
    logger.info(f"Classifying {len(instruments)} instruments")
    classifications = await tag_instruments(instruments)
    
    # Update database with classifications
    updated = []
    errors = []
    
    for classification in classifications:
        try:
            # Convert to database format
            db_instrument = classification_to_db_format(classification)
            
            # Check if instrument exists
            existing = db.instruments.find_by_symbol(classification.symbol)
            
            if existing:
                # Update existing instrument
                update_data = db_instrument.model_dump()
                # Remove symbol as it's the key
                del update_data['symbol']
                
                rows = db.client.update(
                    'instruments',
                    update_data,
                    "symbol = :symbol",
                    {'symbol': classification.symbol}
                )
                logger.info(f"Updated {classification.symbol} in database ({rows} rows)")
            else:
                # Create new instrument
                db.instruments.create_instrument(db_instrument)
                logger.info(f"Created {classification.symbol} in database")
            
            updated.append(classification.symbol)
            
        except Exception as e:
            logger.error(f"Error updating {classification.symbol}: {e}")
            errors.append({
                'symbol': classification.symbol,
                'error': str(e)
            })
    
    # Prepare response (convert Pydantic models to dicts)
    return {
        'tagged': len(classifications),
        'updated': updated,
        'errors': errors,
        'classifications': [
            {
                'symbol': c.symbol,
                'name': c.name,
                'type': c.instrument_type,
                'current_price': c.current_price,
                'asset_class': c.allocation_asset_class.model_dump(),
                'regions': c.allocation_regions.model_dump(),
                'sectors': c.allocation_sectors.model_dump()
            }
            for c in classifications
        ]
    }

def tag_instrument(payload: Dict[str, Any]) -> InstrumentClassification:
    """
    Tag a single instrument (synchronous version).
    
    Args:
        payload: Dict with symbol, name, and instrument_type
        
    Returns:
        Classification result
    """
    model = BedrockModel(
        model_id=model_id,
    )

    agent = Agent(
        model=model,
        system_prompt=TAGGER_INSTRUCTIONS
    )

    task = CLASSIFICATION_PROMPT.format(
        symbol=payload["symbol"], 
        name=payload.get("name", ""), 
        instrument_type=payload.get("instrument_type", "etf")
    )
    print("Tagging payload:", payload)
    print("Generated task:", task)  

    response = agent.structured_output(InstrumentClassification, task)

    return response

app = BedrockAgentCoreApp()


@app.entrypoint
def tagger_agent(payload):
            # Parse the event
        try:
            instruments = payload.get('instruments', [])

            if not instruments:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'No instruments provided'})
                }

            # Process all instruments in a single async context
            result = asyncio.run(process_instruments(instruments))

            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }

        except Exception as e:
            logger.error(f"Lambda handler error: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': str(e)})
            }


if __name__ == "__main__":
    app.run()
    # Simple test when run directly
    # async def test():
    #     payload = {
    #         "symbol": "AAPL",
    #         "name": "Apple Inc",
    #         "instrument_type": "stock"
    #     }
    #     result = await handle_request(payload)
    #     print(json.dumps(result, indent=2))
    
    # asyncio.run(test())
