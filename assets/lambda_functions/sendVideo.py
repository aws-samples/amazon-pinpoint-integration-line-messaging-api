import boto3
import json
import os
from botocore.exceptions import ClientError

from linebot import (
    LineBotApi,
    exceptions
)
from linebot.models import VideoSendMessage

cloudwatch = boto3.client('cloudwatch')
s3 = boto3.client('s3')

def lambda_handler(event, context):
    # Get Line Secrets from Secrets Manager
    secret = get_secret()
    line_bot_api = LineBotApi(secret["YOUR_CHANNEL_ACCESS_TOKEN"])
    line_user_ids = []
    # Check whether custom data is passed by user
    if event.get("Data") is not None:
        video_file_key = event["Data"]["video_file_key"]
        video_image_key = event["Data"]["video_image_key"]
    else:
        video_file_key = "sample_video.mp4"
        video_image_key = "sample_image.jpg"
    # Generate a presigned URL for the video file
    try:
        video_presigned_url = s3.generate_presigned_url("get_object",
                                                Params={
                                                    "Bucket": os.getenv("video_bucket"),
                                                    "Key": video_file_key},
                                                ExpiresIn=3600)
    except ClientError as e:
        print.error(e)
        return None
    # Generate a presigned URL for the cover image file
    try:
        video_image_presigned_url = s3.generate_presigned_url("get_object",
                                                Params={
                                                    "Bucket": "line-video-files",
                                                    "Key": video_image_key},
                                                ExpiresIn=3600)
    except ClientError as e:
        print.error(e)
        return None
    # Build Message
    video_message = VideoSendMessage(
        original_content_url=video_presigned_url,
        preview_image_url=video_image_presigned_url
        )
    # Loop through all endpoints for lists of users
    for key in event['Endpoints'].keys():
        line_user_ids.append(event['Endpoints'][key]['Address'])
    # Send Message
    try:
        line_bot_api.multicast(line_user_ids, video_message)
    except exceptions as e:
        print(e.status_code)
        print(e.request_id)
        print(e.error.message)
        print(e.error.details)
    return "Line video Campaign successfully ran"
        
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