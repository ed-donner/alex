"""
Sunny-day and parameter validation unit tests for Agent Lambda Handlers.
Refers to backend/tests/scheduler/test_lambda_function.py as an example.

Covers:
- Tagger Handler (tagger/lambda_handler.py): test_tagger_lambda_handler_success & missing params
- Reporter Handler (reporter/lambda_handler.py): test_reporter_lambda_handler_success & missing params
- Charter Handler (charter/lambda_handler.py): test_charter_lambda_handler_success & missing params
- Retirement Handler (retirement/lambda_handler.py): test_retirement_lambda_handler_success & missing params
- Planner Handler (planner/lambda_handler.py): test_planner_lambda_handler_success & missing params
"""

import sys
import json
import importlib
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock


def get_lambda_handler(agent_name: str):
    """
    Dynamically loads the lambda_handler function for a specific agent package directory,
    isolating its local submodules (agent, observability, templates, etc.) from sys.modules collisions.
    """
    backend_dir = Path(__file__).parents[2]
    agent_dir = str(backend_dir / agent_name)

    # Clean up shadowed module names from previous handler imports
    modules_to_clear = [
        "agent", "observability", "templates", "market",
        "judge", "prices", "cache", "lambda_handler"
    ]
    for m in list(sys.modules.keys()):
        if m in modules_to_clear:
            del sys.modules[m]

    if agent_dir in sys.path:
        sys.path.remove(agent_dir)
    sys.path.insert(0, agent_dir)

    mod = importlib.import_module(f"{agent_name}.lambda_handler")
    return getattr(mod, "lambda_handler")


# ============================================================================
# 1. Tagger Handler Tests
# ============================================================================

