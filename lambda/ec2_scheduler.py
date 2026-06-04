import boto3
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2 = boto3.client("ec2")
sns = boto3.client("sns")


def get_tagged_instances(action_tag):
    """Return instance IDs where the AutoSchedule tag matches the given action."""
    response = ec2.describe_instances(
        Filters=[
            {"Name": f"tag:AutoSchedule", "Values": [action_tag]},
            {"Name": "instance-state-name", "Values": ["running" if action_tag == "stop" else "stopped"]},
        ]
    )
    ids = []
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            ids.append(instance["InstanceId"])
    return ids


def notify_slack(message):
    topic_arn = os.environ.get("SNS_TOPIC_ARN")
    if topic_arn:
        sns.publish(TopicArn=topic_arn, Message=message, Subject="AWS Cost Optimizer")


def handler(event, context):
    action = event.get("action", "stop")
    hour = datetime.utcnow().hour

    # Only run during off-hours for stop, business hours for start
    if action == "stop" and not (hour >= 20 or hour < 6):
        logger.info("Within business hours, skipping stop action")
        return {"status": "skipped", "reason": "business hours"}

    instance_ids = get_tagged_instances(action)

    if not instance_ids:
        logger.info(f"No instances found for action: {action}")
        return {"status": "ok", "instances_affected": 0}

    if action == "stop":
        ec2.stop_instances(InstanceIds=instance_ids)
        msg = f"Stopped {len(instance_ids)} EC2 instance(s): {', '.join(instance_ids)}"
    else:
        ec2.start_instances(InstanceIds=instance_ids)
        msg = f"Started {len(instance_ids)} EC2 instance(s): {', '.join(instance_ids)}"

    logger.info(msg)
    notify_slack(msg)

    return {"status": "ok", "action": action, "instances_affected": len(instance_ids), "instance_ids": instance_ids}
