# Plan: Disable Hugging Face Transfer on SageMaker Model

## Goal Description
The SageMaker endpoint fails to deploy (`Failed` status) because the underlying container's Model Server process exits unexpectedly with a `RuntimeError` during model weight download. The CloudWatch logs show:

```
RuntimeError: An error occurred while downloading using `hf_transfer`. Consider disabling HF_HUB_ENABLE_HF_TRANSFER for better error handling.
```

The new Hugging Face PyTorch inference container enables `hf_transfer` (a Rust-based downloader) by default. However, it regularly fails in serverless environments, causing the model server process to crash. 

To fix this, we will disable `hf_transfer` by setting the environment variable `HF_HUB_ENABLE_HF_TRANSFER` to `"0"` in the SageMaker model configuration, falling back to the stable python downloader.

---

## User Review Required
No breaking changes. This falls back to standard HTTP downloading which is extremely stable.

---

## Proposed Changes

### SageMaker Terraform Configuration
Update [main.tf](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/2_sagemaker/main.tf) to set `HF_HUB_ENABLE_HF_TRANSFER = "0"` in the container environment.

#### [MODIFY] [main.tf](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/2_sagemaker/main.tf)

```diff
 resource "aws_sagemaker_model" "embedding_model" {
   name               = "alex-embedding-model"
   execution_role_arn = aws_iam_role.sagemaker_role.arn
 
   primary_container {
     image = replace(var.sagemaker_image_uri, "us-east-1", var.aws_region)
     environment = {
-      HF_MODEL_ID = var.embedding_model_name
-      HF_TASK     = "feature-extraction"
+      HF_MODEL_ID               = var.embedding_model_name
+      HF_TASK                   = "feature-extraction"
+      HF_HUB_ENABLE_HF_TRANSFER = "0"
     }
   }
```

---

## Verification Plan

### Automated Tests
1. Validate Terraform syntax:
   ```bash
   cd terraform/2_sagemaker
   terraform validate
   ```

### Manual Verification
1. Re-run deployment:
   ```bash
   cd terraform/2_sagemaker
   terraform apply
   ```
2. Verify endpoint successfully starts and reaches `InService` status.
