# Walkthrough - Scheduler Unit Tests

We have successfully configured the `backend` environment to support Poetry and implemented unit tests for the scheduler Lambda function.

## Changes Made

### 1. Backend Package Configuration
We modified [pyproject.toml](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/pyproject.toml) to add Poetry and `pytest` settings:
- Defined the project metadata and core dependencies for Poetry (`boto3`, `langfuse`, `openai-agents`, `pydantic-ai`, `python-dotenv`, `loguru`).
- Configured a Python version constraint compatible with the dependencies (`>=3.12,<4.0`).
- Configured `pytest` settings to append `scheduler/` to the Python path dynamically during test execution.

### 2. Test Suite Creation
We created a new unit test suite at [test_lambda_function.py](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/tests/scheduler/test_lambda_function.py) covering the following:
- **URL Parsing & Validation (`_normalize_url`)**:
  - Verifies that `http://` and `https://` schemas are correctly removed.
  - Verifies that unsupported schemas or missing schemas correctly raise a `ValueError`.
- **Request Generation & Lambda Invocation (`_trigger_lambda_request`)**:
  - Tests HTTP POST request creation and network triggering using `unittest.mock.patch` to mock `urllib.request.urlopen`.
- **Lambda Handler (`handler`)**:
  - Verifies the handler correctly normalizes the URL and fires the request when the `APP_RUNNER_URL` environment variable is present.
  - Verifies the handler correctly raises a `ValueError` when the required environment variable is missing.

---

## Verification Results

We successfully resolved backend dependencies and executed the tests using Poetry.

```bash
poetry run pytest tests/scheduler/
```

### Output:
```
============================= test session starts ==============================
platform darwin -- Python 3.14.6, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/aponte/personal_workspace/agent_engineering_production_udemy.nosync/projects/alex/backend
configfile: pyproject.toml
plugins: anyio-4.14.2, logfire-4.38.0
collected 5 items

tests/scheduler/test_lambda_function.py .....                            [100%]

============================== 5 passed in 0.09s ===============================
```
