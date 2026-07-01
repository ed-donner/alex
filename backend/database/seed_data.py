#!/usr/bin/env python3
"""
Seed data for Alex Financial Planner
Loads 20+ popular ETF instruments with allocation data
"""

import os
import sys
import json
import boto3

sys.stdout.reconfigure(encoding="utf-8")
from botocore.exceptions import ClientError
from src.schemas import InstrumentCreate
from pydantic import ValidationError
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Get config from environment
cluster_arn = os.environ.get("AURORA_CLUSTER_ARN")
secret_arn = os.environ.get("AURORA_SECRET_ARN")
database = os.environ.get("AURORA_DATABASE", "alex")
region = os.environ.get("DEFAULT_AWS_REGION", "us-east-1")

if not cluster_arn or not secret_arn:
    print("❌ Missing AURORA_CLUSTER_ARN or AURORA_SECRET_ARN in .env file")
    exit(1)

client = boto3.client("rds-data", region_name=region)

# Define popular ETF instruments with realistic allocation data
# All percentages should sum to 100 for each allocation type
INSTRUMENTS = [
    # Core US Equity
    {
        "symbol": "SPY",
        "name": "SPDR S&P 500 ETF Trust",
        "instrument_type": "etf",
        "current_price": 450.25,  # Approximate prices as of 2024
        "allocation_regions": {"north_america": 100},
        "allocation_sectors": {
            "technology": 28,
            "healthcare": 13,
            "financials": 13,
            "consumer_discretionary": 12,
            "industrials": 9,
            "communication": 9,
            "consumer_staples": 6,
            "energy": 4,
            "utilities": 3,
            "real_estate": 2,
            "materials": 1,
        },
        "allocation_asset_class": {"equity": 100},
    },
    {
        "symbol": "QQQ",
        "name": "Invesco QQQ Trust",
        "instrument_type": "etf",
        "current_price": 385.50,
        "allocation_regions": {"north_america": 100},
        "allocation_sectors": {
            "technology": 50,
            "communication": 17,
            "consumer_discretionary": 15,
            "healthcare": 8,
            "consumer_staples": 5,
            "industrials": 3,
            "other": 2,
        },
        "allocation_asset_class": {"equity": 100},
    },
    {
        "symbol": "IWM",
        "name": "iShares Russell 2000 ETF",
        "instrument_type": "etf",
        "current_price": 205.75,
        "allocation_regions": {"north_america": 100},
        "allocation_sectors": {
            "healthcare": 18,
            "financials": 17,
            "industrials": 16,
            "technology": 14,
            "consumer_discretionary": 12,
            "real_estate": 7,
            "energy": 6,
            "materials": 4,
            "consumer_staples": 3,
            "utilities": 2,
            "communication": 1,
        },
        "allocation_asset_class": {"equity": 100},
    },
    # International Equity
    {
        "symbol": "VEA",
        "name": "Vanguard FTSE Developed Markets ETF",
        "instrument_type": "etf",
        "current_price": 48.30,
        "allocation_regions": {"europe": 60, "asia": 35, "oceania": 5},
        "allocation_sectors": {
            "financials": 18,
            "industrials": 14,
            "healthcare": 12,
            "consumer_discretionary": 11,
            "technology": 10,
            "consumer_staples": 9,
            "materials": 8,
            "energy": 6,
            "communication": 5,
            "utilities": 4,
            "real_estate": 3,
        },
        "allocation_asset_class": {"equity": 100},
    },
    {
        "symbol": "VWO",
        "name": "Vanguard FTSE Emerging Markets ETF",
        "instrument_type": "etf",
        "current_price": 42.15,
        "allocation_regions": {"asia": 75, "latin_america": 10, "africa": 8, "europe": 7},
        "allocation_sectors": {
            "technology": 22,
            "financials": 20,
            "consumer_discretionary": 15,
            "communication": 10,
            "energy": 8,
            "materials": 7,
            "industrials": 6,
            "consumer_staples": 5,
            "healthcare": 4,
            "utilities": 2,
            "real_estate": 1,
        },
        "allocation_asset_class": {"equity": 100},
    },
    {
        "symbol": "EFA",
        "name": "iShares MSCI EAFE ETF",
        "instrument_type": "etf",
        "current_price": 75.80,
        "allocation_regions": {"europe": 65, "asia": 35},
        "allocation_sectors": {
            "financials": 17,
            "industrials": 15,
            "healthcare": 13,
            "consumer_discretionary": 12,
            "consumer_staples": 10,
            "technology": 9,
            "materials": 8,
            "energy": 5,
            "communication": 5,
            "utilities": 3,
            "real_estate": 3,
        },
        "allocation_asset_class": {"equity": 100},
    },
    # Fixed Income
    {
        "symbol": "AGG",
        "name": "iShares Core U.S. Aggregate Bond ETF",
        "instrument_type": "bond_fund",
        "current_price": 98.20,
        "allocation_regions": {"north_america": 100},
        "allocation_sectors": {
            "treasury": 40,
            "corporate": 25,
            "mortgage": 28,
            "government_related": 7,
        },
        "allocation_asset_class": {"fixed_income": 100},
    },
    {
        "symbol": "BND",
        "name": "Vanguard Total Bond Market ETF",
        "instrument_type": "bond_fund",
        "current_price": 72.50,
        "allocation_regions": {"north_america": 100},
        "allocation_sectors": {
            "treasury": 42,
            "corporate": 24,
            "mortgage": 27,
            "government_related": 7,
        },
        "allocation_asset_class": {"fixed_income": 100},
    },
    {
        "symbol": "TLT",
        "name": "iShares 20+ Year Treasury Bond ETF",
        "instrument_type": "bond_fund",
        "current_price": 92.30,
        "allocation_regions": {"north_america": 100},
        "allocation_sectors": {"treasury": 100},
        "allocation_asset_class": {"fixed_income": 100},
    },
    {
        "symbol": "HYG",
        "name": "iShares iBoxx High Yield Corporate Bond ETF",
        "instrument_type": "bond_fund",
        "current_price": 76.85,
        "allocation_regions": {"north_america": 95, "international": 5},
        "allocation_sectors": {"corporate": 100},
        "allocation_asset_class": {"fixed_income": 100},
    },
    # Sector ETFs
    {
        "symbol": "XLK",
        "name": "Technology Select Sector SPDR Fund",
        "instrument_type": "etf",
        "current_price": 175.40,
        "allocation_regions": {"north_america": 100},
        "allocation_sectors": {"technology": 100},
        "allocation_asset_class": {"equity": 100},
    },
    {
        "symbol": "XLV",
        "name": "Health Care Select Sector SPDR Fund",
        "instrument_type": "etf",
        "current_price": 135.60,
        "allocation_regions": {"north_america": 100},
        "allocation_sectors": {"healthcare": 100},
        "allocation_asset_class": {"equity": 100},
    },
    {
        "symbol": "XLF",
        "name": "Financial Select Sector SPDR Fund",
        "instrument_type": "etf",
        "current_price": 38.25,
        "allocation_regions": {"north_america": 100},
        "allocation_sectors": {"financials": 100},
        "allocation_asset_class": {"equity": 100},
    },
    {
        "symbol": "XLE",
        "name": "Energy Select Sector SPDR Fund",
        "instrument_type": "etf",
        "current_price": 85.90,
        "allocation_regions": {"north_america": 100},
        "allocation_sectors": {"energy": 100},
        "allocation_asset_class": {"equity": 100},
    },
    # Real Estate
    {
        "symbol": "VNQ",
        "name": "Vanguard Real Estate ETF",
        "instrument_type": "etf",
        "current_price": 82.45,
        "allocation_regions": {"north_america": 100},
        "allocation_sectors": {"real_estate": 100},
        "allocation_asset_class": {"real_estate": 100},
    },
    # Commodities
    {
        "symbol": "GLD",
        "name": "SPDR Gold Shares",
        "instrument_type": "etf",
        "current_price": 195.70,
        "allocation_regions": {"global": 100},
        "allocation_sectors": {"commodities": 100},
        "allocation_asset_class": {"commodities": 100},
    },
    {
        "symbol": "SLV",
        "name": "iShares Silver Trust",
        "instrument_type": "etf",
        "current_price": 22.40,
        "allocation_regions": {"global": 100},
        "allocation_sectors": {"commodities": 100},
        "allocation_asset_class": {"commodities": 100},
    },
    # Mixed/Balanced
    {
        "symbol": "AOR",
        "name": "iShares Core Growth Allocation ETF",
        "instrument_type": "etf",
        "current_price": 48.90,
        "allocation_regions": {"north_america": 60, "international": 40},
        "allocation_sectors": {"diversified": 100},
        "allocation_asset_class": {"equity": 60, "fixed_income": 40},
    },
    {
        "symbol": "AOA",
        "name": "iShares Core Aggressive Allocation ETF",
        "instrument_type": "etf",
        "current_price": 65.15,
        "allocation_regions": {"north_america": 55, "international": 45},
        "allocation_sectors": {"diversified": 100},
        "allocation_asset_class": {"equity": 80, "fixed_income": 20},
    },
    # Growth ETFs
    {
        "symbol": "VUG",
        "name": "Vanguard Growth ETF",
        "instrument_type": "etf",
        "current_price": 312.80,
        "allocation_regions": {"north_america": 100},
        "allocation_sectors": {
            "technology": 45,
            "consumer_discretionary": 18,
            "healthcare": 12,
            "industrials": 10,
            "communication": 8,
            "financials": 4,
            "other": 3,
        },
        "allocation_asset_class": {"equity": 100},
    },
    # Value ETFs
    {
        "symbol": "VTV",
        "name": "Vanguard Value ETF",
        "instrument_type": "etf",
        "current_price": 152.60,
        "allocation_regions": {"north_america": 100},
        "allocation_sectors": {
            "financials": 20,
            "healthcare": 18,
            "industrials": 12,
            "consumer_staples": 11,
            "energy": 10,
            "utilities": 8,
            "communication": 7,
            "materials": 6,
            "technology": 5,
            "other": 3,
        },
        "allocation_asset_class": {"equity": 100},
    },
    # Dividend ETFs
    {
        "symbol": "VIG",
        "name": "Vanguard Dividend Appreciation ETF",
        "instrument_type": "etf",
        "current_price": 168.90,
        "allocation_regions": {"north_america": 100},
        "allocation_sectors": {
            "technology": 22,
            "healthcare": 16,
            "financials": 14,
            "consumer_staples": 13,
            "industrials": 12,
            "consumer_discretionary": 10,
            "utilities": 5,
            "materials": 4,
            "other": 4,
        },
        "allocation_asset_class": {"equity": 100},
    },
]


