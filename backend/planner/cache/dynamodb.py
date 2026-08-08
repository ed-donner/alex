"""
DynamoDB Market Data Cache Provider for Project Alex.
Integrates with AWS DynamoDB with native TTL support.
"""

import os
import time
import logging
from typing import Optional, Dict, List
import boto3
from botocore.exceptions import ClientError
from cache.base import BaseMarketDataCache, CachedPrice

logger = logging.getLogger(__name__)


class DynamoDBMarketCache(BaseMarketDataCache):
    """DynamoDB Implementation of Market Data Cache."""

    def __init__(self, table_name: str = None, region_name: str = None):
        self.table_name = table_name or os.getenv("MARKET_CACHE_TABLE", "alex-market-data-cache")
        self.region_name = region_name or os.getenv("AWS_REGION", "us-west-2")
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region_name)
        self.table = self.dynamodb.Table(self.table_name)

    def get(self, symbol: str) -> Optional[CachedPrice]:
        try:
            response = self.table.get_item(Key={"symbol": symbol.upper()})
            item = response.get("Item")
            if not item:
                return None

            cached = CachedPrice(
                symbol=item["symbol"],
                price=float(item["price"]),
                volume=int(item.get("volume", 0)),
                updated_at=item["updated_at"],
                expires_at_epoch=int(item["ttl"]),
                source=item.get("source", "dynamodb")
            )

            if cached.is_expired():
                logger.info(f"DynamoDB cache entry for {symbol} expired client-side.")
                return None

            return cached
        except ClientError as e:
            logger.error(f"DynamoDB Cache Get Error for {symbol}: {e}")
            return None

    def set(self, cached_price: CachedPrice) -> bool:
        try:
            item = {
                "symbol": cached_price.symbol.upper(),
                "price": str(cached_price.price),
                "volume": cached_price.volume,
                "updated_at": cached_price.updated_at,
                "ttl": cached_price.expires_at_epoch,
                "source": "dynamodb",
            }
            self.table.put_item(Item=item)
            return True
        except ClientError as e:
            logger.error(f"DynamoDB Cache Set Error for {cached_price.symbol}: {e}")
            return False

    def get_many(self, symbols: List[str]) -> Dict[str, CachedPrice]:
        results = {}
        if not symbols:
            return results
        try:
            keys = [{"symbol": sym.upper()} for sym in symbols]
            response = self.dynamodb.batch_get_item(
                RequestItems={self.table_name: {"Keys": keys}}
            )
            items = response.get("Responses", {}).get(self.table_name, [])
            now_epoch = int(time.time())

            for item in items:
                ttl = int(item["ttl"])
                if ttl > now_epoch:
                    sym = item["symbol"]
                    results[sym] = CachedPrice(
                        symbol=sym,
                        price=float(item["price"]),
                        volume=int(item.get("volume", 0)),
                        updated_at=item["updated_at"],
                        expires_at_epoch=ttl,
                        source=item.get("source", "dynamodb")
                    )
        except ClientError as e:
            logger.error(f"DynamoDB Batch Get Error: {e}")

        return results

    def set_many(self, prices: List[CachedPrice]) -> bool:
        try:
            with self.table.batch_writer() as batch:
                for p in prices:
                    batch.put_item(Item={
                        "symbol": p.symbol.upper(),
                        "price": str(p.price),
                        "volume": p.volume,
                        "updated_at": p.updated_at,
                        "ttl": p.expires_at_epoch,
                        "source": "dynamodb",
                    })
            return True
        except ClientError as e:
            logger.error(f"DynamoDB Batch Set Error: {e}")
            return False
