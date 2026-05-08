terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"  # Use latest stable version
    }
  }
  required_version = ">= 1.0"
}
