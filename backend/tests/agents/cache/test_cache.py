"""
Comprehensive Pytest Coverage for planner.cache Submodule and Unlogged Stores.
"""

import sys
import time
from pathlib import Path

planner_dir = str(Path(__file__).parents[3] / "planner")
if planner_dir not in sys.path:
    sys.path.insert(0, planner_dir)

import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from cache.base import CachedPrice, BaseMarketDataCache
from cache.memory import MemoryMarketCache
from cache.postgres import PostgresUnloggedCache
from cache.dynamodb import DynamoDBMarketCache
from cache.factory import get_market_cache
import cache.factory as factory_module
from src.unlogged import UnloggedTableStore, UnloggedMarketCacheStore


# ============================================================================
# 1. MemoryMarketCache Tests
# ============================================================================

def test_memory_cache_set_get():
    cache = MemoryMarketCache(default_ttl_seconds=300)
    price = CachedPrice(symbol="aapl", price=185.50, volume=100000)

    assert cache.set(price) is True
    retrieved = cache.get("AAPL")

    assert retrieved is not None
    assert retrieved.symbol == "aapl"  # Keeps original case in object, key in store is upper
    assert retrieved.price == 185.50
    assert retrieved.volume == 100000
    assert retrieved.source == "memory"
    assert retrieved.expires_at_epoch > 0

    assert cache.get("NONEXISTENT") is None


def test_memory_cache_get_many_set_many():
    cache = MemoryMarketCache(default_ttl_seconds=300)
    prices = [
        CachedPrice(symbol="AAPL", price=185.50),
        CachedPrice(symbol="MSFT", price=410.20),
    ]

    assert cache.set_many(prices) is True

    batch = cache.get_many(["aapl", "MSFT", "GOOGL"])
    assert "AAPL" in batch
    assert "MSFT" in batch
    assert "GOOGL" not in batch
    assert batch["AAPL"].price == 185.50
    assert batch["MSFT"].price == 410.20


def test_memory_cache_ttl_expiration():
    cache = MemoryMarketCache(default_ttl_seconds=1)
    expired_price = CachedPrice(
        symbol="EXPIRED",
        price=100.0,
        expires_at_epoch=int(time.time()) - 10
    )
    cache.set(expired_price)

    assert cache.get("EXPIRED") is None
    assert "EXPIRED" not in cache._store


def test_memory_cache_cached_price_is_expired():
    future_price = CachedPrice(symbol="TSLA", price=200.0, expires_at_epoch=int(time.time()) + 100)
    assert future_price.is_expired() is False

    no_ttl_price = CachedPrice(symbol="TSLA", price=200.0, expires_at_epoch=0)
    assert no_ttl_price.is_expired() is False

    past_price = CachedPrice(symbol="TSLA", price=200.0, expires_at_epoch=int(time.time()) - 10)
    assert past_price.is_expired() is True


def test_memory_cache_clear():
    cache = MemoryMarketCache()
    cache.set(CachedPrice(symbol="AAPL", price=150.0))
    assert len(cache._store) == 1
    cache.clear()
    assert len(cache._store) == 0


# ============================================================================
# 2. PostgresUnloggedCache & UnloggedMarketCacheStore Tests
# ============================================================================

class MockDataAPIClient:
    def __init__(self):
        self.store = {}
        self.last_executed_sql = None
        self.last_executed_params = None

    def _build_parameters(self, data):
        return data

    def execute(self, sql, params=None):
        self.last_executed_sql = sql
        self.last_executed_params = params
        if "INSERT INTO" in sql and params:
            sym = params["symbol"]
            self.store[sym] = {
                "symbol": sym,
                "current_price": params["price"],
                "volume": params["volume"],
                "updated_at": params.get("updated_at", "2026-08-04T00:00:00Z"),
                "expires_at_epoch": params["expires_at_epoch"],
                "source": params.get("source", "postgres_unlogged"),
            }
            return {"numberOfRecordsUpdated": 1}
        elif "DELETE FROM" in sql:
            return {"numberOfRecordsUpdated": 2}
        return {}

    def query(self, sql, params=None):
        self.last_executed_sql = sql
        self.last_executed_params = params
        if "SELECT" in sql and params:
            sym = params.get("symbol")
            now_epoch = params.get("now_epoch", 0)
            if sym and sym in self.store:
                row = self.store[sym]
                if row["expires_at_epoch"] > now_epoch:
                    return [row]
        return []


