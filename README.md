# AWS Cost Optimizer

One of the more frustrating things I've seen across multiple teams is how much money quietly leaks in AWS. Instances running over weekends, EBS volumes nobody attached to anything, underutilized resources that just... sit there. This project is what I built to fix that.

It combines Lambda-based automation with EventBridge scheduling and a Slack bot so the team can control things without touching the AWS console.

## What it does

The EC2 scheduler stops tagged instances automatically at 8 PM IST on weekdays and starts them back up at 9 AM. Simple but effective — at Kaleyra this kind of automation saved around 35% in monthly EC2 costs.

The unused resource detector runs on a schedule and surfaces unattached EBS volumes and instances that haven't done meaningful work in the past week (sub-5% CPU average). It dumps a JSON report to S3 so you always have a history of what was flagged and when.

The Slack bot gives the ops team three commands: `/stopinstances`, `/startinstances`, and `/costcheck`. No need to log into AWS for routine control — which matters a lot when you're oncall at odd hours.

## Architecture

```
EventBridge (cron)
    └── Lambda: ec2_scheduler       → stops/starts EC2 by tag
    └── Lambda: unused_detector     → scans for waste, writes to S3

Slack commands (API Gateway → Lambda)
    └── /stopinstances
    └── /startinstances
    └── /costcheck                  → pulls last 30 days from Cost Explorer

SNS Topic → email alerts on every scheduler action
```

## Setup

**Prerequisites:** Terraform >= 1.3, AWS CLI configured, Python 3.12

```bash
cd terraform
terraform init
terraform plan -var="alert_email=your@email.com"
terraform apply
```

Tag any EC2 instance you want the scheduler to manage:

```
AutoSchedule = stop
```

For the Slack bot, deploy `slack_bot/app.py` as a separate Lambda and set:
- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `SCHEDULER_FUNCTION_NAME` → the ARN from Terraform output

## Cost tagging convention

| Tag | Value | Meaning |
|-----|-------|---------|
| AutoSchedule | stop | Scheduler will stop/start this instance |
| Environment | dev/staging | Helps filter in cost reports |

## Notes

The scheduler only acts during off-hours. If you call the Lambda with `action: stop` during business hours it skips — this was an intentional safety net after one incident where a manual trigger ran at the wrong time.

The Terraform state is stored in S3. If you're forking this, update the backend config in `main.tf` with your own bucket.