def test_tagger_lambda_handler_success():
    """Verify sunny-day execution of tagger lambda handler."""
    tagger_handler = get_lambda_handler("tagger")

    with patch("tagger.lambda_handler.process_instruments") as mock_process:
        mock_process.return_value = {
            "tagged": 1,
            "updated": ["VTI"],
            "errors": [],
            "classifications": [
                {
                    "symbol": "VTI",
                    "name": "Vanguard Total Stock Market ETF",
                    "type": "etf",
                    "current_price": 220.0,
                    "asset_class": {"equity": 100},
                    "regions": {"north_america": 100},
                    "sectors": {"technology": 30}
                }
            ]
        }

        event = {
            "instruments": [
                {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF"}
            ]
        }
        result = tagger_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["tagged"] == 1
        assert "VTI" in body["updated"]
        mock_process.assert_called_once_with(event["instruments"])


def test_tagger_lambda_handler_missing_instruments():
    """Verify tagger lambda handler returns 400 when instruments are missing or empty."""
    tagger_handler = get_lambda_handler("tagger")

    event_empty = {"instruments": []}
    result_empty = tagger_handler(event_empty, None)
    assert result_empty["statusCode"] == 400
    body_empty = json.loads(result_empty["body"])
    assert body_empty["error"] == "No instruments provided"

    event_missing = {}
    result_missing = tagger_handler(event_missing, None)
    assert result_missing["statusCode"] == 400


# ============================================================================
# 2. Reporter Handler Tests
# ============================================================================

def test_reporter_lambda_handler_success():
    """Verify sunny-day execution of reporter lambda handler."""
    reporter_handler = get_lambda_handler("reporter")

    with patch("reporter.lambda_handler.run_reporter_agent") as mock_run_reporter:
        mock_run_reporter.return_value = {
            "success": True,
            "message": "Report generated and stored",
            "final_output": "Comprehensive Portfolio Analysis Report"
        }

        event = {
            "job_id": "test-job-reporter-123",
            "portfolio_data": {"accounts": []},
            "user_data": {"years_until_retirement": 25, "target_retirement_income": 80000}
        }
        result = reporter_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["success"] is True
        assert body["final_output"] == "Comprehensive Portfolio Analysis Report"
        mock_run_reporter.assert_called_once()


def test_reporter_lambda_handler_missing_job_id():
    """Verify reporter lambda handler returns 400 when job_id is missing."""
    reporter_handler = get_lambda_handler("reporter")

    event = {"portfolio_data": {}, "user_data": {}}
    result = reporter_handler(event, None)

    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert body["error"] == "job_id is required"


# ============================================================================
# 3. Charter Handler Tests
# ============================================================================

def test_charter_lambda_handler_success():
    """Verify sunny-day execution of charter lambda handler."""
    charter_handler = get_lambda_handler("charter")

    with patch("charter.lambda_handler.run_charter_agent") as mock_run_charter:
        mock_run_charter.return_value = {
            "success": True,
            "message": "Generated 2 charts",
            "charts_generated": 2,
            "chart_keys": ["allocation_chart", "sector_chart"]
        }

        event = {
            "job_id": "test-job-charter-456",
            "portfolio_data": {"accounts": []}
        }
        result = charter_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["success"] is True
        assert body["charts_generated"] == 2
        assert "allocation_chart" in body["chart_keys"]
        mock_run_charter.assert_called_once()


def test_charter_lambda_handler_missing_job_id():
    """Verify charter lambda handler returns 400 when job_id is missing."""
    charter_handler = get_lambda_handler("charter")

    event = {"portfolio_data": {}}
    result = charter_handler(event, None)

    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert body["error"] == "job_id is required"


# ============================================================================
# 4. Retirement Handler Tests
# ============================================================================

def test_retirement_lambda_handler_success():
    """Verify sunny-day execution of retirement lambda handler."""
    retirement_handler = get_lambda_handler("retirement")

    with patch("retirement.lambda_handler.run_retirement_agent") as mock_run_retirement:
        mock_run_retirement.return_value = {
            "success": True,
            "message": "Retirement analysis completed",
            "final_output": "Retirement readiness score: 85%"
        }

        event = {
            "job_id": "test-job-retirement-789",
            "portfolio_data": {"accounts": []}
        }
        result = retirement_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["success"] is True
        assert body["final_output"] == "Retirement readiness score: 85%"
        mock_run_retirement.assert_called_once()


def test_retirement_lambda_handler_missing_job_id():
    """Verify retirement lambda handler returns 400 when job_id is missing."""
    retirement_handler = get_lambda_handler("retirement")

    event = {"portfolio_data": {}}
    result = retirement_handler(event, None)

    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert body["error"] == "job_id is required"


# ============================================================================
# 5. Planner Orchestrator Handler Tests
# ============================================================================

def test_planner_lambda_handler_success():
    """Verify sunny-day execution of planner lambda handler with direct invocation."""
    planner_handler = get_lambda_handler("planner")

    with patch("planner.lambda_handler.run_orchestrator") as mock_run_orchestrator:
        mock_run_orchestrator.return_value = None

        event = {"job_id": "test-job-planner-000"}
        result = planner_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["success"] is True
        assert "Analysis completed for job test-job-planner-000" in body["message"]
        mock_run_orchestrator.assert_called_once_with("test-job-planner-000")


def test_planner_lambda_handler_sqs_success():
    """Verify sunny-day execution of planner lambda handler triggered via SQS."""
    planner_handler = get_lambda_handler("planner")

    with patch("planner.lambda_handler.run_orchestrator") as mock_run_orchestrator:
        mock_run_orchestrator.return_value = None

        event = {
            "Records": [
                {
                    "body": json.dumps({"job_id": "sqs-job-111"})
                }
            ]
        }
        result = planner_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["success"] is True
        assert "sqs-job-111" in body["message"]
        mock_run_orchestrator.assert_called_once_with("sqs-job-111")


def test_planner_lambda_handler_missing_job_id():
    """Verify planner lambda handler returns 400 when no job_id is provided."""
    planner_handler = get_lambda_handler("planner")

    event = {}
    result = planner_handler(event, None)

    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert body["error"] == "No job_id provided"
