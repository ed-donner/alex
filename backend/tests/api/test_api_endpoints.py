import os
import sys
from unittest.mock import MagicMock, patch
import pytest

from fastapi.testclient import TestClient
from main import app, get_current_user_id, clerk_guard
from fastapi_clerk_auth import HTTPAuthorizationCredentials


@pytest.fixture
def mock_db():
    """Mock database instance for API tests"""
    with patch("deps.db") as mock_db_inst:
        # Mock users model
        mock_db_inst.users.find_by_clerk_id.return_value = {
            "clerk_user_id": "user_test123",
            "display_name": "Test User",
            "years_until_retirement": 20,
            "target_retirement_income": 60000.0,
            "asset_class_targets": {"equity": 70, "fixed_income": 30},
            "region_targets": {"north_america": 50, "international": 50},
        }
        mock_db_inst.users.db.update.return_value = True

        # Mock accounts model
        mock_db_inst.accounts.find_by_user.return_value = [
            {
                "id": "acc-123",
                "clerk_user_id": "user_test123",
                "account_name": "401k",
                "account_purpose": "Retirement",
                "cash_balance": 5000.0,
                "positions": [],
            }
        ]
        mock_db_inst.accounts.find_by_id.return_value = {
            "id": "acc-123",
            "clerk_user_id": "user_test123",
            "account_name": "401k",
            "account_purpose": "Retirement",
            "cash_balance": 5000.0,
        }
        mock_db_inst.accounts.create_account.return_value = "acc-123"
        mock_db_inst.accounts.update.return_value = True
        mock_db_inst.accounts.delete.return_value = True

        # Mock positions model
        mock_db_inst.positions.find_by_account.return_value = [
            {
                "id": "pos-123",
                "account_id": "acc-123",
                "symbol": "SPY",
                "quantity": 10.0,
            }
        ]
        mock_db_inst.positions.find_by_id.return_value = {
            "id": "pos-123",
            "account_id": "acc-123",
            "symbol": "SPY",
            "quantity": 25.0,
        }
        mock_db_inst.positions.add_position.return_value = "pos-123"
        mock_db_inst.positions.update.return_value = True
        mock_db_inst.positions.delete.return_value = True

        # Mock instruments model
        mock_db_inst.instruments.find_all.return_value = [
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "instrument_type": "etf", "current_price": 550.0}
        ]
        mock_db_inst.instruments.find_by_symbol.return_value = {
            "symbol": "SPY",
            "name": "SPDR S&P 500 ETF Trust",
            "instrument_type": "etf",
            "current_price": 550.0,
        }
        mock_db_inst.instruments.create_instrument.return_value = "SPY"
        mock_db_inst.instruments.update.return_value = 1

        # Mock jobs model
        mock_db_inst.jobs.create_job.return_value = "job-123"
        mock_db_inst.jobs.find_by_id.return_value = {
            "id": "job-123",
            "clerk_user_id": "user_test123",
            "job_type": "portfolio",
            "status": "completed",
            "report_payload": {"summary": "Healthy portfolio"},
        }
        mock_db_inst.jobs.find_by_user.return_value = []

        # Mock market cache
        mock_db_inst.market_cache.set_prices.return_value = True

        yield mock_db_inst


