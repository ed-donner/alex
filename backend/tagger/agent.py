"""
InstrumentTagger Agent - Classifies financial instruments using OpenAI Agents SDK.
"""

import os
from typing import List
import logging
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, ConfigDict
from agents import Agent, Runner, trace
from agents.extensions.models.litellm_model import LitellmModel
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from litellm.exceptions import RateLimitError

from src.schemas import InstrumentCreate
from templates import TAGGER_INSTRUCTIONS, CLASSIFICATION_PROMPT

# Load environment variables (dotenv automatically searches up the tree)
load_dotenv(override=True)

# Configure logging
logger = logging.getLogger(__name__)

# Get configuration
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-west-2")


def create_model():
    """Create the configured model, defaulting to Bedrock unless OpenAI is selected."""
    model_provider = os.getenv("MODEL_PROVIDER", "bedrock").lower()
    if model_provider == "openai":
        model_id = os.getenv("OPENAI_MODEL_ID", "gpt-4.1-mini")
        logger.info(f"Tagger: Using OpenAI model {model_id}")
        return model_id

    model_id = BEDROCK_MODEL_ID
    bedrock_region = os.getenv("BEDROCK_REGION", BEDROCK_REGION)
    os.environ["AWS_REGION_NAME"] = bedrock_region
    os.environ["AWS_REGION"] = bedrock_region
    os.environ["AWS_DEFAULT_REGION"] = bedrock_region
    logger.info(f"Tagger: Using Bedrock model {model_id} in {bedrock_region}")
    return LitellmModel(model=f"bedrock/{model_id}")


class AllocationBreakdown(BaseModel):
    """Allocation percentages that must sum to 100"""

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    north_america: float = Field(default=0.0, ge=0, le=100)
    europe: float = Field(default=0.0, ge=0, le=100)
    asia: float = Field(default=0.0, ge=0, le=100)
    latin_america: float = Field(default=0.0, ge=0, le=100)
    africa: float = Field(default=0.0, ge=0, le=100)
    middle_east: float = Field(default=0.0, ge=0, le=100)
    oceania: float = Field(default=0.0, ge=0, le=100)
    global_: float = Field(
        default=0.0, ge=0, le=100, alias="global", description="Global or diversified"
    )
    international: float = Field(
        default=0.0, ge=0, le=100, description="International developed markets"
    )


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
    government_related: float = Field(
        default=0.0, ge=0, le=100, description="Government-related bonds"
    )
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
            v.north_america
            + v.europe
            + v.asia
            + v.latin_america
            + v.africa
            + v.middle_east
            + v.oceania
            + v.global_
            + v.international
        )
        if abs(total - 100.0) > 3:
            raise ValueError(f"Regional allocations must sum to 100.0, got {total}")
        return v

    @field_validator("allocation_sectors")
    def validate_sectors_sum(cls, v: SectorAllocation):
        total = (
            v.technology
            + v.healthcare
            + v.financials
            + v.consumer_discretionary
            + v.consumer_staples
            + v.industrials
            + v.materials
            + v.energy
            + v.utilities
            + v.real_estate
            + v.communication
            + v.treasury
            + v.corporate
            + v.mortgage
            + v.government_related
            + v.commodities
            + v.diversified
            + v.other
        )
        if abs(total - 100.0) > 3:
            raise ValueError(f"Sector allocations must sum to 100.0, got {total}")
        return v


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
        model = create_model()

        # Create the classification task
        task = CLASSIFICATION_PROMPT.format(
            symbol=symbol, name=name, instrument_type=instrument_type
        )

        # Run the agent (following gameplan pattern exactly)
        with trace(f"Classify {symbol}"):
            agent = Agent(
                name="InstrumentTagger",
                instructions=TAGGER_INSTRUCTIONS,
                model=model,
                tools=[],  # No tools needed for classification
                output_type=InstrumentClassification,  # Specify structured output type
            )

            result = await Runner.run(agent, input=task, max_turns=5)

            # Extract the structured output from RunResult using final_output_as
            return result.final_output_as(InstrumentClassification)

    except Exception as e:
        logger.error(f"Error classifying {symbol}: {e}")
        raise


async def tag_instruments(instruments: List[dict]) -> List[InstrumentClassification]:
    """
    Tag multiple instruments with simple retry logic.

    Args:
        instruments: List of dicts with symbol, name, and optionally instrument_type

    Returns:
        List of classifications
    """
    import asyncio

    # Add retry decorator to classify_instrument calls
    @retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        before_sleep=lambda retry_state: logger.info(
            f"Tagger: Rate limit hit, retrying in {retry_state.next_action.sleep} seconds..."
        ),
    )
    async def classify_with_retry(symbol, name, instrument_type):
        return await classify_instrument(symbol, name, instrument_type)

    # Process instruments sequentially with small delay
    results = []
    for i, instrument in enumerate(instruments):
        # Small delay between requests to avoid rate limits
        if i > 0:
            await asyncio.sleep(0.5)

        try:
            classification = await classify_with_retry(
                symbol=instrument["symbol"],
                name=instrument.get("name", ""),
                instrument_type=instrument.get("instrument_type", "etf"),
            )
            logger.info(f"Successfully classified {instrument['symbol']}")
            results.append(classification)
        except Exception as e:
            logger.error(f"Failed to classify {instrument['symbol']}: {e}")
            results.append(None)

    # Filter out None values
    return [r for r in results if r is not None]


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
