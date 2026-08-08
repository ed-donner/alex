"""
Cache Factory Module for Project Alex.
Dynamically instantiates L1 / L2 market cache providers.
"""

import os
import logging
from cache.base import BaseMarketDataCache
from cache.memory import MemoryMarketCache
from cache.postgres import PostgresUnloggedCache
from cache.dynamodb import DynamoDBMarketCache

logger = logging.getLogger(__name__)


_cache_instance = None


def get_market_cache(cache_type: str = None, db_client = None) -> BaseMarketDataCache:
    """
    Factory function returning the configured market data cache implementation.

    Args:
        cache_type: 'memory', 'postgres', 'dynamodb' (Defaults to MARKET_CACHE_PROVIDER env var or 'memory')
        db_client: Database client required if cache_type == 'postgres'

    Returns:
        Instance of BaseMarketDataCache
    """
    global _cache_instance

    if _cache_instance is not None and cache_type is None and db_client is None:
        return _cache_instance

    provider = (cache_type or os.getenv("MARKET_CACHE_PROVIDER", "memory")).lower()

    if provider == "postgres":
        if not db_client:
            logger.warning("Postgres cache requested without db_client, falling back to MemoryMarketCache")
            instance = MemoryMarketCache()
        else:
            logger.info("Initializing PostgresUnloggedCache provider")
            instance = PostgresUnloggedCache(db_client)

    elif provider == "dynamodb":
        try:
            logger.info("Initializing DynamoDBMarketCache provider")
            instance = DynamoDBMarketCache()
        except Exception as e:
            logger.warning(f"Failed to initialize DynamoDBMarketCache ({e}), falling back to MemoryMarketCache")
            instance = MemoryMarketCache()

    else:
        logger.info("Initializing MemoryMarketCache provider")
        instance = MemoryMarketCache()

    if cache_type is None and db_client is None:
        _cache_instance = instance

    return instance

