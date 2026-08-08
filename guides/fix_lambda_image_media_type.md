# Plan: Fix Lambda ECR Image Media Type Error

## Goal Description
When deploying the Researcher service to AWS Lambda using `uv run deploy.py` (which runs `terraform apply`), the deployment fails with:

```
InvalidParameterValueException: The image manifest, config or layer media type for the source image ... is not supported.
```

This occurs because modern Docker Desktop engines default to building images in the OCI format with BuildKit-specific attestations (like build provenance). AWS Lambda does not support these OCI manifest types and strictly requires the Docker Image Manifest V2 Schema 2 format.

To resolve this, we will update the `docker build` command in [deploy.py](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/researcher/deploy.py) to include the `--provenance=false` flag, which forces the creation of a compatible legacy manifest.

---

## User Review Required
No breaking changes. This ensures the Docker image is built in a format compatible with AWS Lambda.

---

## Proposed Changes

### Researcher Service Backend
Modify [deploy.py](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/researcher/deploy.py) to append `--provenance=false` to the list of Docker build arguments.

#### [MODIFY] [deploy.py](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/researcher/deploy.py)

```diff
     # Build Docker image
     print(f"\nBuilding Docker image for linux/amd64 with tag: {image_tag}")
     run_command(
         [
             "docker",
             "build",
             "--platform",
             "linux/amd64",
+            "--provenance=false",
             "-t",
             local_image,
             ".",
         ],
         cwd=backend_dir,
     )
```

---

## Verification Plan

### Automated Tests
1. Re-run the deployment script:
   ```bash
   cd backend/researcher
   uv run deploy.py
   ```
2. Verify the script successfully tags, builds, pushes, and applies Terraform without the `InvalidParameterValueException` from Lambda.
