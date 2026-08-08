# Project Alex: Market Data Caching Strategy

## 1. Executive Summary & Context
Project Alex (Agentic Learning Equities eXplainer) relies heavily on financial market data from Polygon. Frequent calls to the Polygon API for identical data points (e.g., current prices, historical aggregates) introduce unnecessary latency, increase API costs, and risk hitting rate limits. Implementing a robust caching strategy is critical to ensure high performance and scalability. This document evaluates four caching strategies and recommends an architecture tailored for Project Alex.

## 2. Evaluation of Caching Strategies

### Python `lru_cache` (In-Memory)
- **Pros:** Zero network overhead, trivial to implement, sub-microsecond latency.
- **Cons:** Strictly local to the process. If Project Alex scales horizontally across multiple pods/workers, each will maintain its own stale cache. Cache is cleared on restarts. Not suitable for a distributed microservices architecture.

### PostgreSQL UNLOGGED Tables
- **Pros:** Reuses existing database infrastructure (e.g., Aurora). UNLOGGED tables bypass Write-Ahead Logging (WAL), making writes significantly faster than standard tables.
- **Cons:** Data is truncated on database crash/failover. Higher latency (single-digit ms) compared to in-memory caches. Can increase CPU load on the primary DB instance if read volume is extremely high.

### AWS ElastiCache for Redis
- **Pros:** Industry standard for distributed caching. Sub-millisecond latency. Supports complex data structures, pub/sub for real-time WebSocket updates, and native TTL (Time-To-Live).
- **Cons:** Introduces a new infrastructure component. Additional fixed costs (even when idle). Requires VPC endpoint configuration and increases operational complexity (e.g., managing failover, Redis clusters).

### DynamoDB with TTL
- **Pros:** Fully serverless, scale-to-zero pricing (pay-per-request). Built-in TTL automatically expires stale market data without background sweepers. No VPC needed (accessed via HTTPS).
- **Cons:** Higher latency (typically 10-20ms) than Redis or local PostgreSQL. Eventual consistency model might occasionally serve slightly stale prices immediately after an update.

## 3. Technical Architecture & Trade-offs

| Feature | `lru_cache` | PostgreSQL UNLOGGED | ElastiCache (Redis) | DynamoDB (TTL) |
| :--- | :--- | :--- | :--- | :--- |
| **Latency** | < 0.1 ms | 2-5 ms | < 1 ms | 10-20 ms |
| **Cost** | Free | Included in DB | High (Fixed hourly) | Low (Pay-per-request) |
| **VPC Networking**| None | Existing DB VPC | Requires VPC/Subnets | Public / VPC Endpoint |
| **Failover** | N/A | Truncated on DB crash | Automatic (Multi-AZ) | Highly Available |
| **Cold Start** | Instant | Instant | Minutes to provision | Instant |

**Recommendation:** For the initial launch of Project Alex, **PostgreSQL UNLOGGED tables** offer the best balance of performance and operational simplicity, leveraging our existing Aurora setup. As user load increases and latency requirements tighten, the architecture should migrate to **AWS ElastiCache for Redis**.

## 4. Recommended Implementation Plan & Schema Design

We will implement a PostgreSQL UNLOGGED table designed to act as a key-value store for Polygon market data, complete with a manual expiration mechanism.

### Schema Design
```sql
CREATE UNLOGGED TABLE market_data_cache (
    symbol VARCHAR(20) PRIMARY KEY,
    current_price NUMERIC(15, 6) NOT NULL,
    last_updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_market_data_cache_expires ON market_data_cache(expires_at);
```

## 5. Step-by-Step Migration Guide & Code Snippets

### Step 1: Database Initialization
Run the schema creation script on the target PostgreSQL database.

### Step 2: Python Cache Interface
Implement a Python abstraction layer in `backend/cache/market_cache.py`.

```python
from datetime import datetime, timedelta
import asyncpg

class MarketDataCache:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_price(self, symbol: str) -> float | None:
        query = """
            SELECT current_price FROM market_data_cache 
            WHERE symbol = $1 AND expires_at > NOW()
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, symbol)

    async def set_price(self, symbol: str, price: float, ttl_seconds: int = 60):
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        query = """
            INSERT INTO market_data_cache (symbol, current_price, last_updated_at, expires_at)
            VALUES ($1, $2, NOW(), $3)
            ON CONFLICT (symbol) DO UPDATE 
            SET current_price = EXCLUDED.current_price,
                last_updated_at = EXCLUDED.last_updated_at,
                expires_at = EXCLUDED.expires_at
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, symbol, price, expires_at)
```

### Step 3: Application Integration
Replace existing raw Polygon API calls with a cache-aside pattern:

```python
async def fetch_ticker_price(symbol: str, db_pool: asyncpg.Pool) -> float:
    cache = MarketDataCache(db_pool)
    
    # 1. Check cache
    price = await cache.get_price(symbol)
    if price is not None:
        return price
        
    # 2. Fetch from Polygon if missing or stale
    live_price = await polygon_client.get_last_trade(symbol)
    
    # 3. Update cache async
    await cache.set_price(symbol, live_price, ttl_seconds=300) # 5 min TTL
    
    return live_price
```