def test_postgres_unlogged_cache_set_get():
    mock_db = MockDataAPIClient()
    pg_cache = PostgresUnloggedCache(mock_db)

    price = CachedPrice(
        symbol="GOOGL",
        price=175.25,
        volume=50000,
        expires_at_epoch=int(time.time()) + 300,
        source="postgres_unlogged"
    )

    assert pg_cache.set(price) is True
    retrieved = pg_cache.get("googl")

    assert retrieved is not None
    assert retrieved.symbol == "GOOGL"
    assert retrieved.price == 175.25
    assert retrieved.volume == 50000
    assert retrieved.source == "postgres_unlogged"

    assert pg_cache.get("NONEXISTENT") is None


def test_postgres_unlogged_cache_get_many_set_many():
    mock_db = MockDataAPIClient()
    pg_cache = PostgresUnloggedCache(mock_db)

    prices = [
        CachedPrice(symbol="NVDA", price=120.0, expires_at_epoch=int(time.time()) + 300),
        CachedPrice(symbol="AMD", price=150.0, expires_at_epoch=int(time.time()) + 300),
    ]

    assert pg_cache.set_many(prices) is True
    batch = pg_cache.get_many(["nvda", "amd", "INTC"])

    assert "NVDA" in batch
    assert "AMD" in batch
    assert "INTC" not in batch
    assert batch["NVDA"].price == 120.0


def test_postgres_unlogged_cache_exceptions():
    mock_db = MagicMock()
    mock_db.client = None
    mock_db.query.side_effect = Exception("DB connection error")
    mock_db.execute.side_effect = Exception("DB insert error")

    pg_cache = PostgresUnloggedCache(mock_db)
    assert pg_cache.get("AAPL") is None
    assert pg_cache.set(CachedPrice(symbol="AAPL", price=150.0)) is False


def test_unlogged_market_cache_store_purge_expired_and_error_handling():
    mock_db = MockDataAPIClient()
    store = UnloggedMarketCacheStore(mock_db, table_name="custom_market_cache")

    deleted_count = store.delete_expired(now_epoch=10000)
    assert deleted_count == 2
    assert "DELETE FROM custom_market_cache WHERE expires_at_epoch <= :now_epoch" in mock_db.last_executed_sql
    assert mock_db.last_executed_params == {"now_epoch": 10000}

    # Verify error handling when DB raises an exception
    failing_db = MagicMock()
    failing_db.client = None
    failing_db.query.side_effect = Exception("Relation 'custom_market_cache' does not exist")
    failing_db.execute.side_effect = Exception("Relation 'custom_market_cache' does not exist")
    failing_db.delete.side_effect = Exception("Relation 'custom_market_cache' does not exist")
    err_store = UnloggedMarketCacheStore(failing_db, table_name="custom_market_cache")

    assert err_store.get_price("AAPL") is None
    assert err_store.set_price("AAPL", 150.0, 1000, "2026-08-04T00:00:00Z", 20000) is False
    assert err_store.get_prices(["AAPL"]) == []
    assert err_store.delete_expired() == 0
    assert err_store.count() == 0


def test_unlogged_market_cache_store_count():
    mock_db = MagicMock()
    mock_db.client = None
    mock_db.query.return_value = [{"cnt": 42}]

    store = UnloggedMarketCacheStore(mock_db, table_name="custom_market_cache")
    assert store.count() == 42
    assert store.count(active_only=True, now_epoch=1000) == 42

    pg_cache = PostgresUnloggedCache(store)
    assert pg_cache.count() == 42


# ============================================================================
# 3. DynamoDBMarketCache Tests
# ============================================================================

