#!/usr/bin/env python3
"""
Seed UNLOGGED Market Data Cache for Alex Financial Planner.
Populates the PostgreSQL UNLOGGED market data cache table with initial synthetic ticker entries.
"""

import os
import sys
import time
import random
import argparse

sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
from loguru import logger
from src import Database

# Load environment variables
load_dotenv(override=True)

# Default benchmark ETFs and equities for seed cache data
SYNTHETIC_CACHE_ITEMS = [
    ("SPY", 550.25),
    ("QQQ", 480.10),
    ("IVV", 552.00),
    ("VOO", 505.30),
    ("VTI", 275.40),
    ("BND", 72.85),
    ("AGG", 98.15),
    ("EFA", 78.90),
    ("EEM", 42.50),
    ("IWM", 215.60),
    ("VUG", 370.80),
    ("VTV", 162.30),
    ("VNQ", 88.40),
    ("GLD", 225.10),
    ("TLT", 94.75),
    ("XLF", 44.20),
    ("XLK", 220.50),
    ("XLE", 89.60),
    ("AAPL", 222.50),
    ("MSFT", 445.80),
    ("NVDA", 128.40),
    ("AMZN", 185.30),
]


def seed_market_cache(
    db: Database = None,
    count: int = 20,
    ttl_seconds: int = 86400,
    clear_first: bool = False,
) -> int:
    """
    Seed UNLOGGED market data cache with synthetic price records.

    Args:
        db: Initialized Database instance.
        count: Number of ETF/stock records to seed.
        ttl_seconds: Cache TTL duration in seconds (default: 24 hrs).
        clear_first: If True, truncates cache before seeding.

    Returns:
        Number of successfully inserted cache records.
    """
    if db is None:
        logger.info("Initializing database connection for cache seeding...")
        db = Database()

    if clear_first:
        logger.info("Truncating existing UNLOGGED market data cache table...")
        db.market_cache.truncate()

    now_epoch = int(time.time())
    expires_at_epoch = now_epoch + ttl_seconds

    records = []
    items_to_seed = SYNTHETIC_CACHE_ITEMS[:count]

    for sym, base_price in items_to_seed:
        price_variance = random.uniform(-0.015, 0.015)
        price = round(base_price * (1 + price_variance), 2)
        volume = random.randint(1_000_000, 50_000_000)
        records.append({
            "symbol": sym,
            "price": price,
            "volume": volume,
            "expires_at_epoch": expires_at_epoch,
            "source": "seed_cache",
        })

    logger.info(f"Seeding {len(records)} synthetic cache records into UNLOGGED table...")
    success = db.market_cache.set_prices(records)

    if success:
        total_count = db.market_cache.count()
        active_count = db.market_cache.count(active_only=True)
        logger.info(f"Cache seeding complete: {len(records)} items seeded (Total: {total_count}, Active: {active_count})")
        for rec in records[:5]:
            logger.info(f"  • {rec['symbol']}: ${rec['price']} (Volume: {rec['volume']:,})")
        if len(records) > 5:
            logger.info(f"  ... and {len(records) - 5} more cache items.")
        return len(records)
    else:
        logger.error("Failed to seed market data cache records.")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Seed PostgreSQL UNLOGGED market data cache table with synthetic ETF/stock data."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=20,
        help="Number of synthetic ticker records to seed (default: 20).",
    )
    parser.add_argument(
        "--ttl-seconds",
        type=int,
        default=86400,
        help="TTL duration in seconds for cache expiration (default: 86400 / 24 hrs).",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing cache table before seeding.",
    )

    args = parser.parse_args()
    try:
        seed_market_cache(count=args.count, ttl_seconds=args.ttl_seconds, clear_first=args.clear)
    except Exception as e:
        logger.error(f"Cache seeding failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
