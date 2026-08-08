"""
PostgreSQL UNLOGGED Table Store implementation for Project Alex.
Provides DataAPIClient backed store interfaces:
- UnloggedTableStore: Generic database interface for UNLOGGED tables
- UnloggedMarketCacheStore: Domain-specific store for market data caching
"""

import time
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class UnloggedTableStore:
    """
    Generic store interface for PostgreSQL UNLOGGED tables using DataAPIClient.
    Bypasses Write-Ahead Logging (WAL) for high-performance ephemeral table operations.
    """

    def __init__(self, db_client: Any, table_name: str):
        """
        Initialize the UNLOGGED table store.

        Args:
            db_client: DataAPIClient instance or Database wrapper object
            table_name: Name of the target UNLOGGED table
        """
        if hasattr(db_client, "client") and hasattr(getattr(db_client, "client"), "execute"):
            self.db = db_client.client
        else:
            self.db = db_client
        self.table_name = table_name

    def _build_params(self, params_dict: Optional[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """Convert a parameter dictionary to Data API format if required."""
        if not params_dict:
            return None
        if hasattr(self.db, "_build_parameters") and callable(self.db._build_parameters):
            return self.db._build_parameters(params_dict)
        return params_dict

    def query(self, sql: str, params_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as list of column dictionaries.
        """
        params = self._build_params(params_dict)
        if hasattr(self.db, "query") and callable(self.db.query):
            return self.db.query(sql, params)
        elif hasattr(self.db, "execute") and callable(self.db.execute):
            resp = self.db.execute(sql, params)
            if isinstance(resp, list):
                return resp
            return resp.get("records", []) if isinstance(resp, dict) else []
        return []

    def query_one(self, sql: str, params_dict: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Execute a SELECT query and return the first row dictionary or None.
        """
        results = self.query(sql, params_dict)
        return results[0] if results else None

    def execute(self, sql: str, params_dict: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a SQL statement (INSERT, UPDATE, DELETE, CREATE, etc.).
        """
        params = self._build_params(params_dict)
        if hasattr(self.db, "execute") and callable(self.db.execute):
            return self.db.execute(sql, params)
        return None

    def insert(self, data: Dict[str, Any], returning: Optional[str] = None) -> Any:
        """
        Insert a row into the UNLOGGED table.
        """
        if hasattr(self.db, "insert") and callable(self.db.insert):
            return self.db.insert(self.table_name, data, returning=returning)

        columns = list(data.keys())
        placeholders = [f":{c}" for c in columns]
        sql = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        if returning:
            sql += f" RETURNING {returning}"
        return self.execute(sql, data)

    def delete(self, where: str, where_params: Optional[Dict[str, Any]] = None) -> int:
        """
        Delete matching records from the UNLOGGED table.
        """
        if hasattr(self.db, "delete") and callable(self.db.delete):
            return self.db.delete(self.table_name, where, where_params)

        sql = f"DELETE FROM {self.table_name} WHERE {where}"
        resp = self.execute(sql, where_params)
        if isinstance(resp, dict):
            return resp.get("numberOfRecordsUpdated", 0)
        return 0

    def count(self, where: Optional[str] = None, where_params: Optional[Dict[str, Any]] = None) -> int:
        """
        Count rows in the UNLOGGED table.

        Args:
            where: Optional WHERE clause filter string (e.g. "expires_at_epoch > :now_epoch").
            where_params: Optional parameter dictionary for WHERE clause.

        Returns:
            Integer row count.
        """
        sql = f"SELECT COUNT(*) AS cnt FROM {self.table_name}"
        if where:
            sql += f" WHERE {where}"
        try:
            row = self.query_one(sql, where_params)
            if row and "cnt" in row:
                return int(row["cnt"])
            return 0
        except Exception as e:
            logger.error(
                f"UNLOGGED table '{self.table_name}' error during count: {e}. "
                "Ensure the UNLOGGED table is created and accessible."
            )
            return 0

    def truncate(self) -> Any:
        """
        Truncate all rows in the UNLOGGED table.
        """
        return self.execute(f"TRUNCATE TABLE {self.table_name}")


class UnloggedTableError(Exception):
    """Exception raised when an operation on a PostgreSQL UNLOGGED table fails."""
    pass


class UnloggedMarketCacheStore(UnloggedTableStore):
    """
    PostgreSQL UNLOGGED Table interface specifically for Market Data Cache storage.
    Handles point lookups, batch lookups, count queries, and upsert operations with explicit error logging.
    """

    def __init__(self, db_client: Any, table_name: str = "market_data_cache"):
        super().__init__(db_client, table_name=table_name)

    def count(self, active_only: bool = False, now_epoch: Optional[int] = None) -> int:
        """
        Count total or active non-expired rows in the UNLOGGED market data cache table.

        Args:
            active_only: If True, count only non-expired cache entries (expires_at_epoch > now_epoch).
            now_epoch: Optional UNIX epoch timestamp in seconds for expiry check.

        Returns:
            Integer row count.
        """
        if active_only:
            if now_epoch is None:
                now_epoch = int(time.time())
            return super().count("expires_at_epoch > :now_epoch", {"now_epoch": now_epoch})
        return super().count()

    def get_price(self, symbol: str, now_epoch: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Fetch non-expired price record for a symbol.

        Args:
            symbol: Ticker symbol
            now_epoch: UNIX epoch timestamp in seconds for expiry check (defaults to current time)

        Returns:
            Dict containing price record fields, or None if not found/expired
        """
        if now_epoch is None:
            now_epoch = int(time.time())

        sql = f"""
            SELECT symbol, price AS current_price, volume, updated_at, expires_at_epoch
            FROM {self.table_name}
            WHERE symbol = :symbol AND expires_at_epoch > :now_epoch
        """
        try:
            return self.query_one(sql, {"symbol": symbol.upper(), "now_epoch": now_epoch})
        except Exception as e:
            logger.error(
                f"UNLOGGED table '{self.table_name}' error during get_price for '{symbol}': {e}. "
                "Ensure the UNLOGGED table is created and accessible."
            )
            return None

    def set_price(
        self,
        symbol: str,
        price: float,
        volume: int = 0,
        updated_at: Optional[Any] = None,
        expires_at_epoch: Optional[int] = None,
        source: str = "postgres_unlogged",
    ) -> bool:
        """
        Upsert a price record into the UNLOGGED cache table.

        Returns:
            True on success, False on failure
        """
        if isinstance(updated_at, (int, float)) and expires_at_epoch is None:
            expires_at_epoch = int(updated_at)

        if expires_at_epoch is None:
            expires_at_epoch = int(time.time()) + 86400

        sql = f"""
            INSERT INTO {self.table_name}
            (symbol, price, volume, updated_at, expires_at_epoch)
            VALUES (:symbol, :price, :volume, NOW(), :expires_at_epoch)
            ON CONFLICT (symbol) DO UPDATE SET
                price = EXCLUDED.price,
                volume = EXCLUDED.volume,
                updated_at = NOW(),
                expires_at_epoch = EXCLUDED.expires_at_epoch
        """
        params = {
            "symbol": symbol.upper(),
            "price": float(price),
            "volume": int(volume),
            "expires_at_epoch": int(expires_at_epoch),
        }
        try:
            self.execute(sql, params)
            return True
        except Exception as e:
            logger.error(
                f"UNLOGGED table '{self.table_name}' error during set_price for '{symbol}': {e}. "
                "Ensure the UNLOGGED table is created and accessible."
            )
            return False

    def get_prices(self, symbols: List[str], now_epoch: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch non-expired price records for a list of symbols.
        """
        if not symbols:
            return []
        if now_epoch is None:
            now_epoch = int(time.time())

        results = []
        try:
            for sym in symbols:
                row = self.get_price(sym, now_epoch)
                if row:
                    results.append(row)
        except Exception as e:
            logger.error(
                f"UNLOGGED table '{self.table_name}' error during get_prices: {e}. "
                "Ensure the UNLOGGED table is created and accessible."
            )
        return results

    def set_prices(self, prices: List[Dict[str, Any]]) -> bool:
        """
        Batch set price records into the UNLOGGED cache table.
        """
        success = True
        for item in prices:
            ok = self.set_price(
                symbol=item["symbol"],
                price=item["price"],
                volume=item.get("volume", 0),
                expires_at_epoch=item["expires_at_epoch"],
                source=item.get("source", "postgres_unlogged"),
            )
            if not ok:
                success = False
        return success

    def delete_expired(self, now_epoch: Optional[int] = None) -> int:
        """
        Purge expired cache entries.
        """
        if now_epoch is None:
            now_epoch = int(time.time())
        try:
            return self.delete("expires_at_epoch <= :now_epoch", {"now_epoch": now_epoch})
        except Exception as e:
            logger.error(
                f"UNLOGGED table '{self.table_name}' error during delete_expired: {e}. "
                "Ensure the UNLOGGED table is created and accessible."
            )
            return 0
