"""
Unit tests for database models and store wrappers in backend/database.
Covering:
- test_database_initialization: Verify Database instantiation attaches all sub-models.
- test_user_model_sunny_day: Test find_by_clerk_id, create, update.
- test_instrument_model_sunny_day: Test find_by_symbol, create, find_all.
- test_account_model_sunny_day: Test find_by_user, create.
- test_position_model_sunny_day: Test find_by_account, create.
- test_job_model_sunny_day: Test find_by_user, update_status, update_payload, create.
- test_unlogged_market_cache_store_sunny_day: Test set, get, get_many.
"""

import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_dir = str(Path(__file__).parents[2])
database_src_dir = str(Path(__file__).parents[2] / "database" / "src")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if database_src_dir not in sys.path:
    sys.path.insert(0, database_src_dir)

from database.src.client import DataAPIClient
from database.src.models import Database, Users, Instruments, Accounts, Positions, Jobs
from database.src.unlogged.store import UnloggedMarketCacheStore
from database.src.schemas import InstrumentCreate


@patch("database.src.client.boto3.client")
def test_database_initialization(mock_boto_client):
    """Verify Database instantiation attaches all sub-models."""
    db = Database(
        cluster_arn="arn:aws:rds:us-east-1:123456789012:cluster:dummy",
        secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:dummy",
        database="alex_test",
        region="us-east-1",
    )
    assert isinstance(db.client, DataAPIClient)
    assert isinstance(db.users, Users)
    assert isinstance(db.instruments, Instruments)
    assert isinstance(db.accounts, Accounts)
    assert isinstance(db.positions, Positions)
    assert isinstance(db.jobs, Jobs)
    assert isinstance(db.market_cache, UnloggedMarketCacheStore)


def test_user_model_sunny_day():
    """Test Users model: find_by_clerk_id, create, update."""
    mock_db = MagicMock(spec=DataAPIClient)
    users_model = Users(mock_db)

    # 1. find_by_clerk_id
    mock_db.query_one.return_value = {
        "clerk_user_id": "user_clerk_123",
        "display_name": "Test User",
    }
    user = users_model.find_by_clerk_id("user_clerk_123")
    assert user == {"clerk_user_id": "user_clerk_123", "display_name": "Test User"}
    mock_db.query_one.assert_called_once()

    # 2. create (create_user and inherited create)
    mock_db.insert.return_value = "user_clerk_123"
    created_id = users_model.create_user(
        clerk_user_id="user_clerk_123",
        display_name="Test User",
        years_until_retirement=25,
        target_retirement_income=Decimal("80000"),
    )
    assert created_id == "user_clerk_123"
    mock_db.insert.assert_called_once()

    mock_db.insert.reset_mock()
    mock_db.insert.return_value = "user_uuid_123"
    created_generic = users_model.create(
        {"clerk_user_id": "user_clerk_123", "display_name": "Test User"}
    )
    assert created_generic == "user_uuid_123"
    mock_db.insert.assert_called_once()

    # 3. update
    mock_db.update.return_value = 1
    updated_rows = users_model.update(
        "user_uuid_123", {"display_name": "Updated User"}
    )
    assert updated_rows == 1
    mock_db.update.assert_called_once_with(
        "users", {"display_name": "Updated User"}, "id = :id::uuid", {"id": "user_uuid_123"}
    )


