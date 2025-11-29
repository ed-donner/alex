"""
Pydantic schemas for data validation and LLM tool interfaces
These models serve as both database validation and LLM structured output schemas
"""

from typing import Dict, Literal, Optional, List
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from datetime import date, datetime


# Define allowed values as Literals for LLM compatibility
RegionType = Literal[
    "north_america",
    "europe",
    "asia",
    "latin_america",
    "africa",
    "middle_east",
    "oceania",
    "global",
    "international",  # For mixed non-US
]

AssetClassType = Literal[
    "equity", "fixed_income", "real_estate", "commodities", "cash", "alternatives"
]

SectorType = Literal[
    "technology",
    "healthcare",
    "financials",
    "consumer_discretionary",
    "consumer_staples",
    "industrials",
    "energy",
    "materials",
    "utilities",
    "real_estate",
    "communication",
    "treasury",
    "corporate",
    "mortgage",
    "government_related",
    "commodities",
    "diversified",
    "other",
]

InstrumentType = Literal["etf", "mutual_fund", "stock", "bond", "bond_fund", "commodity", "reit"]

JobType = Literal[
    "portfolio_analysis",
    "rebalance_recommendation",
    "retirement_projection",
    "risk_assessment",
    "tax_optimization",
    "instrument_research",
]

JobStatus = Literal["pending", "running", "completed", "failed"]

AccountType = Literal[
    "401k", "roth_ira", "traditional_ira", "taxable", "529", "hsa", "pension", "other"
]


class AllocationDict(BaseModel):
    """Base class for allocation dictionaries ensuring they sum to 100"""

    @field_validator("*", mode="after")
    def validate_sum(cls, v, info):
        """Ensure allocation percentages sum to 100"""
        if isinstance(v, dict):
            total = sum(v.values())
            if abs(total - 100) > 3:  # Allow small floating point errors
                raise ValueError(f"Allocations must sum to 100, got {total}")
        return v


class RegionAllocation(BaseModel):
    """Geographic allocation of an instrument"""

    allocations: Dict[RegionType, float] = Field(
        description="Percentage allocation by geographic region. Must sum to 100.",
        example={"north_america": 60, "europe": 25, "asia": 15},
    )

    @field_validator("allocations")
    def validate_sum(cls, v):
        total = sum(v.values())
        if abs(total - 100) > 3:
            raise ValueError(f"Region allocations must sum to 100, got {total}")
        return v


class AssetClassAllocation(BaseModel):
    """Asset class allocation of an instrument"""

    allocations: Dict[AssetClassType, float] = Field(
        description="Percentage allocation by asset class. Must sum to 100.",
        example={"equity": 80, "fixed_income": 20},
    )

    @field_validator("allocations")
    def validate_sum(cls, v):
        total = sum(v.values())
        if abs(total - 100) > 3:
            raise ValueError(f"Asset class allocations must sum to 100, got {total}")
        return v


class SectorAllocation(BaseModel):
    """Sector allocation of an instrument"""

    allocations: Dict[SectorType, float] = Field(
        description="Percentage allocation by market sector. Must sum to 100.",
        example={"technology": 30, "healthcare": 25, "financials": 20, "other": 25},
    )

    @field_validator("allocations")
    def validate_sum(cls, v):
        total = sum(v.values())
        if abs(total - 100) > 3:
            raise ValueError(f"Sector allocations must sum to 100, got {total}")
        return v


class InstrumentCreate(BaseModel):
    """Schema for creating a new instrument - suitable for LLM tool input"""

    symbol: str = Field(
        description="The ticker symbol of the instrument (e.g., 'SPY', 'BND')",
        min_length=1,
        max_length=20,
    )
    name: str = Field(description="Full name of the instrument", min_length=1, max_length=255)
    instrument_type: InstrumentType = Field(description="The type of financial instrument")
    current_price: Optional[Decimal] = Field(
        None,
        description="Current price of the instrument for portfolio calculations",
        ge=0,
        le=999999,
    )
    allocation_regions: Dict[RegionType, float] = Field(
        description="Geographic allocation percentages. Must sum to 100.",
        example={"north_america": 100},
    )
    allocation_sectors: Dict[SectorType, float] = Field(
        description="Sector allocation percentages. Must sum to 100.",
        example={"technology": 40, "healthcare": 30, "financials": 30},
    )
    allocation_asset_class: Dict[AssetClassType, float] = Field(
        description="Asset class allocation percentages. Must sum to 100.", example={"equity": 100}
    )

    @field_validator("allocation_regions", "allocation_sectors", "allocation_asset_class")
    def validate_allocations(cls, v):
        """Ensure all allocations sum to 100"""
        if not v:
            raise ValueError("Allocation cannot be empty")
        total = sum(v.values())
        if abs(total - 100) > 3:
            raise ValueError(f"Allocations must sum to 100, got {total}")
        return v


