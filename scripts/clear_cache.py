#!/usr/bin/env bash
''':'
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PY="$PROJECT_ROOT/backend/.venv/bin/python"

if [ -f "$VENV_PY" ]; then
    exec "$VENV_PY" "$0" "$@"
else
    exec uv run --directory "$PROJECT_ROOT/backend" python "$0" "$@"
fi
':'''
from typing import Any

"""
Manual Cache Cleanup Utility for Project Alex.
Clears or purges records from the PostgreSQL UNLOGGED market data cache table.
"""

import sys
import argparse
from pathlib import Path

# Add project root, backend, and database to sys.path
PROJECT_ROOT = Path(__file__).parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
DATABASE_DIR = BACKEND_DIR / "database"

for path in (PROJECT_ROOT, BACKEND_DIR, DATABASE_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dotenv import load_dotenv
from loguru import logger
from src import Database

# Load environment variables from .env
load_dotenv(PROJECT_ROOT / ".env", override=True)

def get_cache_stats(db) -> dict:
    count = db.market_cache.count()
    active_count = db.market_cache.count(active_only=True)
    return {"total": count, "active": active_count}


def clear_cache(
    db: Any,
    expired_only: bool = False,
    symbol: str = None
) -> None:
    """
    Clear or purge entries from the market_data_cache UNLOGGED table.
    """
    pre_stats = get_cache_stats(db)
    logger.info(f"Current cache state: {pre_stats['total']} total records ({pre_stats['active']} active)")

    if symbol:
        symbol_upper = symbol.upper()
        logger.info(f"Purging cache entry for symbol: {symbol_upper}")
        deleted = db.market_cache.delete("symbol = :symbol", {"symbol": symbol_upper})
        logger.info(f"Purged cache entry for '{symbol_upper}' (Records updated: {deleted})")
    elif expired_only:
        logger.info("Purging expired entries from UNLOGGED market_data_cache table...")
        deleted = db.market_cache.delete_expired()
        logger.info(f"Expired cache cleanup complete (Purged {deleted} records)")
    else:
        logger.info("Truncating UNLOGGED market_data_cache table...")
        db.market_cache.truncate()
        logger.info("Market data cache table truncated successfully!")

    post_stats = get_cache_stats(db)
    logger.info(f"Post-cleanup cache state: {post_stats['total']} total records ({post_stats['active']} active)")


def init_db():
    logger.info("Initializing database connection for cache cleanup...")
    return Database()


def main():
    parser = argparse.ArgumentParser(
        description="Clear or purge records from the PostgreSQL UNLOGGED market data cache table."
    )
    parser.add_argument(
        "--expired-only",
        action="store_true",
        help="Purge only expired TTL cache records instead of truncating the entire table.",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Clear cache entry for a specific stock ticker symbol (e.g. --symbol AAPL).",
    )

    args = parser.parse_args()
    try:
        db = init_db()
        clear_cache(
            db=db,
            expired_only=args.expired_only,
            symbol=args.symbol
        )
    except Exception as e:
        logger.error(f"Failed to clear market data cache: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
