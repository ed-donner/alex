"""
Unit and integration tests for database migrations runner (backend/database/run_migrations.py).
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

backend_dir = str(Path(__file__).parents[2])
database_dir = str(Path(__file__).parents[2] / "database")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if database_dir not in sys.path:
    sys.path.insert(0, database_dir)

from database.run_migrations import run_migrations, STATEMENTS


def test_migration_sql_files_exist_and_valid():
    """Verify backend/database/migrations/ contains 001_schema.sql and 002_unlogged_cache.sql,
    and that both contain expected DDL keywords (CREATE TABLE, CREATE UNLOGGED TABLE, CREATE INDEX)."""
    migrations_dir = Path(__file__).parents[2] / "database" / "migrations"
    file_001 = migrations_dir / "001_schema.sql"
    file_002 = migrations_dir / "002_unlogged_cache.sql"

    assert file_001.exists(), "001_schema.sql does not exist"
    assert file_002.exists(), "002_unlogged_cache.sql does not exist"

    content_001 = file_001.read_text(encoding="utf-8")
    assert "CREATE TABLE" in content_001
    assert "CREATE INDEX" in content_001

    content_002 = file_002.read_text(encoding="utf-8")
    assert "CREATE UNLOGGED TABLE" in content_002
    assert "CREATE INDEX" in content_002


@patch("database.run_migrations.boto3.client")
def test_run_migrations_execution_success(mock_boto_client):
    """Mock boto3 rds-data client and verify run_migrations execution calls execute_statement
    for all 19 schema/index/trigger/unlogged statements."""
    mock_rds = MagicMock()
    mock_boto_client.return_value = mock_rds
    mock_rds.execute_statement.return_value = {"numberOfRecordsUpdated": 0}

    env_vars = {
        "AURORA_CLUSTER_ARN": "arn:aws:rds:us-east-1:123456789012:cluster:mycluster",
        "AURORA_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:mysecret",
        "AURORA_DATABASE": "alex",
        "DEFAULT_AWS_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        success_count, error_count = run_migrations()

    assert mock_boto_client.called
    assert mock_rds.execute_statement.call_count == 19
    assert len(STATEMENTS) == 19
    assert success_count == 19
    assert error_count == 0


@patch("database.run_migrations.boto3.client")
def test_run_migrations_idempotency_already_exists(mock_boto_client):
    """Mock boto3 rds-data client throwing ClientError with 'already exists' for existing
    tables/triggers and verify the migration runner handles them gracefully without failing."""
    mock_rds = MagicMock()
    mock_boto_client.return_value = mock_rds
    mock_rds.execute_statement.side_effect = ClientError(
        {"Error": {"Code": "BadRequestException", "Message": "Relation 'users' already exists"}},
        "execute_statement",
    )

    env_vars = {
        "AURORA_CLUSTER_ARN": "arn:aws:rds:us-east-1:123456789012:cluster:mycluster",
        "AURORA_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:mysecret",
        "AURORA_DATABASE": "alex",
        "DEFAULT_AWS_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        success_count, error_count = run_migrations()

    assert mock_rds.execute_statement.call_count == 19
    assert success_count == 19
    assert error_count == 0


@patch("database.run_migrations.boto3.client")
def test_run_migrations_handles_unexpected_error(mock_boto_client):
    """Mock boto3 rds-data client throwing an unexpected ClientError and verify error handling
    and summary error count reporting."""
    mock_rds = MagicMock()
    mock_boto_client.return_value = mock_rds
    mock_rds.execute_statement.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "Database connection unexpected error"}},
        "execute_statement",
    )

    env_vars = {
        "AURORA_CLUSTER_ARN": "arn:aws:rds:us-east-1:123456789012:cluster:mycluster",
        "AURORA_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:mysecret",
        "AURORA_DATABASE": "alex",
        "DEFAULT_AWS_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        success_count, error_count = run_migrations()

    assert mock_rds.execute_statement.call_count == 19
    assert success_count == 0
    assert error_count == 19


def test_run_migrations_missing_env_vars():
    """Verify ValueError is raised when AURORA_CLUSTER_ARN or AURORA_SECRET_ARN environment
    variables are missing."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="Missing AURORA_CLUSTER_ARN or AURORA_SECRET_ARN"):
            run_migrations()

    env_vars_partial = {"AURORA_CLUSTER_ARN": "arn:aws:rds:us-east-1:123:cluster:dummy"}
    with patch.dict(os.environ, env_vars_partial, clear=True):
        with pytest.raises(ValueError, match="Missing AURORA_CLUSTER_ARN or AURORA_SECRET_ARN"):
            run_migrations()

    env_vars_partial_2 = {"AURORA_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:dummy"}
    with patch.dict(os.environ, env_vars_partial_2, clear=True):
        with pytest.raises(ValueError, match="Missing AURORA_CLUSTER_ARN or AURORA_SECRET_ARN"):
            run_migrations()
