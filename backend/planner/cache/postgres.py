"""
PostgreSQL UNLOGGED Table Market Data Cache Provider for Project Alex.
Integrates with Aurora Serverless v2 PostgreSQL Data API via UnloggedMarketCacheStore.
"""

import logging
from typing import Optional, Dict, List
from cache.base import BaseMarketDataCache, CachedPrice
from src.unlogged import UnloggedMarketCacheStore

logger = logging.getLogger(__name__)


class PostgresUnloggedCache(BaseMarketDataCache):
    """PostgreSQL UNLOGGED Table Implementation of Market Data Cache."""

    def __init__(self, db_client, table_name: str = "market_data_cache"):
        if isinstance(db_client, UnloggedMarketCacheStore):
            self.store = db_client
        else:
            self.store = UnloggedMarketCacheStore(db_client, table_name=table_name)
        self.table_name = self.store.table_name

    def get(self, symbol: str) -> Optional[CachedPrice]:
        try:
            row = self.store.get_price(symbol)
            if not row:
                return None

            return CachedPrice(
                symbol=row["symbol"],
                price=float(row["current_price"]),
                volume=int(row.get("volume", 0)),
                updated_at=str(row["updated_at"]),
                expires_at_epoch=int(row["expires_at_epoch"]),
                source=row.get("source", "postgres_unlogged")
            )
        except Exception as e:
            logger.error(f"Postgres Cache Get Error for {symbol}: {e}")
            return None

    def set(self, cached_price: CachedPrice) -> bool:
        try:
            return self.store.set_price(
                symbol=cached_price.symbol.upper(),
                price=cached_price.price,
                volume=cached_price.volume,
                updated_at=cached_price.updated_at,
                expires_at_epoch=cached_price.expires_at_epoch,
                source=cached_price.source or "postgres_unlogged"
            )
        except Exception as e:
            logger.error(f"Postgres Cache Set Error for {cached_price.symbol}: {e}")
            return False

    def get_many(self, symbols: List[str]) -> Dict[str, CachedPrice]:
        results = {}
        if not symbols:
            return results
        rows = self.store.get_prices(symbols)
        for row in rows:
            sym = row["symbol"].upper()
            results[sym] = CachedPrice(
                symbol=sym,
                price=float(row["current_price"]),
                volume=int(row.get("volume", 0)),
                updated_at=str(row["updated_at"]),
                expires_at_epoch=int(row["expires_at_epoch"]),
                source=row.get("source", "postgres_unlogged")
            )
        return results

    def set_many(self, prices: List[CachedPrice]) -> bool:
        return self.store.set_prices([
            {
                "symbol": p.symbol,
                "price": p.price,
                "volume": p.volume,
                "updated_at": p.updated_at,
                "expires_at_epoch": p.expires_at_epoch,
                "source": p.source or "postgres_unlogged"
            }
            for p in prices
        ])

    def count(self, active_only: bool = False) -> int:
        """Return row count from the PostgreSQL UNLOGGED cache."""
        return self.store.count(active_only=active_only)

