-- Migration 002: Create UNLOGGED Market Data Cache Table
-- UNLOGGED tables bypass Write-Ahead Logging (WAL) for 2x-10x faster write performance.
-- Useful for ephemeral market data cache entries with TTL expiration.

CREATE UNLOGGED TABLE IF NOT EXISTS market_data_cache (
    symbol VARCHAR(20) PRIMARY KEY,
    price DECIMAL(12,4) NOT NULL,
    volume BIGINT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at_epoch BIGINT NOT NULL
);

-- Index for efficient expired entry purges
CREATE INDEX IF NOT EXISTS idx_market_cache_expires ON market_data_cache(expires_at_epoch);
