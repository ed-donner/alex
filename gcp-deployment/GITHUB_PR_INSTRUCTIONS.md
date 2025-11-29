# GitHub Pull Request Instructions

This guide will help you create a pull request from your fork to submit the GCP deployment to the community contributions branch.

## Prerequisites

1. You have a fork of the repository at: https://github.com/TheTopDeveloper/alex
2. You have `git` installed and configured
3. You have the `gcp-deployment` directory ready in your local workspace

## Step-by-Step Instructions

### Step 1: Navigate to Your Repository Root

```bash
# Navigate to your alex repository root (not gcp-deployment)
cd /path/to/your/alex/repository
```

### Step 2: Check Current Remote Configuration

```bash
# Check your current remotes
git remote -v
```

You should see:
- `origin` pointing to your fork: `https://github.com/TheTopDeveloper/alex.git`
- Optionally `upstream` pointing to the original: `https://github.com/ed-donner/alex.git`

If you don't have the upstream remote, add it:

```bash
git remote add upstream https://github.com/ed-donner/alex.git
```

### Step 3: Fetch Latest Changes

```bash
# Fetch latest changes from upstream
git fetch upstream

# Update your main branch
git checkout main
git pull upstream main
```

### Step 4: Create a New Branch for Community Contributions

```bash
# Create and switch to a new branch
git checkout -b community-contributions-branch

# Or if the branch already exists:
git checkout community-contributions-branch
git pull upstream main  # Update with latest changes
```

### Step 5: Copy gcp-deployment to Repository

**Option A: If gcp-deployment is in the parent directory**

```bash
# From your alex repository root
cp -r ../gcp-deployment ./gcp-deployment

# On Windows PowerShell:
Copy-Item -Path ..\gcp-deployment -Destination .\gcp-deployment -Recurse
```

**Option B: If gcp-deployment is already in your repository**

```bash
# Just ensure it's in the right location
ls -la gcp-deployment/
```

### Step 6: Stage and Commit Changes

```bash
# Add the gcp-deployment directory
git add gcp-deployment/

# Check what will be committed
git status

# Commit with a descriptive message
git commit -m "Add GCP deployment alternative for Alex Multi-Agent SaaS

- Complete GCP-native deployment using Cloud Run, Vertex AI, and Cloud SQL
- Removed all AWS fallback code for clean GCP-only implementation
- Replaced all secrets with generic placeholders
- Added comprehensive AWS to GCP service mapping documentation
- Consolidated troubleshooting guides
- Updated README with GCP vs AWS resource comparison

Key features:
- Cloud Run for serverless agents (replaces Lambda)
- Vertex AI with Gemini 2.0 Flash (replaces Bedrock)
- Cloud SQL PostgreSQL (replaces Aurora)
- Cloud Pub/Sub (replaces SQS)
- Artifact Registry (replaces ECR)
- Secret Manager integration
- Complete Terraform infrastructure as code"
```

### Step 7: Push to Your Fork

```bash
# Push the branch to your fork
git push origin community-contributions-branch

# If this is the first push, set upstream:
git push -u origin community-contributions-branch
```

### Step 8: Create Pull Request on GitHub

1. **Go to your fork on GitHub:**
   - Navigate to: https://github.com/TheTopDeveloper/alex

