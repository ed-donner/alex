"""
Unit and integration tests for database migration runner (backend/database/run_migrations.py).
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


@patch("database.run_migrations.boto3.client")
def test_run_migrations_success(mock_boto_client):
    """Mock boto3 rds-data client and env vars, invoke run_migrations(), assert success_count == 19 and error_count == 0."""
    mock_rds = MagicMock()
    mock_boto_client.return_value = mock_rds
    mock_rds.execute_statement.return_value = {"numberOfRecordsUpdated": 0}

    env_vars = {
        "AURORA_CLUSTER_ARN": "arn:aws:rds:us-east-1:123456789012:cluster:test-cluster",
        "AURORA_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret",
        "AURORA_DATABASE": "alex",
        "DEFAULT_AWS_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        success_count, error_count = run_migrations()

    assert mock_boto_client.called
    assert mock_rds.execute_statement.call_count == 19
    assert success_count == 19
    assert error_count == 0


@patch("database.run_migrations.boto3.client")
def test_run_migrations_idempotency_already_exists(mock_boto_client):
    """Mock execute_statement throwing ClientError with 'already exists', assert success_count == 19 and error_count == 0."""
    mock_rds = MagicMock()
    mock_boto_client.return_value = mock_rds
    mock_rds.execute_statement.side_effect = ClientError(
        {"Error": {"Code": "BadRequestException", "Message": "Relation 'users' already exists"}},
        "execute_statement",
    )

    env_vars = {
        "AURORA_CLUSTER_ARN": "arn:aws:rds:us-east-1:123456789012:cluster:test-cluster",
        "AURORA_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret",
        "AURORA_DATABASE": "alex",
        "DEFAULT_AWS_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        success_count, error_count = run_migrations()

    assert mock_rds.execute_statement.call_count == 19
    assert success_count == 19
    assert error_count == 0


@patch("database.run_migrations.boto3.client")
def test_run_migrations_handles_error(mock_boto_client):
    """Mock execute_statement throwing unexpected ClientError, assert error_count > 0."""
    mock_rds = MagicMock()
    mock_boto_client.return_value = mock_rds
    mock_rds.execute_statement.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "Syntax error near token 'FOO'"}},
        "execute_statement",
    )

    env_vars = {
        "AURORA_CLUSTER_ARN": "arn:aws:rds:us-east-1:123456789012:cluster:test-cluster",
        "AURORA_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret",
        "AURORA_DATABASE": "alex",
        "DEFAULT_AWS_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        success_count, error_count = run_migrations()

    assert mock_rds.execute_statement.call_count == 19
    assert error_count > 0


def test_run_migrations_missing_env_vars():
    """Test ValueError when AURORA_CLUSTER_ARN or AURORA_SECRET_ARN is missing."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="Missing AURORA_CLUSTER_ARN or AURORA_SECRET_ARN"):
            run_migrations()

    env_vars_missing_secret = {"AURORA_CLUSTER_ARN": "arn:aws:rds:us-east-1:123:cluster:test"}
    with patch.dict(os.environ, env_vars_missing_secret, clear=True):
        with pytest.raises(ValueError, match="Missing AURORA_CLUSTER_ARN or AURORA_SECRET_ARN"):
            run_migrations()

    env_vars_missing_cluster = {"AURORA_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:test"}
    with patch.dict(os.environ, env_vars_missing_cluster, clear=True):
        with pytest.raises(ValueError, match="Missing AURORA_CLUSTER_ARN or AURORA_SECRET_ARN"):
            run_migrations()
