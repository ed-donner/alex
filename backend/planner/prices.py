"""
Market data fetching and caching layer for Project Alex.
Integrates Polygon.io API with L1/L2 cache submodule.
"""

import os
import random
import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional, Dict

from dotenv import load_dotenv
from polygon import RESTClient

from cache import get_market_cache, CachedPrice

load_dotenv(override=True)

logger = logging.getLogger(__name__)

polygon_api_key = os.getenv("POLYGON_API_KEY")
polygon_plan = os.getenv("POLYGON_PLAN")

is_paid_polygon = polygon_plan == "paid"


def get_default_ttl_seconds() -> int:
    """Calculate cache TTL based on market trading hours and Polygon API tier."""
    now = datetime.now(timezone.utc)
    # Weekend check (Saturday = 5, Sunday = 6)
    if now.weekday() >= 5:
        return 86400  # 24 hours on weekends

    if is_paid_polygon:
        return 900  # 15 minutes for real-time snapshots
    else:
        return 3600  # 1 hour for free tier EOD data


def is_market_open() -> bool:
    if not polygon_api_key:
        return False
    try:
        client = RESTClient(polygon_api_key)
        market_status = client.get_market_status()
        return getattr(market_status, "market", "") == "open"
    except Exception as e:
        logger.warning(f"Could not fetch market status: {e}")
        return False


def get_all_share_prices_polygon_eod() -> dict[str, float]:
    """With much thanks to student Reema R. for fixing the timezone issue with this!"""
    if not polygon_api_key:
        raise ValueError("POLYGON_API_KEY environment variable is missing")
    client = RESTClient(polygon_api_key)

    probe = client.get_previous_close_agg("SPY")[0]
    last_close = datetime.fromtimestamp(probe.timestamp / 1000, tz=timezone.utc).date()

    results = client.get_grouped_daily_aggs(last_close, adjusted=True, include_otc=False)
    price_dict = {
        result.ticker: float(result.close)
        for result in results
        if getattr(result, "close", None) is not None
    }

    # Populate cache
    cache = get_market_cache()
    now_dt = datetime.now(timezone.utc)
    ttl = get_default_ttl_seconds()
    expires_epoch = int(now_dt.timestamp()) + ttl
    iso_now = now_dt.isoformat()

    cached_prices = [
        CachedPrice(
            symbol=ticker.upper(),
            price=price,
            volume=0,
            updated_at=iso_now,
            expires_at_epoch=expires_epoch,
            source="polygon_eod",
        )
        for ticker, price in price_dict.items()
    ]
    cache.set_many(cached_prices)
    return price_dict


@lru_cache(maxsize=2)
def get_market_for_prior_date(today):
    market_data = get_all_share_prices_polygon_eod()
    return market_data


def get_share_price_polygon_eod(symbol: str) -> float:
    symbol_upper = symbol.upper()
    today = datetime.now().date().strftime("%Y-%m-%d")
    market_data = get_market_for_prior_date(today)
    return market_data.get(symbol_upper, 0.0)


def get_share_price_polygon_min(symbol: str) -> float:
    if not polygon_api_key:
        raise ValueError("POLYGON_API_KEY environment variable is missing")
    client = RESTClient(polygon_api_key)
    result = client.get_snapshot_ticker("stocks", symbol.upper())
    price = result.min.close or result.prev_day.close
    if not price or float(price) <= 0:
        raise ValueError(f"Invalid price received for {symbol}: {price}")
    return float(price)


def get_share_price_polygon(symbol: str) -> float:
    if is_paid_polygon:
        return get_share_price_polygon_min(symbol)
    else:
        return get_share_price_polygon_eod(symbol)


def get_share_price(symbol: str) -> float:
    """
    Get share price with cache lookup before invoking Polygon API.
    Falls back gracefully to a random mock price if API fails.
    """
    if not symbol:
        return 0.0

    symbol_upper = symbol.upper()
    cache = get_market_cache()

    # Tier 1 & Tier 2 Cache Lookup
    cached_entry = cache.get(symbol_upper)
    if cached_entry and not cached_entry.is_expired():
        logger.info(f"[CACHE HIT] {symbol_upper}: ${cached_entry.price:.2f} (Source: {cached_entry.source})")
        return cached_entry.price

    # Cache Miss - Call Polygon API
    logger.info(f"[CACHE MISS] Fetching {symbol_upper} from Polygon API...")
    if polygon_api_key:
        try:
            price = get_share_price_polygon(symbol_upper)
            if price and price > 0:
                now_dt = datetime.now(timezone.utc)
                ttl_seconds = get_default_ttl_seconds()
                expires_epoch = int(now_dt.timestamp()) + ttl_seconds
                iso_now = now_dt.isoformat()

                record = CachedPrice(
                    symbol=symbol_upper,
                    price=price,
                    volume=0,
                    updated_at=iso_now,
                    expires_at_epoch=expires_epoch,
                    source="polygon_api",
                )
                cache.set(record)
                return price
        except Exception as e:
            print(f"Was not able to use the polygon API due to {e}; using a random number")
            logger.warning(f"Was not able to use the polygon API for {symbol_upper} due to {e}; using a random number")

    # Fallback to random number
    mock_price = float(random.randint(1, 100))
    logger.info(f"[FALLBACK] Generated mock price for {symbol_upper}: ${mock_price:.2f}")

    # Cache fallback mock price
    now_dt = datetime.now(timezone.utc)
    ttl_seconds = get_default_ttl_seconds()
    expires_epoch = int(now_dt.timestamp()) + ttl_seconds
    record = CachedPrice(
        symbol=symbol_upper,
        price=mock_price,
        volume=0,
        updated_at=now_dt.isoformat(),
        expires_at_epoch=expires_epoch,
        source="fallback_mock",
    )
    cache.set(record)

    return mock_price

