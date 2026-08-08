"""
In-Memory Market Data Cache Provider for Project Alex.
Utilizes in-process memory with configurable TTL.
"""

import time
import logging
from typing import Optional, Dict, List
from datetime import datetime, timezone
from cache.base import BaseMarketDataCache, CachedPrice

logger = logging.getLogger(__name__)


class MemoryMarketCache(BaseMarketDataCache):
    """In-Process Memory Implementation of Market Data Cache."""

    def __init__(self, default_ttl_seconds: int = 300):
        self.default_ttl = default_ttl_seconds
        self._store: Dict[str, CachedPrice] = {}

    def get(self, symbol: str) -> Optional[CachedPrice]:
        sym = symbol.upper()
        cached = self._store.get(sym)
        if not cached:
            return None
        if cached.is_expired():
            del self._store[sym]
            return None
        return cached

    def set(self, cached_price: CachedPrice) -> bool:
        sym = cached_price.symbol.upper()
        if cached_price.expires_at_epoch == 0:
            cached_price.expires_at_epoch = int(time.time()) + self.default_ttl
        cached_price.source = "memory"
        self._store[sym] = cached_price
        return True

    def get_many(self, symbols: List[str]) -> Dict[str, CachedPrice]:
        results = {}
        for sym in symbols:
            cached = self.get(sym)
            if cached:
                results[sym.upper()] = cached
        return results

    def set_many(self, prices: List[CachedPrice]) -> bool:
        for p in prices:
            self.set(p)
        return True

    def clear(self):
        self._store.clear()
