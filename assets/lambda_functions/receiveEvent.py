import boto3,json,logging,os

from websocket import create_connection

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError,LineBotApiError
)
from linebot.models import (
    FollowEvent,UnfollowEvent
)

from botocore.exceptions import ClientError

pinpoint = boto3.client('pinpoint')


def lambda_handler(event,context):
    # Set up logging
    global log_level
    log_level = str(os.environ.get('LOG_LEVEL')).upper()
    if log_level not in [
                              'DEBUG', 'INFO',
                              'WARNING', 'ERROR',
                              'CRITICAL'
                          ]:
        log_level = 'INFO'
    logging.getLogger().setLevel(log_level)
    logging.info('## EVENT')
    logging.info(event)
    
    # Get Line Secrets from Secrets Manager
    secret = get_secret()
    line_bot_api = LineBotApi(secret['YOUR_CHANNEL_ACCESS_TOKEN'])
    handler = WebhookHandler(secret['YOUR_CHANNEL_SECRET'])
    
    ## Handle Follow Event and add the user to Pinpoint Endpoint
    @handler.add(FollowEvent)
    def handle_follow(event):
        userId = event.source.user_id
        userProfile = line_bot_api.get_profile(userId)
        response = pinpoint.update_endpoint(
            ApplicationId=os.getenv('pinpoint_app_id'),
            EndpointId=userId,
            EndpointRequest={
                'Address': userId,
                'ChannelType': 'CUSTOM',
                'OptOut': 'NONE',
                'User': {
                    'UserAttributes': {
                        'DisplayName': [userProfile.display_name]
                    },
                    'UserId': userId
                }
            })
            
    ## Handle Unfollow Event and delete the endpoint
    @handler.add(UnfollowEvent)
    def handle_unfollow(event):
        userId = event.source.user_id
        response = pinpoint.delete_endpoint(
            ApplicationId=os.getenv('pinpoint_app_id'),
            EndpointId=userId)
            
    ### TEST SIGNATURE/LINE_BOT_API ERROR
    try:
        signature = event['headers']['x-line-signature']
        body = event['body']
        handler.handle(body, signature)
    except InvalidSignatureError:
        return {
            'statusCode': 400,
            'body': json.dumps('InvalidSignatureError') }        
    except LineBotApiError as e:
        return {
            'statusCode': 400,
            'body': json.dumps('LineBotApiError') }
    ### Return HTTP 200 for valid Webhook Endpoint
    return {
        'statusCode': 200,
        'body': json.dumps('OK') }


### HELPER FUNCTIONS
# Function to get secret        
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