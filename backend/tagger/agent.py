"""
InstrumentTagger Agent - Classifies financial instruments using OpenAI Agents SDK.
"""

import os
from typing import List, Optional
import logging

from pydantic import BaseModel, Field, field_validator, ConfigDict
from agents import Agent, Runner, trace
from agents.extensions.models.litellm_model import LitellmModel
from dotenv import load_dotenv

from src.schemas import InstrumentCreate
from templates import TAGGER_INSTRUCTIONS, CLASSIFICATION_PROMPT

# Load environment variables
load_dotenv(override=True)

# Configure logging
logger = logging.getLogger(__name__)

# Get configuration
BEDROCK_MODEL_ID = os.getenv('BEDROCK_MODEL_ID', 'us.anthropic.claude-3-5-sonnet-20241022-v2:0')
BEDROCK_MODEL_REGION = os.getenv('BEDROCK_MODEL_REGION', os.getenv('AWS_REGION', 'us-east-1'))

class AllocationBreakdown(BaseModel):
    """Allocation percentages that must sum to 100"""
    model_config = ConfigDict(extra='forbid')
    
    # We'll use a simplified approach with specific fields
    # Asset classes
    equity: float = Field(default=0.0, ge=0, le=100, description="Equity percentage")
    fixed_income: float = Field(default=0.0, ge=0, le=100, description="Fixed income percentage")
    real_estate: float = Field(default=0.0, ge=0, le=100, description="Real estate percentage")
    commodities: float = Field(default=0.0, ge=0, le=100, description="Commodities percentage")
    cash: float = Field(default=0.0, ge=0, le=100, description="Cash percentage")
    alternatives: float = Field(default=0.0, ge=0, le=100, description="Alternatives percentage")

class RegionAllocation(BaseModel):
    """Regional allocation percentages"""
    model_config = ConfigDict(extra='forbid', populate_by_name=True)
    
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
    model_config = ConfigDict(extra='forbid')
    
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
    model_config = ConfigDict(extra='forbid')
    
    symbol: str = Field(description="Ticker symbol of the instrument")
    name: str = Field(description="Name of the instrument")
    instrument_type: str = Field(description="Type: etf, stock, mutual_fund, bond_fund, etc.")
    
    # Separate allocation objects
    allocation_asset_class: AllocationBreakdown = Field(description="Asset class breakdown")
    allocation_regions: RegionAllocation = Field(description="Regional breakdown")
    allocation_sectors: SectorAllocation = Field(description="Sector breakdown")
    
    @field_validator('allocation_asset_class')
    def validate_asset_class_sum(cls, v: AllocationBreakdown):
        total = v.equity + v.fixed_income + v.real_estate + v.commodities + v.cash + v.alternatives
        if abs(total - 100.0) > 0.01:  # Allow small floating point errors
            raise ValueError(f"Asset class allocations must sum to 100.0, got {total}")
        return v
    
    @field_validator('allocation_regions')
    def validate_regions_sum(cls, v: RegionAllocation):
        total = (v.north_america + v.europe + v.asia + v.latin_america + 
                v.africa + v.middle_east + v.oceania + v.global_ + v.international)
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Regional allocations must sum to 100.0, got {total}")
        return v
    
    @field_validator('allocation_sectors')
    def validate_sectors_sum(cls, v: SectorAllocation):
        total = (v.technology + v.healthcare + v.financials + v.consumer_discretionary +
                v.consumer_staples + v.industrials + v.materials + v.energy +
                v.utilities + v.real_estate + v.communication + 
                v.treasury + v.corporate + v.mortgage + v.government_related +
                v.commodities + v.diversified + v.other)
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Sector allocations must sum to 100.0, got {total}")
        return v

