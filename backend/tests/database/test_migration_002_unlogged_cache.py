"""
Unit tests for database migration 002_unlogged_cache.sql.
"""

from pathlib import Path
import pytest


def test_002_unlogged_cache_file_exists_and_readable():
    """Verify that 002_unlogged_cache.sql exists in migrations directory and is readable."""
    migrations_dir = Path(__file__).parents[2] / "database" / "migrations"
    schema_path = migrations_dir / "002_unlogged_cache.sql"
    assert schema_path.exists(), "002_unlogged_cache.sql file should exist"

    with open(schema_path, encoding="utf-8") as f:
        content = f.read()

    assert len(content) > 0, "002_unlogged_cache.sql should not be empty"
    assert "CREATE UNLOGGED TABLE IF NOT EXISTS market_data_cache" in content
    assert "expires_at_epoch" in content


def test_002_unlogged_cache_sql_content_validation():
    """Verify DDL elements in 002_unlogged_cache.sql contain required columns and index."""
    migrations_dir = Path(__file__).parents[2] / "database" / "migrations"
    schema_path = migrations_dir / "002_unlogged_cache.sql"
    with open(schema_path, encoding="utf-8") as f:
        sql = f.read()

    assert "symbol VARCHAR(20) PRIMARY KEY" in sql
    assert "price DECIMAL(12,4) NOT NULL" in sql
    assert "idx_market_cache_expires" in sql
