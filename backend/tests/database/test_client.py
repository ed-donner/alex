"""
Dedicated unit tests for DataAPIClient in backend/database/src/client.py.
Covering:
- test_data_api_client_initialization
- test_data_api_client_parameter_building (stringValue, longValue, doubleValue, booleanValue, isNull)
- test_data_api_client_execute_statement
- test_data_api_client_batch_execute_statement
- test_data_api_client_query_formatting & type parsing
- test_data_api_client_crud_helpers (insert, update, delete, transactions)
"""

import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

backend_dir = str(Path(__file__).parents[2])
database_src_dir = str(Path(__file__).parents[2] / "database" / "src")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if database_src_dir not in sys.path:
    sys.path.insert(0, database_src_dir)

from database.src.client import DataAPIClient


@patch("database.src.client.boto3.client")
def test_data_api_client_initialization(mock_boto_client):
    """Test DataAPIClient initialization with parameters, environment variables, and missing configs."""
    # 1. Explicit parameters
    client = DataAPIClient(
        cluster_arn="arn:aws:rds:us-east-1:123456789012:cluster:mycluster",
        secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:mysecret",
        database="test_db",
        region="us-west-2",
    )
    assert client.cluster_arn == "arn:aws:rds:us-east-1:123456789012:cluster:mycluster"
    assert client.secret_arn == "arn:aws:secretsmanager:us-east-1:123456789012:secret:mysecret"
    assert client.database == "test_db"
    mock_boto_client.assert_called_once_with("rds-data", region_name="us-west-2")

    # 2. Initialization via environment variables
    mock_boto_client.reset_mock()
    env_vars = {
        "AURORA_CLUSTER_ARN": "arn:aws:rds:us-east-1:123456789012:cluster:envcluster",
        "AURORA_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:envsecret",
        "AURORA_DATABASE": "env_db",
        "DEFAULT_AWS_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        client_env = DataAPIClient()
        assert client_env.cluster_arn == "arn:aws:rds:us-east-1:123456789012:cluster:envcluster"
        assert client_env.secret_arn == "arn:aws:secretsmanager:us-east-1:123456789012:secret:envsecret"
        assert client_env.database == "env_db"

    # 3. Missing required credentials raises ValueError
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="Missing required Aurora configuration"):
            DataAPIClient()


@patch("database.src.client.boto3.client")
def test_data_api_client_parameter_building(mock_boto_client):
    """Test DataAPIClient parameter mapping for stringValue, longValue, doubleValue, booleanValue, isNull, etc."""
    client = DataAPIClient(
        cluster_arn="arn:aws:rds:us-east-1:123456789012:cluster:dummy",
        secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:dummy",
        database="alex",
    )

    test_params = {
        "str_key": "hello_world",
        "int_key": 42,
        "float_key": 3.14159,
        "bool_key": True,
        "none_key": None,
        "decimal_key": Decimal("99.99"),
        "datetime_key": datetime(2026, 8, 4, 20, 0, 0),
        "date_key": date(2026, 8, 4),
        "dict_key": {"a": 1},
        "list_key": [1, 2, 3],
    }

    built = client._build_parameters(test_params)

    expected_dict = {
        "str_key": {"stringValue": "hello_world"},
        "int_key": {"longValue": 42},
        "float_key": {"doubleValue": 3.14159},
        "bool_key": {"booleanValue": True},
        "none_key": {"isNull": True},
        "decimal_key": {"stringValue": "99.99"},
        "datetime_key": {"stringValue": "2026-08-04T20:00:00"},
        "date_key": {"stringValue": "2026-08-04"},
        "dict_key": {"stringValue": '{"a": 1}'},
        "list_key": {"stringValue": "[1, 2, 3]"},
    }

    assert len(built) == len(expected_dict)
    for p in built:
        key = p["name"]
        val = p["value"]
        assert val == expected_dict[key]

    # Test empty dict input
    assert client._build_parameters({}) == []
    assert client._build_parameters(None) == []


