output "scheduler_lambda_arn" {
  description = "ARN of the EC2 scheduler Lambda function"
  value       = aws_lambda_function.ec2_scheduler.arn
}

output "sns_topic_arn" {
  description = "ARN of the cost alerts SNS topic"
  value       = aws_sns_topic.cost_alerts.arn
}
