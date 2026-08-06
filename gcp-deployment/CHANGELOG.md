# Changelog

## [Unreleased]

### Fixed
- **Missing pg8000 dependency in agent containers**: Fixed `ModuleNotFoundError: No module named 'pg8000'` in Reporter, Charter, and Retirement agents by explicitly installing the database package with all dependencies before syncing main project dependencies. See [guides/FIX_PG8000_DEPENDENCY.md](guides/FIX_PG8000_DEPENDENCY.md) for details.

### Changed
- Updated Dockerfiles for Reporter, Charter, and Retirement agents to explicitly install database package dependencies
- Added troubleshooting section for pg8000 dependency issue

### Files Modified
- `backend/reporter/Dockerfile`
- `backend/charter/Dockerfile`
- `backend/retirement/Dockerfile`
- `guides/TROUBLESHOOTING.md`
- `guides/FIX_PG8000_DEPENDENCY.md` (new)

