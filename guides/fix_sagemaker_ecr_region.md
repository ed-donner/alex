# Plan: Fix SageMaker ECR Region Mismatch

## Goal Description
When deploying SageMaker in a region other than `us-east-1` (such as `us-west-2`), Terraform fails with a `ValidationException` during `aws_sagemaker_model` creation. This is because SageMaker does not support cross-region ECR image pulls, and the default SageMaker image URI in [variables.tf](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/2_sagemaker/variables.tf) is hardcoded to `us-east-1` (`763104351884.dkr.ecr.us-east-1.amazonaws.com/...`).

To fix this, we will update the container image parameter in the SageMaker model definition to dynamically use the selected deployment region (`var.aws_region`) instead of a hardcoded region.

---

## User Review Required
No breaking changes are introduced. This is a standard and robust fix that dynamically adapts to whatever region you configure in `terraform.tfvars`.

---

## Proposed Changes

### SageMaker Terraform Configuration
Modify [main.tf](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/2_sagemaker/main.tf) to use Terraform's `replace` function to substitute `us-east-1` in the image URI with the active `var.aws_region`.

#### [MODIFY] [main.tf](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/2_sagemaker/main.tf)

```diff
 resource "aws_sagemaker_model" "embedding_model" {
   name               = "alex-embedding-model"
   execution_role_arn = aws_iam_role.sagemaker_role.arn
 
   primary_container {
-    image = var.sagemaker_image_uri
+    image = replace(var.sagemaker_image_uri, "us-east-1", var.aws_region)
     environment = {
       HF_MODEL_ID = var.embedding_model_name
       HF_TASK     = "feature-extraction"
     }
   }
```

---

## Verification Plan

### Automated Tests
1. Run `terraform validate` to verify syntax.
2. Run `terraform plan` to inspect the generated plan.

### Manual Verification
1. Run `terraform apply` in [terraform/2_sagemaker](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/terraform/2_sagemaker).
2. Verify the endpoint creates successfully and reaches the `InService` state.
