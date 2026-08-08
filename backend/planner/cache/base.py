"""
Abstract Market Data Cache Interface for Project Alex.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class CachedPrice:
    symbol: str
    price: float
    volume: int = 0
    updated_at: str = ""
    expires_at_epoch: int = 0
    source: str = "cache"

    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc).isoformat()

    def is_expired(self) -> bool:
        if self.expires_at_epoch == 0:
            return False
        return datetime.now(timezone.utc).timestamp() > self.expires_at_epoch


class BaseMarketDataCache(ABC):
    """Abstract Base Class for Market Data Cache Implementations."""

    @abstractmethod
    def get(self, symbol: str) -> Optional[CachedPrice]:
        """Retrieve cached price for a given ticker symbol."""
        pass

    @abstractmethod
    def set(self, cached_price: CachedPrice) -> bool:
        """Store a price record in the cache."""
        pass

    @abstractmethod
    def get_many(self, symbols: List[str]) -> Dict[str, CachedPrice]:
        """Batch retrieve cached prices for multiple symbols."""
        pass

    @abstractmethod
    def set_many(self, prices: List[CachedPrice]) -> bool:
        """Batch store price records."""
        pass