@patch("database.src.client.boto3.client")
def test_data_api_client_execute_statement(mock_boto_client):
    """Test DataAPIClient execute statement method and error handling."""
    client = DataAPIClient(
        cluster_arn="arn:aws:rds:us-east-1:123456789012:cluster:dummy",
        secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:dummy",
        database="alex",
    )

    client.client.execute_statement.return_value = {
        "numberOfRecordsUpdated": 1,
        "records": [],
    }

    sql = "UPDATE users SET display_name = :name WHERE id = :id"
    params = [{"name": "id", "value": {"stringValue": "123"}}]
    response = client.execute(sql, parameters=params)

    assert response == {"numberOfRecordsUpdated": 1, "records": []}
    client.client.execute_statement.assert_called_once_with(
        resourceArn=client.cluster_arn,
        secretArn=client.secret_arn,
        database=client.database,
        sql=sql,
        includeResultMetadata=True,
        parameters=params,
    )

    # Error handling test
    client.client.execute_statement.side_effect = ClientError(
        {"Error": {"Code": "BadRequestException", "Message": "Syntax error"}},
        "execute_statement",
    )
    with pytest.raises(ClientError):
        client.execute(sql)


@patch("database.src.client.boto3.client")
def test_data_api_client_batch_execute_statement(mock_boto_client):
    """Test DataAPIClient batch_execute_statement method and error handling."""
    client = DataAPIClient(
        cluster_arn="arn:aws:rds:us-east-1:123456789012:cluster:dummy",
        secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:dummy",
        database="alex",
    )

    client.client.batch_execute_statement.return_value = {
        "updateResults": [{"numberOfRecordsUpdated": 1}, {"numberOfRecordsUpdated": 1}]
    }

    sql = "INSERT INTO users (clerk_user_id) VALUES (:clerk_user_id)"
    param_sets = [
        [{"name": "clerk_user_id", "value": {"stringValue": "user_1"}}],
        [{"name": "clerk_user_id", "value": {"stringValue": "user_2"}}],
    ]

    res = client.batch_execute_statement(sql, parameter_sets=param_sets)
    assert res == {"updateResults": [{"numberOfRecordsUpdated": 1}, {"numberOfRecordsUpdated": 1}]}

    client.client.batch_execute_statement.assert_called_once_with(
        resourceArn=client.cluster_arn,
        secretArn=client.secret_arn,
        database=client.database,
        sql=sql,
        parameterSets=param_sets,
    )

    # ClientError propagation test
    client.client.batch_execute_statement.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "Database error"}},
        "batch_execute_statement",
    )
    with pytest.raises(ClientError):
        client.batch_execute_statement(sql, parameter_sets=param_sets)


@patch("database.src.client.boto3.client")
def test_data_api_client_query_formatting(mock_boto_client):
    """Test DataAPIClient query formatting, query_one, and type parsing (stringValue, longValue, booleanValue, JSON)."""
    client = DataAPIClient(
        cluster_arn="arn:aws:rds:us-east-1:123456789012:cluster:dummy",
        secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:dummy",
        database="alex",
    )

    # Response with various field types including JSON strings
    mock_response = {
        "columnMetadata": [
            {"name": "id"},
            {"name": "name"},
            {"name": "age"},
            {"name": "score"},
            {"name": "is_active"},
            {"name": "null_col"},
            {"name": "json_obj"},
            {"name": "json_arr"},
            {"name": "blob_col"},
        ],
        "records": [
            [
                {"stringValue": "uuid-123"},
                {"stringValue": "Alice"},
                {"longValue": 30},
                {"doubleValue": 95.5},
                {"booleanValue": True},
                {"isNull": True},
                {"stringValue": '{"role": "admin"}'},
                {"stringValue": "[10, 20, 30]"},
                {"blobValue": b"bytes_data"},
            ],
            [
                {"stringValue": "uuid-456"},
                {"stringValue": "Bob"},
                {"longValue": 25},
                {"doubleValue": 88.0},
                {"booleanValue": False},
                {"isNull": True},
                {"stringValue": "not_json_string"},
                {"stringValue": "plain text"},
                {"blobValue": b""},
            ],
        ],
    }

    client.client.execute_statement.return_value = mock_response

    # Test query
    results = client.query("SELECT * FROM users")
    assert len(results) == 2

    row1 = results[0]
    assert row1["id"] == "uuid-123"
    assert row1["name"] == "Alice"
    assert row1["age"] == 30
    assert row1["score"] == 95.5
    assert row1["is_active"] is True
    assert row1["null_col"] is None
    assert row1["json_obj"] == {"role": "admin"}
    assert row1["json_arr"] == [10, 20, 30]
    assert row1["blob_col"] == b"bytes_data"

    row2 = results[1]
    assert row2["json_obj"] == "not_json_string"
    assert row2["is_active"] is False

    # Test query_one
    first_row = client.query_one("SELECT * FROM users WHERE id = :id", [{"name": "id", "value": {"stringValue": "uuid-123"}}])
    assert first_row == row1

    # Test empty query response
    client.client.execute_statement.return_value = {}
    assert client.query("SELECT * FROM empty_table") == []
    assert client.query_one("SELECT * FROM empty_table") is None


