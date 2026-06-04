terraform {
  required_version = ">= 1.3"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "pratik-terraform-state"
    key    = "aws-cost-optimizer/terraform.tfstate"
    region = "ap-south-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# IAM role for the scheduler Lambda
resource "aws_iam_role" "scheduler_role" {
  name = "ec2-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler_policy" {
  name = "ec2-scheduler-policy"
  role = aws_iam_role.scheduler_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ec2:DescribeInstances", "ec2:StartInstances", "ec2:StopInstances"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.cost_alerts.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Lambda function for EC2 scheduling
data "archive_file" "scheduler_zip" {
  type        = "zip"
  source_file = "${path.module}/../lambda/ec2_scheduler.py"
  output_path = "${path.module}/scheduler.zip"
}

resource "aws_lambda_function" "ec2_scheduler" {
  filename         = data.archive_file.scheduler_zip.output_path
  function_name    = "ec2-cost-scheduler"
  role             = aws_iam_role.scheduler_role.arn
  handler          = "ec2_scheduler.handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.scheduler_zip.output_base64sha256
  timeout          = 60

  environment {
    variables = {
      SNS_TOPIC_ARN = aws_sns_topic.cost_alerts.arn
    }
  }

  tags = var.common_tags
}

# EventBridge rules
resource "aws_cloudwatch_event_rule" "stop_schedule" {
  name                = "ec2-stop-schedule"
  description         = "Stop tagged EC2 instances at 8 PM IST"
  schedule_expression = "cron(30 14 ? * MON-FRI *)"
}

resource "aws_cloudwatch_event_rule" "start_schedule" {
  name                = "ec2-start-schedule"
  description         = "Start tagged EC2 instances at 9 AM IST"
  schedule_expression = "cron(30 3 ? * MON-FRI *)"
}

resource "aws_cloudwatch_event_target" "stop_target" {
  rule  = aws_cloudwatch_event_rule.stop_schedule.name
  arn   = aws_lambda_function.ec2_scheduler.arn
  input = jsonencode({ action = "stop" })
}

resource "aws_cloudwatch_event_target" "start_target" {
  rule  = aws_cloudwatch_event_rule.start_schedule.name
  arn   = aws_lambda_function.ec2_scheduler.arn
  input = jsonencode({ action = "start" })
}

resource "aws_lambda_permission" "allow_eventbridge_stop" {
  statement_id  = "AllowEventBridgeStop"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ec2_scheduler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.stop_schedule.arn
}

resource "aws_lambda_permission" "allow_eventbridge_start" {
  statement_id  = "AllowEventBridgeStart"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ec2_scheduler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.start_schedule.arn
}

# SNS topic for alerts
resource "aws_sns_topic" "cost_alerts" {
  name = "aws-cost-alerts"
  tags = var.common_tags
}

resource "aws_sns_topic_subscription" "email_alert" {
  topic_arn = aws_sns_topic.cost_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
