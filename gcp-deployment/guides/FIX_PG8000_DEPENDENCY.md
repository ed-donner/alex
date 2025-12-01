# Fix: Missing pg8000 Dependency in Agent Containers

## Problem

When deploying Reporter, Charter, and Retirement agents to Cloud Run, they were failing with:

```
ModuleNotFoundError: No module named 'pg8000'
```

This error occurred when agents tried to connect to the Cloud SQL database. The planner agent worked fine, but the other three agents returned 500 Internal Server Error.

## Root Cause

The `pg8000` package is a dependency of the `alex-database` package (required by the Cloud SQL connector). However, when using `uv sync --no-install-project` in Docker builds, transitive dependencies from local path dependencies may not be installed correctly.

The database package's `pyproject.toml` includes:
```toml
dependencies = [
    "psycopg2-binary>=2.9.9",
    "cloud-sql-python-connector>=1.11.0",
    "pg8000>=1.31.2",  # Required by Cloud SQL connector
    ...
]
```

But when the database package is referenced as a local path dependency (`path = "./database"`), `uv sync` may not install all transitive dependencies.

## Solution

Explicitly install the database package with all its dependencies before syncing the main project dependencies. This ensures that `pg8000` and all other database package dependencies are installed in the container.

### Updated Dockerfile Pattern

For Reporter, Charter, and Retirement agents, update the Dockerfile:

```dockerfile
# Install Python dependencies
# Don't use --frozen because the lock file has the old path
# First install database package with all its dependencies (including pg8000)
# This ensures transitive dependencies from the local path dependency are installed
RUN cd database && uv pip install --system -e . && cd ..
# Then sync the main project dependencies
RUN uv sync --no-install-project
```

### Files Modified

- `backend/reporter/Dockerfile`
- `backend/charter/Dockerfile`
- `backend/retirement/Dockerfile`

## Deployment Steps

1. **Rebuild Docker images:**
   ```bash
   cd backend
   
   # Build each agent
   docker build --platform linux/amd64 \
     -f reporter/Dockerfile \
     -t us-central1-docker.pkg.dev/PROJECT_ID/alex-agents/reporter:latest .
   
   docker build --platform linux/amd64 \
     -f charter/Dockerfile \
     -t us-central1-docker.pkg.dev/PROJECT_ID/alex-agents/charter:latest .
   
   docker build --platform linux/amd64 \
     -f retirement/Dockerfile \
     -t us-central1-docker.pkg.dev/PROJECT_ID/alex-agents/retirement:latest .
   ```

2. **Push to Artifact Registry:**
   ```bash
   gcloud auth configure-docker us-central1-docker.pkg.dev
   
   docker push us-central1-docker.pkg.dev/PROJECT_ID/alex-agents/reporter:latest
   docker push us-central1-docker.pkg.dev/PROJECT_ID/alex-agents/charter:latest
   docker push us-central1-docker.pkg.dev/PROJECT_ID/alex-agents/retirement:latest
   ```

3. **Update Cloud Run services:**
   ```bash
   gcloud run services update alex-reporter \
     --image us-central1-docker.pkg.dev/PROJECT_ID/alex-agents/reporter:latest \
     --region us-central1 \
     --project PROJECT_ID
   
   gcloud run services update alex-charter \
     --image us-central1-docker.pkg.dev/PROJECT_ID/alex-agents/charter:latest \
     --region us-central1 \
     --project PROJECT_ID
   
   gcloud run services update alex-retirement \
     --image us-central1-docker.pkg.dev/PROJECT_ID/alex-agents/retirement:latest \
     --region us-central1 \
     --project PROJECT_ID
   ```

## Verification

After deployment, verify the fix:

1. **Check logs for errors:**
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=~'alex-(reporter|charter|retirement)' AND severity>=ERROR" \
     --limit 20 \
     --format="table(timestamp,resource.labels.service_name,severity,textPayload)" \
     --project=PROJECT_ID \
     --freshness=10m
   ```
   
   Should see no more `ModuleNotFoundError: No module named 'pg8000'` errors.

2. **Trigger a test analysis:**
   - Go to frontend → Advisor Team page
   - Click "Run Analysis"
   - Verify results appear (report, charts, retirement analysis)

3. **Check agent logs for successful database connections:**
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=alex-reporter AND textPayload=~'saved|completed'" \
     --limit 10 \
     --format="table(timestamp,textPayload)" \
     --project=PROJECT_ID \
     --freshness=10m
   ```

## Why This Works

- `uv pip install --system -e .` installs the database package in editable mode with all its dependencies
- The `--system` flag installs to the system Python (required in Docker containers without a virtual environment)
- Installing the database package first ensures `pg8000` is available before `uv sync` runs
- `uv sync` then installs the remaining project dependencies, which can now find `pg8000` if needed

## Alternative Solutions Considered

1. **Adding pg8000 directly to agent dependencies:** This would work but duplicates the dependency and could lead to version conflicts.

2. **Using `uv sync` without `--no-install-project`:** This would install the project itself, but we want to keep the build minimal.

3. **Installing pg8000 separately:** This works but doesn't address the root cause - other transitive dependencies might also be missing.

The chosen solution (explicitly installing the database package) is the most robust as it ensures all database package dependencies are installed correctly.

## Related Files

- `backend/database/pyproject.toml` - Database package dependencies
- `backend/database/src/cloudsql_client.py` - Database client that requires pg8000
- `backend/reporter/Dockerfile` - Reporter agent Dockerfile
- `backend/charter/Dockerfile` - Charter agent Dockerfile
- `backend/retirement/Dockerfile` - Retirement agent Dockerfile