class InstrumentResponse(InstrumentCreate):
    """Schema for instrument responses from database"""

    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    """Schema for creating a user - suitable for LLM tool input"""

    clerk_user_id: str = Field(description="Unique identifier from Clerk authentication system")
    display_name: Optional[str] = Field(None, description="User's display name", max_length=255)
    years_until_retirement: Optional[int] = Field(
        None, description="Number of years until the user plans to retire", ge=0, le=100
    )
    target_retirement_income: Optional[Decimal] = Field(
        None, description="Annual income goal in retirement (in dollars)", ge=0, decimal_places=2
    )
    asset_class_targets: Optional[Dict[AssetClassType, float]] = Field(
        default={"equity": 70, "fixed_income": 30},
        description="Target allocation percentages for rebalancing. Must sum to 100.",
    )
    region_targets: Optional[Dict[RegionType, float]] = Field(
        default={"north_america": 50, "international": 50},
        description="Target geographic allocation for rebalancing. Must sum to 100.",
    )


class AccountCreate(BaseModel):
    """Schema for creating an account - suitable for LLM tool input"""

    account_name: str = Field(
        description="Name of the account (e.g., '401k', 'Roth IRA')", min_length=1, max_length=255
    )
    account_purpose: Optional[str] = Field(None, description="Purpose or goal of this account")
    cash_balance: Decimal = Field(
        default=Decimal("0"),
        description="Uninvested cash balance in the account",
        ge=0,
        decimal_places=2,
    )
    cash_interest: Decimal = Field(
        default=Decimal("0"),
        description="Annual interest rate on cash (e.g., 0.045 for 4.5%)",
        ge=0,
        le=1,
        decimal_places=4,
    )


class PositionCreate(BaseModel):
    """Schema for creating a position - suitable for LLM tool input"""

    account_id: str = Field(description="UUID of the account holding this position")
    symbol: str = Field(description="Ticker symbol of the instrument", min_length=1, max_length=20)
    quantity: Decimal = Field(
        description="Number of shares (supports fractional shares)", gt=0, decimal_places=8
    )
    as_of_date: Optional[date] = Field(
        default_factory=date.today, description="Date of this position snapshot"
    )


class JobCreate(BaseModel):
    """Schema for creating a job - suitable for LLM tool input"""

    clerk_user_id: str = Field(description="User requesting this job")
    job_type: JobType = Field(description="Type of analysis or operation to perform")
    request_payload: Optional[Dict] = Field(None, description="Input parameters for the job")


class JobUpdate(BaseModel):
    """Schema for updating job status - suitable for LLM tool output"""

    status: JobStatus = Field(description="Current status of the job")
    result_payload: Optional[Dict] = Field(None, description="Results of the completed job")
    error_message: Optional[str] = Field(None, description="Error details if job failed")


class PortfolioAnalysis(BaseModel):
    """Schema for portfolio analysis results - LLM structured output"""

    total_value: Decimal = Field(description="Total portfolio value in dollars", decimal_places=2)
    asset_allocation: Dict[AssetClassType, float] = Field(
        description="Current asset class allocation percentages"
    )
    region_allocation: Dict[RegionType, float] = Field(
        description="Current geographic allocation percentages"
    )
    sector_allocation: Dict[SectorType, float] = Field(
        description="Current sector allocation percentages"
    )
    risk_score: int = Field(
        description="Risk score from 1 (conservative) to 10 (aggressive)", ge=1, le=10
    )
    recommendations: List[str] = Field(
        description="List of actionable recommendations for the portfolio"
    )


class RebalanceRecommendation(BaseModel):
    """Schema for rebalancing recommendations - LLM structured output"""

    current_allocation: Dict[str, float] = Field(
        description="Current allocation by instrument symbol"
    )
    target_allocation: Dict[str, float] = Field(
        description="Recommended target allocation by symbol"
    )
    trades: List[Dict] = Field(
        description="List of trades needed to rebalance",
        example=[
            {"symbol": "SPY", "action": "sell", "quantity": 10},
            {"symbol": "BND", "action": "buy", "quantity": 50},
        ],
    )
    rationale: str = Field(description="Explanation of why these changes are recommended")