@patch("boto3.resource")
def test_dynamodb_market_cache_set_get(mock_boto_resource):
    mock_table = MagicMock()
    mock_boto_resource.return_value.Table.return_value = mock_table

    future_epoch = int(time.time()) + 300
    mock_table.get_item.return_value = {
        "Item": {
            "symbol": "AMZN",
            "price": "180.5",
            "volume": 1234,
            "updated_at": "2026-08-04T00:00:00Z",
            "ttl": future_epoch,
            "source": "dynamodb"
        }
    }

    dynamo_cache = DynamoDBMarketCache(table_name="test-table", region_name="us-west-2")
    retrieved = dynamo_cache.get("amzn")

    assert retrieved is not None
    assert retrieved.symbol == "AMZN"
    assert retrieved.price == 180.5
    assert retrieved.volume == 1234
    assert retrieved.source == "dynamodb"
    mock_table.get_item.assert_called_with(Key={"symbol": "AMZN"})

    # Test set
    price = CachedPrice(symbol="AMZN", price=180.5, volume=1234, expires_at_epoch=future_epoch)
    assert dynamo_cache.set(price) is True
    mock_table.put_item.assert_called_once()


@patch("boto3.resource")
def test_dynamodb_market_cache_expired_and_missing(mock_boto_resource):
    mock_table = MagicMock()
    mock_boto_resource.return_value.Table.return_value = mock_table

    dynamo_cache = DynamoDBMarketCache()

    # Expired item client-side check
    past_epoch = int(time.time()) - 100
    mock_table.get_item.return_value = {
        "Item": {
            "symbol": "AMZN",
            "price": "180.5",
            "volume": 1234,
            "updated_at": "2026-08-04T00:00:00Z",
            "ttl": past_epoch,
            "source": "dynamodb"
        }
    }
    assert dynamo_cache.get("AMZN") is None

    # Missing item
    mock_table.get_item.return_value = {}
    assert dynamo_cache.get("MISSING") is None


@patch("boto3.resource")
def test_dynamodb_market_cache_client_error(mock_boto_resource):
    mock_table = MagicMock()
    mock_boto_resource.return_value.Table.return_value = mock_table
    error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}}
    client_err = ClientError(error_response, "GetItem")

    mock_table.get_item.side_effect = client_err
    mock_table.put_item.side_effect = client_err

    dynamo_cache = DynamoDBMarketCache()
    assert dynamo_cache.get("AMZN") is None
    assert dynamo_cache.set(CachedPrice(symbol="AMZN", price=180.0)) is False


@patch("boto3.resource")
def test_dynamodb_market_cache_get_many_set_many(mock_boto_resource):
    mock_dynamo = MagicMock()
    mock_table = MagicMock()
    mock_boto_resource.return_value = mock_dynamo
    mock_dynamo.Table.return_value = mock_table

    future_epoch = int(time.time()) + 300
    past_epoch = int(time.time()) - 300

    mock_dynamo.batch_get_item.return_value = {
        "Responses": {
            "alex-market-data-cache": [
                {
                    "symbol": "AAPL",
                    "price": "185.0",
                    "volume": 10,
                    "updated_at": "2026-08-04",
                    "ttl": future_epoch,
                    "source": "dynamodb"
                },
                {
                    "symbol": "EXPIRED",
                    "price": "50.0",
                    "volume": 5,
                    "updated_at": "2026-08-04",
                    "ttl": past_epoch,
                    "source": "dynamodb"
                }
            ]
        }
    }

    dynamo_cache = DynamoDBMarketCache()
    batch = dynamo_cache.get_many(["AAPL", "EXPIRED"])
    assert "AAPL" in batch
    assert "EXPIRED" not in batch

    # Batch set
    mock_batch_writer = MagicMock()
    mock_table.batch_writer.return_value.__enter__.return_value = mock_batch_writer
    prices = [CachedPrice(symbol="AAPL", price=185.0), CachedPrice(symbol="MSFT", price=400.0)]
    assert dynamo_cache.set_many(prices) is True
    assert mock_batch_writer.put_item.call_count == 2


