"""
Unit tests for database migration 001_schema.sql.
"""

from pathlib import Path
import pytest


def test_001_schema_file_exists_and_readable():
    """Verify that 001_schema.sql exists in migrations directory and is readable."""
    migrations_dir = Path(__file__).parents[2] / "database" / "migrations"
    schema_path = migrations_dir / "001_schema.sql"
    assert schema_path.exists(), "001_schema.sql file should exist"

    with open(schema_path, encoding="utf-8") as f:
        content = f.read()

    assert len(content) > 0, "001_schema.sql should not be empty"
    assert "CREATE TABLE IF NOT EXISTS users" in content
    assert "CREATE TABLE IF NOT EXISTS instruments" in content
    assert "CREATE TABLE IF NOT EXISTS accounts" in content
    assert "CREATE TABLE IF NOT EXISTS positions" in content
    assert "CREATE TABLE IF NOT EXISTS jobs" in content


def test_001_schema_sql_content_validation():
    """Verify DDL elements in 001_schema.sql contain required columns and indexes."""
    migrations_dir = Path(__file__).parents[2] / "database" / "migrations"
    schema_path = migrations_dir / "001_schema.sql"
    with open(schema_path, encoding="utf-8") as f:
        sql = f.read()

    assert "clerk_user_id" in sql
    assert "uuid-ossp" in sql
    assert "idx_accounts_user" in sql
    assert "idx_positions_account" in sql
    assert "idx_jobs_user" in sql
