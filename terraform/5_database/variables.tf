variable "aws_region" {
  description = "AWS region for resources"
  type        = string
}

variable "aurora_cluster_arn" {
  description = "ARN of the Aurora Express cluster, populated by bootstrap/setup_aurora_express.py via bootstrap.auto.tfvars.json"
  type        = string
  default     = ""
}

variable "database_name" {
  description = "Application database name"
  type        = string
  default     = "alex"
}