def insert_instrument(instrument_data):
    """Insert a single instrument into the database with Pydantic validation"""
    # Validate with Pydantic first
    try:
        instrument = InstrumentCreate(**instrument_data)
    except ValidationError as e:
        print(f"    ❌ Validation error: {e}")
        return False

    # Get validated data
    validated = instrument.model_dump()

    sql = """
        INSERT INTO instruments (
            symbol, name, instrument_type, current_price,
            allocation_regions, allocation_sectors, allocation_asset_class
        ) VALUES (
            :symbol, :name, :instrument_type, :current_price::numeric,
            :allocation_regions::jsonb, :allocation_sectors::jsonb, :allocation_asset_class::jsonb
        )
        ON CONFLICT (symbol) DO UPDATE SET
            name = EXCLUDED.name,
            instrument_type = EXCLUDED.instrument_type,
            current_price = EXCLUDED.current_price,
            allocation_regions = EXCLUDED.allocation_regions,
            allocation_sectors = EXCLUDED.allocation_sectors,
            allocation_asset_class = EXCLUDED.allocation_asset_class,
            updated_at = NOW()
    """

    try:
        response = client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=database,
            sql=sql,
            parameters=[
                {"name": "symbol", "value": {"stringValue": validated["symbol"]}},
                {"name": "name", "value": {"stringValue": validated["name"]}},
                {"name": "instrument_type", "value": {"stringValue": validated["instrument_type"]}},
                {
                    "name": "current_price",
                    "value": {"stringValue": str(validated.get("current_price", 0))},
                },
                {
                    "name": "allocation_regions",
                    "value": {"stringValue": json.dumps(validated["allocation_regions"])},
                },
                {
                    "name": "allocation_sectors",
                    "value": {"stringValue": json.dumps(validated["allocation_sectors"])},
                },
                {
                    "name": "allocation_asset_class",
                    "value": {"stringValue": json.dumps(validated["allocation_asset_class"])},
                },
            ],
        )
        return True
    except ClientError as e:
        print(f"    ❌ Error: {e.response['Error']['Message'][:100]}")
        return False