@pytest.fixture
def client(mock_db):
    """FastAPI TestClient with overridden authentication dependencies"""
    app.dependency_overrides[get_current_user_id] = lambda: "user_test123"
    app.dependency_overrides[clerk_guard] = lambda: HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="mock-token",
        decoded={"sub": "user_test123", "name": "Test User"},
    )
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def test_health_check_sunny_day(client):
    """Test GET /health returns 200 OK and healthy status"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_get_or_create_user_sunny_day(client, mock_db):
    """Test GET /api/user returns existing user profile"""
    response = client.get("/api/user")
    assert response.status_code == 200
    data = response.json()
    assert data["created"] is False
    assert data["user"]["clerk_user_id"] == "user_test123"


def test_update_user_sunny_day(client, mock_db):
    """Test PUT /api/user updates user preferences"""
    payload = {
        "display_name": "Updated Name",
        "years_until_retirement": 15,
        "target_retirement_income": 75000.0,
    }
    response = client.put("/api/user", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["clerk_user_id"] == "user_test123"


def test_get_accounts_sunny_day(client, mock_db):
    """Test GET /api/accounts lists user accounts with positions"""
    response = client.get("/api/accounts")
    assert response.status_code == 200
    accounts = response.json()
    assert len(accounts) == 1
    assert accounts[0]["id"] == "acc-123"


def test_create_account_sunny_day(client, mock_db):
    """Test POST /api/accounts creates new investment account"""
    payload = {
        "account_name": "Roth IRA",
        "account_purpose": "Retirement",
        "cash_balance": 2500.0,
    }
    response = client.post("/api/accounts", json=payload)
    assert response.status_code == 200
    account = response.json()
    assert account["id"] == "acc-123"


def test_delete_account_sunny_day(client, mock_db):
    """Test DELETE /api/accounts/{account_id} removes account"""
    response = client.delete("/api/accounts/acc-123")
    assert response.status_code == 200
    assert response.json()["message"] == "Account deleted successfully"


def test_add_position_sunny_day(client, mock_db):
    """Test POST /api/positions adds a holding position"""
    payload = {"account_id": "acc-123", "symbol": "SPY", "quantity": 25.0}
    response = client.post("/api/positions", json=payload)
    assert response.status_code == 200
    position = response.json()
    assert position["id"] == "pos-123"


def test_delete_position_sunny_day(client, mock_db):
    """Test DELETE /api/positions/{position_id} removes a position holding"""
    response = client.delete("/api/positions/pos-123")
    assert response.status_code == 200
    assert response.json()["message"] == "Position deleted"


def test_populate_test_data_static_sunny_day(client, mock_db):
    """Test POST /api/populate-test-data with default static seed data"""
    response = client.post("/api/populate-test-data?fetch_live_prices=false")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Test data populated successfully"
    assert data["accounts_created"] == 3


@patch("planner.prices.get_all_share_prices_polygon_eod")
def test_populate_test_data_live_polygon_sunny_day(mock_polygon_fetch, client, mock_db):
    """Test POST /api/populate-test-data with fetch_live_prices=true querying Polygon"""
    mock_polygon_fetch.return_value = {"SPY": 555.0, "AAPL": 220.0, "NVDA": 130.0}

    response = client.post("/api/populate-test-data?fetch_live_prices=true")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Test data populated successfully"
    assert mock_polygon_fetch.called


def test_reset_accounts_sunny_day(client, mock_db):
    """Test DELETE /api/reset-accounts removes all user accounts"""
    response = client.delete("/api/reset-accounts")
    assert response.status_code == 200
    assert "deleted" in response.json()["message"].lower()


@patch("deps.sqs_client")
def test_analyze_portfolio_sunny_day(mock_sqs, client, mock_db):
    """Test POST /api/analyze queues analysis job to SQS"""
    mock_sqs.send_message.return_value = {"MessageId": "msg-123"}

    payload = {"analysis_type": "portfolio", "options": {}}
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "job-123"
    assert "analysis started" in data["message"].lower()


def test_get_job_status_sunny_day(client, mock_db):
    """Test GET /api/jobs/{job_id} retrieves job execution details"""
    response = client.get("/api/jobs/job-123")
    assert response.status_code == 200
    job = response.json()
    assert job["id"] == "job-123"
    assert job["status"] == "completed"


def test_get_instruments_sunny_day(client, mock_db):
    """Test GET /api/instruments lists supported financial instruments"""
    response = client.get("/api/instruments")
    assert response.status_code == 200
    instruments = response.json()
    assert len(instruments) == 1
    assert instruments[0]["symbol"] == "SPY"
