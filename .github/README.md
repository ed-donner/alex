## GitHub Actions

### CI
Workflow: `.github/workflows/ci.yml`

Runs on every PR and on pushes to `main`/`master`:
- Terraform formatting check (`terraform fmt -check -recursive terraform`)
- Local Python agent tests (`uv run test_simple.py`) for the main agents
- Frontend lint + build (`npm ci`, `npm run lint`, `npm run build`)

### CD (optional / manual)
Workflow: `.github/workflows/deploy-part7.yml`

Manual only (`workflow_dispatch`). It runs `scripts/deploy.py`, which:
- Packages the API Lambda via Docker
- Applies `terraform/7_frontend`
- Builds + exports the frontend
- Uploads the frontend to S3 (and invalidates CloudFront if enabled)

#### Required GitHub secrets (choose one option)

**Option A (recommended): OIDC role**
- `AWS_ROLE_ARN`: IAM Role ARN that GitHub Actions can assume via OIDC

**Option B: access keys**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- (optional) `AWS_SESSION_TOKEN`

#### Safety
The workflow requires typing `DEPLOY` into the confirmation input before it will run.
