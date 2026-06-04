import boto3
import json
import os
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2 = boto3.client("ec2")
cloudwatch = boto3.client("cloudwatch")


def get_unattached_ebs_volumes():
    response = ec2.describe_volumes(Filters=[{"Name": "status", "Values": ["available"]}])
    volumes = []
    for v in response["Volumes"]:
        name = next((t["Value"] for t in v.get("Tags", []) if t["Key"] == "Name"), v["VolumeId"])
        volumes.append({
            "id": v["VolumeId"],
            "name": name,
            "size_gb": v["Size"],
            "type": v["VolumeType"],
            "created": v["CreateTime"].isoformat(),
        })
    return volumes


def get_idle_ec2_instances():
    """Find instances with < 5% average CPU over the past 7 days."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)

    response = ec2.describe_instances(
        Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
    )

    idle = []
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            instance_id = instance["InstanceId"]
            metrics = cloudwatch.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start,
                EndTime=end,
                Period=86400,
                Statistics=["Average"],
            )
            if metrics["Datapoints"]:
                avg_cpu = sum(d["Average"] for d in metrics["Datapoints"]) / len(metrics["Datapoints"])
                if avg_cpu < 5.0:
                    name = next((t["Value"] for t in instance.get("Tags", []) if t["Key"] == "Name"), instance_id)
                    idle.append({"id": instance_id, "name": name, "avg_cpu_7d": round(avg_cpu, 2)})

    return idle


def handler(event, context):
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "unattached_volumes": get_unattached_ebs_volumes(),
        "idle_instances": get_idle_ec2_instances(),
    }

    logger.info(json.dumps(report))

    # Optionally push to S3
    bucket = os.environ.get("REPORT_BUCKET")
    if bucket:
        s3 = boto3.client("s3")
        key = f"cost-reports/{datetime.now(timezone.utc).strftime('%Y/%m/%d')}/unused_resources.json"
        s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(report, indent=2))
        logger.info(f"Report saved to s3://{bucket}/{key}")

    return report