2. **You should see a banner** saying "community-contributions-branch had recent pushes" with a "Compare & pull request" button. Click it.

   OR

   **Manually create PR:**
   - Click the "Pull requests" tab
   - Click "New pull request"
   - Set base repository: `ed-donner/alex`
   - Set base branch: `community-contributions-branch` (or `main` if that's where contributions go)
   - Set compare repository: `TheTopDeveloper/alex`
   - Set compare branch: `community-contributions-branch`
   - Click "Create pull request"

3. **Fill in the PR details:**

   **Title:**
   ```
   Add GCP Deployment Alternative for Alex Multi-Agent SaaS
   ```

   **Description:**
   ```markdown
   ## Overview
   
   This PR adds a complete GCP-native deployment alternative for the Alex Multi-Agent SaaS application. This is a clean, production-ready implementation that replaces AWS services with their GCP equivalents.

   ## What's Included
   
   ### Infrastructure
   - ✅ Complete Terraform configurations for all deployment phases
   - ✅ Cloud Run services for all agents (Planner, Tagger, Reporter, Charter, Retirement)
   - ✅ Cloud SQL PostgreSQL database setup
   - ✅ Cloud Pub/Sub for message queuing
   - ✅ Vertex AI integration with Gemini 2.0 Flash
   - ✅ Artifact Registry for container images
   - ✅ Secret Manager integration
   - ✅ Frontend deployment with Cloud CDN

   ### Code Changes
   - ✅ Removed all AWS fallback code (GCP-only implementation)
   - ✅ Replaced hardcoded secrets with environment variables and Secret Manager
   - ✅ Updated database client to use Cloud SQL exclusively
   - ✅ Replaced AWS SageMaker/S3 Vectors with placeholder for GCP vector search
   - ✅ Updated all service references from AWS to GCP equivalents

   ### Documentation
   - ✅ Comprehensive AWS to GCP service mapping guide
   - ✅ Detailed architecture comparison
   - ✅ Step-by-step deployment guides for each phase
   - ✅ Combined troubleshooting guide
   - ✅ Updated README with GCP vs AWS resource comparison
   - ✅ Cost comparison and optimization recommendations

   ## Key Differences from AWS Version
   
   | AWS Service | GCP Equivalent |
   |-------------|----------------|
   | Lambda | Cloud Run |
   | Bedrock | Vertex AI (Gemini 2.0 Flash) |
   | Aurora Serverless | Cloud SQL PostgreSQL |
   | SQS | Cloud Pub/Sub |
   | ECR | Artifact Registry |
   | SageMaker | Vertex AI Embeddings API |

   ## Testing
   
   - [x] All Terraform configurations tested
   - [x] Cloud Run services deploy successfully
   - [x] Database connections working
   - [x] Pub/Sub message flow verified
   - [x] Frontend deployment tested

   ## Files Changed
   
   - New directory: `gcp-deployment/` with complete GCP implementation
   - All secrets replaced with generic placeholders
   - All AWS-specific code removed

   ## Notes
   
   - This is a complete, standalone GCP deployment
   - No dependencies on AWS services
   - Uses Gemini 2.0 Flash as the recommended LLM (cost-effective alternative to Claude)
   - Vector search functionality marked as TODO (needs GCP implementation)

   ## Related
   
   This addresses the community contribution request for GCP deployment alternative.
   ```

4. **Add labels** (if you have permission):
   - `community-contribution`
   - `gcp`
   - `infrastructure`

5. **Click "Create pull request"**

### Step 9: Monitor Your Pull Request

- GitHub will run any CI/CD checks automatically
- The maintainer will review your PR
- Respond to any feedback or requested changes

## Troubleshooting

### If you get "branch already exists" error:

```bash
# Delete local branch and recreate
git branch -D community-contributions-branch
git checkout -b community-contributions-branch
```

### If you need to update your PR:

```bash
# Make changes to files
git add .
git commit -m "Update: description of changes"
git push origin community-contributions-branch
```

The PR will automatically update with your new commits.

### If you need to sync with upstream:

```bash
# Fetch latest from upstream
git fetch upstream

# Merge upstream changes into your branch
git checkout community-contributions-branch
git merge upstream/main

# Resolve any conflicts, then push
git push origin community-contributions-branch
```

## Quick Reference Commands

```bash
# Complete workflow in one go (after initial setup)
cd /path/to/alex
git checkout -b community-contributions-branch
cp -r ../gcp-deployment ./
git add gcp-deployment/
git commit -m "Add GCP deployment alternative"
git push -u origin community-contributions-branch
```

Then create the PR on GitHub as described in Step 8.

## Additional Notes

- Make sure `.gitignore` is properly configured to exclude sensitive files
- Double-check that no API keys or secrets are committed
- Ensure all `terraform.tfvars` files are excluded (only `.example` files should be committed)
- Verify that the `gcp-deployment` directory structure is complete

Good luck with your pull request! 🚀

