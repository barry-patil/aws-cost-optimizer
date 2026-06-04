from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
import boto3
import os
import json

app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
    process_before_response=True,
)

lambda_client = boto3.client("lambda")


def invoke_scheduler(action):
    response = lambda_client.invoke(
        FunctionName=os.environ["SCHEDULER_FUNCTION_NAME"],
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": action}),
    )
    result = json.loads(response["Payload"].read())
    return result


@app.command("/stopinstances")
def stop_instances(ack, respond, command):
    ack()
    result = invoke_scheduler("stop")
    count = result.get("instances_affected", 0)
    if count == 0:
        respond("No running instances found with AutoSchedule tag.")
    else:
        respond(f"Stopped {count} instance(s). Check CloudWatch for details.")


@app.command("/startinstances")
def start_instances(ack, respond, command):
    ack()
    result = invoke_scheduler("start")
    count = result.get("instances_affected", 0)
    if count == 0:
        respond("No stopped instances found with AutoSchedule tag.")
    else:
        respond(f"Started {count} instance(s).")


@app.command("/costcheck")
def cost_check(ack, respond):
    ack()
    ce = boto3.client("ce", region_name="us-east-1")
    from datetime import datetime, timedelta
    end = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    response = ce.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
    )
    total = response["ResultsByTime"][0]["Total"]["UnblendedCost"]
    respond(f"AWS spend last 30 days: ${float(total['Amount']):.2f} ({total['Unit']})")


def handler(event, context):
    slack_handler = SlackRequestHandler(app=app)
    return slack_handler.handle(event, context)