def verify_allocations(instrument):
    """Verify instrument using Pydantic validation"""
    try:
        InstrumentCreate(**instrument)
        return []  # No errors
    except ValidationError as e:
        # Extract error messages
        errors = []
        for error in e.errors():
            field = ".".join(str(x) for x in error["loc"])
            msg = error["msg"]
            errors.append(f"{field}: {msg}")
        return errors


def main():
    print("🚀 Seeding Instrument Data")
    print("=" * 50)
    print(f"Loading {len(INSTRUMENTS)} instruments...")

    # First verify all allocations
    print("\n📊 Verifying allocation data...")
    all_valid = True
    for inst in INSTRUMENTS:
        errors = verify_allocations(inst)
        if errors:
            print(f"  ❌ {inst['symbol']}: {', '.join(errors)}")
            all_valid = False

    if not all_valid:
        print("\n❌ Some instruments have invalid allocations. Please fix before continuing.")
        exit(1)

    print("  ✅ All allocations valid!")

    # Insert instruments
    print("\n💾 Inserting instruments...")
    success_count = 0

    for inst in INSTRUMENTS:
        print(
            f"  [{success_count + 1}/{len(INSTRUMENTS)}] {inst['symbol']}: {inst['name'][:40]}..."
        )
        if insert_instrument(inst):
            print(f"    ✅ Success")
            success_count += 1
        else:
            print(f"    ❌ Failed")

    print("\n" + "=" * 50)
    print(f"Seeding complete: {success_count}/{len(INSTRUMENTS)} instruments loaded")

    # Verify by querying
    print("\n🔍 Verifying data...")
    try:
        response = client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=database,
            sql="SELECT COUNT(*) as count FROM instruments",
        )
        count = response["records"][0][0]["longValue"]
        print(f"  Database now contains {count} instruments")

        # Show a sample
        response = client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=database,
            sql="SELECT symbol, name FROM instruments ORDER BY symbol LIMIT 5",
        )

        print("\n  Sample instruments:")
        for record in response["records"]:
            symbol = record[0]["stringValue"]
            name = record[1]["stringValue"]
            print(f"    - {symbol}: {name}")

    except ClientError as e:
        print(f"  ❌ Error verifying: {e}")

    print("\n✅ Seed data loaded successfully!")
    print("\n📝 Next steps:")
    print("1. Create test user and portfolio: uv run create_test_data.py")
    print("2. Test database operations: uv run test_db.py")


if __name__ == "__main__":
    main()
