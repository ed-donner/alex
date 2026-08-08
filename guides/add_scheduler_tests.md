# Plan: Configure Poetry and Create Scheduler Unit Tests (Simplified)

## Goal Description
We will add a new test suite for the scheduler Lambda function located at [lambda_function.py](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/scheduler/lambda_function.py).

To do this, we will:
1. Configure `poetry` in the `backend` folder by adding `[tool.poetry]` configurations to [pyproject.toml](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/pyproject.toml) without including the local `alex-database` package, keeping the test environment minimal.
2. Create the [tests/scheduler/test_lambda_function.py](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/tests/scheduler/test_lambda_function.py) file.
3. Implement unit tests covering URL normalization and the Lambda handler invocation using mocked network requests.

---

## User Review Required
No breaking changes. This only adds testing configurations and unit tests.

---

## Proposed Changes

### Backend Dependencies & Test Configurations
Modify [pyproject.toml](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/pyproject.toml) to configure Poetry and `pytest`. We will configure `pytest` to include `scheduler` in the pythonpath. We exclude `alex-database` since it is not needed for the scheduler tests.

#### [MODIFY] [pyproject.toml](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/pyproject.toml)

```diff
 [project]
 name = "backend"
 version = "0.1.0"
 requires-python = ">=3.12"
 dependencies = [
     "alex-database",
     "boto3>=1.40.29",
     "langfuse>=3.3.4",
     "openai-agents>=0.3.0",
     "pydantic-ai>=1.0.6",
     "python-dotenv>=1.1.1",
 ]
 
 [tool.uv.workspace]
 members = [
     "database",
     "api",
     "scheduler",
 ]
 
 [tool.uv.sources]
 alex-database = { workspace = true }
+
+[tool.poetry]
+name = "backend"
+version = "0.1.0"
+description = "Alex Backend"
+authors = ["Your Name <you@example.com>"]
+readme = "README.md"
+packages = []
+
+[tool.poetry.dependencies]
+python = ">=3.12"
+boto3 = ">=1.40.29"
+langfuse = ">=3.3.4"
+openai-agents = ">=0.3.0"
+pydantic-ai = ">=1.0.6"
+python-dotenv = ">=1.1.1"
+loguru = "^0.7.2"
+
+[tool.poetry.group.dev.dependencies]
+pytest = "^8.0.0"
+
+[tool.pytest.ini_options]
+pythonpath = [
+  "scheduler"
+]
```

---

### Scheduler Unit Tests
Create [test_lambda_function.py](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/tests/scheduler/test_lambda_function.py) under the new `backend/tests/scheduler/` directory.

#### [NEW] [test_lambda_function.py](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/tests/scheduler/test_lambda_function.py)

```python
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
```

---

## Verification Plan

### Automated Tests
Execute the following commands from the `/Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend` directory:

1. Install backend dependencies using Poetry:
   ```bash
   poetry install
   ```
2. Run the newly created scheduler unit tests:
   ```bash
   poetry run pytest tests/scheduler/
   ```