async def classify_instrument(
    symbol: str,
    name: str,
    instrument_type: str = "etf"
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
    # Set region for Bedrock if specified
    if BEDROCK_MODEL_REGION != os.getenv('AWS_REGION', 'us-east-1'):
        os.environ["AWS_REGION_NAME"] = BEDROCK_MODEL_REGION
        os.environ["AWS_REGION"] = BEDROCK_MODEL_REGION
        os.environ["AWS_DEFAULT_REGION"] = BEDROCK_MODEL_REGION
    
    # Initialize the model
    model = LitellmModel(model=f"bedrock/{BEDROCK_MODEL_ID}")
    
    # Create the classification task
    task = CLASSIFICATION_PROMPT.format(
        symbol=symbol,
        name=name,
        instrument_type=instrument_type
    )
    
    # Run the agent (following gameplan pattern exactly)
    with trace(f"Classify {symbol}"):
        agent = Agent(
            name="InstrumentTagger",
            instructions=TAGGER_INSTRUCTIONS,
            model=model,
            tools=[],  # No tools needed for classification
            output_type=InstrumentClassification  # Specify structured output type
        )
        
        result = await Runner.run(
            agent,
            input=task,
            max_turns=5
        )
        
        # Extract the structured output from RunResult using final_output_as
        return result.final_output_as(InstrumentClassification)

async def tag_instruments(instruments: List[dict]) -> List[InstrumentClassification]:
    """
    Tag multiple instruments concurrently with bounded parallelism.
    
    Args:
        instruments: List of dicts with symbol, name, and optionally instrument_type
        
    Returns:
        List of classifications
    """
    import asyncio
    
    # Process instruments sequentially (simple and reliable)
    results = []
    for instrument in instruments:
        try:
            classification = await classify_instrument(
                symbol=instrument['symbol'],
                name=instrument.get('name', ''),
                instrument_type=instrument.get('instrument_type', 'etf')
            )
            logger.info(f"Successfully classified {instrument['symbol']}")
            results.append(classification)
        except Exception as e:
            logger.error(f"Error classifying {instrument['symbol']}: {e}")
            results.append(None)
    
    # Filter out None values (failed classifications)
    classifications = [r for r in results if r is not None]
    
    return classifications

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
        'equity': classification.allocation_asset_class.equity,
        'fixed_income': classification.allocation_asset_class.fixed_income,
        'real_estate': classification.allocation_asset_class.real_estate,
        'commodities': classification.allocation_asset_class.commodities,
        'cash': classification.allocation_asset_class.cash,
        'alternatives': classification.allocation_asset_class.alternatives
    }
    # Remove zero values
    asset_class_dict = {k: v for k, v in asset_class_dict.items() if v > 0}
    
    regions_dict = {
        'north_america': classification.allocation_regions.north_america,
        'europe': classification.allocation_regions.europe,
        'asia': classification.allocation_regions.asia,
        'latin_america': classification.allocation_regions.latin_america,
        'africa': classification.allocation_regions.africa,
        'middle_east': classification.allocation_regions.middle_east,
        'oceania': classification.allocation_regions.oceania,
        'global': classification.allocation_regions.global_,
        'international': classification.allocation_regions.international
    }
    # Remove zero values
    regions_dict = {k: v for k, v in regions_dict.items() if v > 0}
    
    sectors_dict = {
        'technology': classification.allocation_sectors.technology,
        'healthcare': classification.allocation_sectors.healthcare,
        'financials': classification.allocation_sectors.financials,
        'consumer_discretionary': classification.allocation_sectors.consumer_discretionary,
        'consumer_staples': classification.allocation_sectors.consumer_staples,
        'industrials': classification.allocation_sectors.industrials,
        'materials': classification.allocation_sectors.materials,
        'energy': classification.allocation_sectors.energy,
        'utilities': classification.allocation_sectors.utilities,
        'real_estate': classification.allocation_sectors.real_estate,
        'communication': classification.allocation_sectors.communication,
        'treasury': classification.allocation_sectors.treasury,
        'corporate': classification.allocation_sectors.corporate,
        'mortgage': classification.allocation_sectors.mortgage,
        'government_related': classification.allocation_sectors.government_related,
        'commodities': classification.allocation_sectors.commodities,
        'diversified': classification.allocation_sectors.diversified,
        'other': classification.allocation_sectors.other
    }
    # Remove zero values
    sectors_dict = {k: v for k, v in sectors_dict.items() if v > 0}
    
    return InstrumentCreate(
        symbol=classification.symbol,
        name=classification.name,
        instrument_type=classification.instrument_type,
        allocation_asset_class=asset_class_dict,
        allocation_regions=regions_dict,
        allocation_sectors=sectors_dict
    )