@patch("database.src.client.boto3.client")
def test_data_api_client_crud_helpers(mock_boto_client):
    """Test DataAPIClient insert, update, delete, and transaction methods."""
    client = DataAPIClient(
        cluster_arn="arn:aws:rds:us-east-1:123456789012:cluster:dummy",
        secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:dummy",
        database="alex",
    )

    # 1. Test insert with type casting placeholders and RETURNING clause
    client.client.execute_statement.return_value = {
        "records": [[{"stringValue": "new-user-uuid"}]]
    }
    insert_data = {
        "clerk_user_id": "clerk_99",
        "metadata": {"theme": "dark"},
        "balance": Decimal("100.50"),
        "created_date": date(2026, 8, 4),
        "created_at": datetime(2026, 8, 4, 20, 0, 0),
        "is_verified": True,
    }
    returned_id = client.insert("users", insert_data, returning="id")
    assert returned_id == "new-user-uuid"

    # Check SQL format passed to execute_statement
    args, kwargs = client.client.execute_statement.call_args
    executed_sql = kwargs["sql"]
    assert "INSERT INTO users" in executed_sql
    assert ":metadata::jsonb" in executed_sql
    assert ":balance::numeric" in executed_sql
    assert ":created_date::date" in executed_sql
    assert ":created_at::timestamp" in executed_sql
    assert "RETURNING id" in executed_sql

    # 2. Test update
    client.client.execute_statement.reset_mock()
    client.client.execute_statement.return_value = {"numberOfRecordsUpdated": 2}

    update_data = {
        "display_name": "New Name",
        "settings": {"notifications": False},
        "updated_at": datetime(2026, 8, 4, 20, 5, 0),
    }
    where_clause = "clerk_user_id = :user_id"
    where_params = {"user_id": "clerk_99"}

    updated_count = client.update("users", update_data, where=where_clause, where_params=where_params)
    assert updated_count == 2

    args, kwargs = client.client.execute_statement.call_args
    executed_sql = kwargs["sql"]
    assert "UPDATE users" in executed_sql
    assert "display_name = :display_name" in executed_sql
    assert "settings = :settings::jsonb" in executed_sql
    assert "updated_at = :updated_at::timestamp" in executed_sql
    assert "WHERE clerk_user_id = :user_id" in executed_sql

    # 3. Test delete
    client.client.execute_statement.reset_mock()
    client.client.execute_statement.return_value = {"numberOfRecordsUpdated": 1}

    deleted_count = client.delete("users", where="id = :id", where_params={"id": "uuid-123"})
    assert deleted_count == 1

    args, kwargs = client.client.execute_statement.call_args
    assert kwargs["sql"] == "DELETE FROM users WHERE id = :id"

    # 4. Test transactions
    client.client.begin_transaction.return_value = {"transactionId": "tx-12345"}
    tx_id = client.begin_transaction()
    assert tx_id == "tx-12345"
    client.client.begin_transaction.assert_called_once_with(
        resourceArn=client.cluster_arn,
        secretArn=client.secret_arn,
        database=client.database,
    )

    client.commit_transaction("tx-12345")
    client.client.commit_transaction.assert_called_once_with(
        resourceArn=client.cluster_arn,
        secretArn=client.secret_arn,
        transactionId="tx-12345",
    )

    client.rollback_transaction("tx-12345")
    client.client.rollback_transaction.assert_called_once_with(
        resourceArn=client.cluster_arn,
        secretArn=client.secret_arn,
        transactionId="tx-12345",
    )