# ============================================================================
# 4. UnloggedTableStore Generic Operations Tests
# ============================================================================

def test_unlogged_table_store_generic_operations():
    # Test client wrapper delegation
    mock_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.client = mock_client

    store = UnloggedTableStore(mock_wrapper, table_name="test_table")
    assert store.db == mock_client
    assert store.table_name == "test_table"

    # Test query delegation
    mock_client.query.return_value = [{"id": 1, "name": "test"}]
    res = store.query("SELECT * FROM test_table", {"id": 1})
    assert res == [{"id": 1, "name": "test"}]

    # Test query_one
    res_one = store.query_one("SELECT * FROM test_table WHERE id = :id", {"id": 1})
    assert res_one == {"id": 1, "name": "test"}

    res_empty = store.query_one("SELECT * FROM test_table WHERE id = :id", {"id": 999})
    mock_client.query.return_value = []
    assert store.query_one("SELECT * FROM test_table WHERE id = :id", {"id": 999}) is None

    # Test execute
    mock_client.execute.return_value = {"numberOfRecordsUpdated": 1}
    exec_res = store.execute("UPDATE test_table SET name = :name", {"name": "new"})
    assert exec_res == {"numberOfRecordsUpdated": 1}

    # Test insert fallback SQL construction
    mock_client_no_insert = MagicMock(spec=["execute"])
    mock_client_no_insert.execute.return_value = {"numberOfRecordsUpdated": 1}
    store_no_insert = UnloggedTableStore(mock_client_no_insert, "test_table")
    store_no_insert.insert({"col1": "val1", "col2": 2}, returning="id")
    mock_client_no_insert.execute.assert_called_with(
        "INSERT INTO test_table (col1, col2) VALUES (:col1, :col2) RETURNING id",
        {"col1": "val1", "col2": 2}
    )

    # Test delete fallback SQL construction
    mock_client_no_delete = MagicMock(spec=["execute"])
    mock_client_no_delete.execute.return_value = {"numberOfRecordsUpdated": 3}
    store_no_delete = UnloggedTableStore(mock_client_no_delete, "test_table")
    deleted = store_no_delete.delete("id > :id", {"id": 10})
    assert deleted == 3
    mock_client_no_delete.execute.assert_called_with(
        "DELETE FROM test_table WHERE id > :id",
        {"id": 10}
    )

    # Test truncate
    store.truncate()
    mock_client.execute.assert_called_with("TRUNCATE TABLE test_table", None)


# ============================================================================
# 5. Cache Factory Singleton and Fallback Tests
# ============================================================================

def test_cache_factory_memory():
    factory_module._cache_instance = None
    cache = get_market_cache("memory")
    assert isinstance(cache, MemoryMarketCache)


def test_cache_factory_postgres():
    factory_module._cache_instance = None
    mock_db = MockDataAPIClient()
    pg_cache = get_market_cache("postgres", db_client=mock_db)
    assert isinstance(pg_cache, PostgresUnloggedCache)

    # Fallback when db_client is missing
    factory_module._cache_instance = None
    fallback_cache = get_market_cache("postgres", db_client=None)
    assert isinstance(fallback_cache, MemoryMarketCache)


@patch("boto3.resource")
def test_cache_factory_dynamodb(mock_boto_resource):
    factory_module._cache_instance = None
    dynamo_cache = get_market_cache("dynamodb")
    assert isinstance(dynamo_cache, DynamoDBMarketCache)

    # Fallback when DynamoDB init raises Exception
    factory_module._cache_instance = None
    mock_boto_resource.side_effect = Exception("AWS Auth error")
    fallback_cache = get_market_cache("dynamodb")
    assert isinstance(fallback_cache, MemoryMarketCache)


def test_cache_factory_singleton():
    factory_module._cache_instance = None
    cache1 = get_market_cache()
    assert isinstance(cache1, MemoryMarketCache)

    cache2 = get_market_cache()
    assert cache2 is cache1
