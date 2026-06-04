variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "ap-south-1"
}

variable "alert_email" {
  description = "Email address to receive cost alert notifications"
  type        = string
}

variable "common_tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default = {
    Project     = "aws-cost-optimizer"
    ManagedBy   = "terraform"
    Environment = "production"
  }
}
