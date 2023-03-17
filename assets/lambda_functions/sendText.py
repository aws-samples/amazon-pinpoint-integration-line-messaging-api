import boto3
import json
import os
from botocore.exceptions import ClientError

from linebot import (
    LineBotApi,
    exceptions
)
from linebot.models import TextSendMessage

cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    # Get Line Secrets from Secrets Manager
    secret = get_secret()
    line_bot_api = LineBotApi(secret["YOUR_CHANNEL_ACCESS_TOKEN"])
    line_user_ids = []
    # Check whether custom data is passed by user
    if event.get("Data") is not None:
        custom_message = event["Data"]
    else:
        custom_message = "Hello, congratulations! You are eligible for a 15% off on hotel bookings and car rental. Chat with us to find out more!"
    # Build Message
    text_message = TextSendMessage(text=custom_message)
    # Loop through all endpoints for lists of users
    for key in event['Endpoints'].keys():
        line_user_ids.append(event['Endpoints'][key]['Address'])
    # Send Message
    try:
        line_bot_api.multicast(line_user_ids, text_message)
    except exceptions as e:
        print(e.status_code)
        print(e.request_id)
        print(e.error.message)
        print(e.error.details)
    return "Line Text Campaign successfully ran"
        
def get_secret():

    secret_arn = os.getenv("secret_arn")
    region_name = os.getenv("secret_region")

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_arn
        )
    except ClientError as e:
        raise e

    # Decrypts secret using the associated KMS key and return a dict
    secret = json.loads(get_secret_value_response['SecretString'])
    return(secret)