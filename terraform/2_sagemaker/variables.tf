variable "aws_region" {
  description = "AWS region for resources"
  type        = string
}

variable "sagemaker_image_uri" {
  description = "URI of the SageMaker container image"
  type        = string
  default     = "763104351884.dkr.ecr.${var.aws_region}.amazonaws.com/huggingface-pytorch-inference:1.13.1-transformers4.26.0-cpu-py39-ubuntu20.04"
}

variable "embedding_model_name" {
  description = "Name of the HuggingFace model to use"
  type        = string
  default     = "sentence-transformers/all-MiniLM-L6-v2"
}