def test_instrument_model_sunny_day():
    """Test Instruments model: find_by_symbol, create, find_all."""
    mock_db = MagicMock(spec=DataAPIClient)
    inst_model = Instruments(mock_db)

    # 1. find_by_symbol
    mock_db.query_one.return_value = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "instrument_type": "etf",
    }
    instrument = inst_model.find_by_symbol("AAPL")
    assert instrument["symbol"] == "AAPL"
    assert instrument["name"] == "Apple Inc."
    mock_db.query_one.assert_called_once()

    # 2. create (create_instrument and inherited create)
    mock_db.insert.return_value = "AAPL"
    inst_create = InstrumentCreate(
        symbol="AAPL",
        name="Apple Inc.",
        instrument_type="etf",
        allocation_regions={"north_america": 100.0},
        allocation_sectors={"technology": 100.0},
        allocation_asset_class={"equity": 100.0},
    )
    created_sym = inst_model.create_instrument(inst_create)
    assert created_sym == "AAPL"
    mock_db.insert.assert_called_once()

    mock_db.insert.reset_mock()
    mock_db.insert.return_value = "MSFT"
    created_generic = inst_model.create(
        {"symbol": "MSFT", "name": "Microsoft Corp.", "instrument_type": "stock"}
    )
    assert created_generic == "MSFT"
    mock_db.insert.assert_called_once()

    # 3. find_all
    mock_db.query.return_value = [
        {"symbol": "AAPL", "name": "Apple Inc."},
        {"symbol": "MSFT", "name": "Microsoft Corp."},
    ]
    all_insts = inst_model.find_all()
    assert len(all_insts) == 2
    assert all_insts[0]["symbol"] == "AAPL"
    assert all_insts[1]["symbol"] == "MSFT"
    mock_db.query.assert_called_once()


def test_account_model_sunny_day():
    """Test Accounts model: find_by_user, create."""
    mock_db = MagicMock(spec=DataAPIClient)
    accounts_model = Accounts(mock_db)

    # 1. find_by_user
    mock_db.query.return_value = [
        {"id": "acc-uuid-1", "clerk_user_id": "user_123", "account_name": "Checking"},
        {"id": "acc-uuid-2", "clerk_user_id": "user_123", "account_name": "Investment"},
    ]
    user_accounts = accounts_model.find_by_user("user_123")
    assert len(user_accounts) == 2
    assert user_accounts[0]["account_name"] == "Checking"
    mock_db.query.assert_called_once()

    # 2. create (create_account and inherited create)
    mock_db.insert.return_value = "acc-uuid-1"
    account_id = accounts_model.create_account(
        clerk_user_id="user_123",
        account_name="Investment",
        account_purpose="Retirement",
        cash_balance=Decimal("5000.00"),
    )
    assert account_id == "acc-uuid-1"
    mock_db.insert.assert_called_once()

    mock_db.insert.reset_mock()
    mock_db.insert.return_value = "acc-uuid-2"
    generic_acc_id = accounts_model.create(
        {"clerk_user_id": "user_123", "account_name": "Savings"}
    )
    assert generic_acc_id == "acc-uuid-2"
    mock_db.insert.assert_called_once()


def test_position_model_sunny_day():
    """Test Positions model: find_by_account, create."""
    mock_db = MagicMock(spec=DataAPIClient)
    positions_model = Positions(mock_db)

    # 1. find_by_account
    mock_db.query.return_value = [
        {"id": "pos-1", "account_id": "acc-123", "symbol": "AAPL", "quantity": Decimal("10")},
        {"id": "pos-2", "account_id": "acc-123", "symbol": "MSFT", "quantity": Decimal("5")},
    ]
    account_positions = positions_model.find_by_account("acc-123")
    assert len(account_positions) == 2
    assert account_positions[0]["symbol"] == "AAPL"
    mock_db.query.assert_called_once()

    # 2. create (add_position and inherited create)
    mock_db.execute.return_value = {"records": [[{"stringValue": "pos-uuid-1"}]]}
    pos_id = positions_model.add_position(
        account_id="acc-123",
        symbol="AAPL",
        quantity=Decimal("15.5"),
    )
    assert pos_id == "pos-uuid-1"
    mock_db.execute.assert_called_once()

    mock_db.insert.return_value = "pos-uuid-2"
    generic_pos_id = positions_model.create(
        {"account_id": "acc-123", "symbol": "GOOGL", "quantity": 20}
    )
    assert generic_pos_id == "pos-uuid-2"
    mock_db.insert.assert_called_once()


