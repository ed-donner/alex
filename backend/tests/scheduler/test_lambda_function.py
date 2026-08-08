import json
import os
import pytest
from unittest.mock import patch, MagicMock
from urllib.request import Request

from lambda_function import handler, _normalize_url, _trigger_lambda_request

def test_normalize_url_valid():
    """Verify normalization of http/https URLs."""
    assert _normalize_url("https://my-app-runner.com") == "my-app-runner.com"
    assert _normalize_url("http://my-app-runner.com") == "my-app-runner.com"

def test_normalize_url_invalid():
    """Verify invalid URL schemes raise ValueError."""
    with pytest.raises(ValueError, match="Invalid url scheme"):
        _normalize_url("ftp://my-app-runner.com")
    with pytest.raises(ValueError, match="Invalid url scheme"):
        _normalize_url("my-app-runner.com")

@patch('urllib.request.urlopen')
def test_trigger_lambda_request_success(mock_urlopen):
    """Verify successful execution of _trigger_lambda_request with mocked urlopen."""
    # Set up mock response context manager
    mock_response = MagicMock()
    mock_response.read.return_value = b"research_agent_output"
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    req = Request("https://example.com/research", data=b"{}", method="POST")
    result = _trigger_lambda_request(req, 180)

    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert body['message'] == 'Research triggered successfully'
    assert body['result'] == 'research_agent_output'

@patch('urllib.request.urlopen')
@patch.dict(os.environ, {"APP_RUNNER_URL": "https://my-app-runner.com"})
def test_handler_success(mock_urlopen):
    """Verify successful lambda handler execution when env var is present."""
    # Set up mock response context manager
    mock_response = MagicMock()
    mock_response.read.return_value = b"success"
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    event = {}
    context = {}
    result = handler(event, context)

    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert body['message'] == 'Research triggered successfully'
    assert body['result'] == 'success'

    # Verify mock_urlopen was called with correct parameters
    args, kwargs = mock_urlopen.call_args
    req = args[0]
    assert req.full_url == "https://my-app-runner.com/research"
    assert req.method == "POST"
    assert kwargs['timeout'] == 180

@patch.dict(os.environ, {}, clear=True)
def test_handler_missing_env_var():
    """Verify ValueError is raised if APP_RUNNER_URL env var is missing."""
    event = {}
    context = {}
    with pytest.raises(ValueError, match="`APP_RUNNER_URL` environment variable not set"):
        handler(event, context)
