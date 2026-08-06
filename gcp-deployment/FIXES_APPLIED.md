# Fixes Applied to GCP Deployment

This document summarizes the fixes applied to resolve issues encountered during deployment.

## Fix: Missing pg8000 Dependency

### Issue
Reporter, Charter, and Retirement agents were failing with:
```
ModuleNotFoundError: No module named 'pg8000'
```

This prevented agents from connecting to the Cloud SQL database, resulting in 500 Internal Server Error responses.

### Root Cause
The `pg8000` package is a transitive dependency of the `alex-database` package (required by Cloud SQL connector). When using `uv sync --no-install-project` with local path dependencies, transitive dependencies may not be installed correctly.

### Solution
Updated Dockerfiles to explicitly install the database package with all dependencies before syncing main project dependencies:

```dockerfile
# First install database package with all its dependencies (including pg8000)
RUN cd database && uv pip install --system -e . && cd ..
# Then sync the main project dependencies
RUN uv sync --no-install-project
```

### Files Modified
- `backend/reporter/Dockerfile`
- `backend/charter/Dockerfile`
- `backend/retirement/Dockerfile`

### Documentation Added
- `guides/FIX_PG8000_DEPENDENCY.md` - Detailed fix documentation
- Updated `guides/TROUBLESHOOTING.md` - Added troubleshooting section
- Updated `guides/6_agents.md` - Added Dockerfile example with fix
- Updated `README.md` - Added reference to fix documentation

### Verification
After applying the fix:
1. Rebuild Docker images
2. Push to Artifact Registry
3. Update Cloud Run services
4. Verify no more `pg8000` errors in logs
5. Test agent workflow end-to-end

### Status
✅ **Fixed and Verified** - All three agents now work correctly and can connect to the database.