def test_job_model_sunny_day():
    """Test Jobs model: find_by_user, update_status, update_payload, create."""
    mock_db = MagicMock(spec=DataAPIClient)
    jobs_model = Jobs(mock_db)

    # 1. create (create_job and inherited create)
    mock_db.insert.return_value = "job-uuid-1"
    job_id = jobs_model.create_job(
        clerk_user_id="user_123",
        job_type="portfolio_analysis",
        request_payload={"account_id": "acc-123"},
    )
    assert job_id == "job-uuid-1"
    mock_db.insert.assert_called_once()

    mock_db.insert.reset_mock()
    mock_db.insert.return_value = "job-uuid-2"
    generic_job_id = jobs_model.create(
        {"clerk_user_id": "user_123", "job_type": "rebalance", "status": "pending"}
    )
    assert generic_job_id == "job-uuid-2"
    mock_db.insert.assert_called_once()

    # 2. find_by_user
    mock_db.query.return_value = [
        {"id": "job-uuid-1", "clerk_user_id": "user_123", "status": "pending"},
    ]
    user_jobs = jobs_model.find_by_user("user_123")
    assert len(user_jobs) == 1
    assert user_jobs[0]["id"] == "job-uuid-1"
    mock_db.query.assert_called_once()

    # 3. update_status
    mock_db.update.return_value = 1
    updated_status_rows = jobs_model.update_status("job-uuid-1", "running")
    assert updated_status_rows == 1
    assert mock_db.update.call_count == 1

    # 4. update_payload (testing payload update helper methods)
    mock_db.update.reset_mock()
    mock_db.update.return_value = 1
    updated_report_rows = jobs_model.update_report("job-uuid-1", {"analysis": "good"})
    assert updated_report_rows == 1
    mock_db.update.assert_called_once_with(
        "jobs", {"report_payload": {"analysis": "good"}}, "id = :id::uuid", {"id": "job-uuid-1"}
    )

    mock_db.update.reset_mock()
    mock_db.update.return_value = 1
    updated_summary_rows = jobs_model.update_summary("job-uuid-1", {"summary": "done"})
    assert updated_summary_rows == 1


def test_unlogged_market_cache_store_sunny_day():
    """Test UnloggedMarketCacheStore: set, get, get_many."""
    mock_db = MagicMock(spec=DataAPIClient)
    cache_store = UnloggedMarketCacheStore(mock_db)

    # 1. set (set_price & set_prices)
    mock_db.execute.return_value = {"numberOfRecordsUpdated": 1}
    success = cache_store.set_price(
        symbol="AAPL",
        price=180.50,
        volume=1000000,
        updated_at="2026-08-04T20:00:00Z",
        expires_at_epoch=1700000000,
        source="postgres_unlogged",
    )
    assert success is True
    mock_db.execute.assert_called_once()

    mock_db.execute.reset_mock()
    prices_list = [
        {
            "symbol": "AAPL",
            "price": 180.50,
            "volume": 1000000,
            "updated_at": "2026-08-04T20:00:00Z",
            "expires_at_epoch": 1700000000,
        },
        {
            "symbol": "MSFT",
            "price": 400.00,
            "volume": 500000,
            "updated_at": "2026-08-04T20:00:00Z",
            "expires_at_epoch": 1700000000,
        },
    ]
    batch_success = cache_store.set_prices(prices_list)
    assert batch_success is True
    assert mock_db.execute.call_count == 2

    # 2. get (get_price)
    mock_db.query.return_value = [
        {
            "symbol": "AAPL",
            "current_price": Decimal("180.50"),
            "volume": 1000000,
            "updated_at": "2026-08-04T20:00:00Z",
            "expires_at_epoch": 1700000000,
            "source": "postgres_unlogged",
        }
    ]
    retrieved = cache_store.get_price("AAPL", now_epoch=1600000000)
    assert retrieved is not None
    assert retrieved["symbol"] == "AAPL"

    # 3. get_many (get_prices)
    mock_db.query.side_effect = [
        [
            {
                "symbol": "AAPL",
                "current_price": Decimal("180.50"),
                "volume": 1000000,
                "updated_at": "2026-08-04T20:00:00Z",
                "expires_at_epoch": 1700000000,
                "source": "postgres_unlogged",
            }
        ],
        [
            {
                "symbol": "MSFT",
                "current_price": Decimal("400.00"),
                "volume": 500000,
                "updated_at": "2026-08-04T20:00:00Z",
                "expires_at_epoch": 1700000000,
                "source": "postgres_unlogged",
            }
        ],
    ]
    many_results = cache_store.get_prices(["AAPL", "MSFT"], now_epoch=1600000000)
    assert len(many_results) == 2
    assert many_results[0]["symbol"] == "AAPL"
    assert many_results[1]["symbol"] == "MSFT"
