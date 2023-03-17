import boto3,json,logging,os,time

from websocket import create_connection

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError,LineBotApiError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,FollowEvent,UnfollowEvent
)

from botocore.exceptions import ClientError

pinpoint = boto3.client('pinpoint')
chat = boto3.client('connectparticipant')
connect = boto3.client('connect')
step_function = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('line-chat-history')

# Set up the Amazon Lex client
lex_client = boto3.client('lex-runtime', region_name='us-east-1')

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
    
    ## Handle Text Message Event
    @handler.add(MessageEvent, message=TextMessage)    
    def handle_text_message(event):
        line_user_id = event.source.user_id
        message = event.message.text
        userProfile = line_bot_api.get_profile(line_user_id)
        line_display_name = userProfile.display_name
        
        ## Start Chat with Agent
        
        if "CHAT" in message.upper():
            start_response = connect.start_chat_contact(
                        InstanceId=os.environ.get('CONNECT_INSTANCE_ID'),
                        ContactFlowId=os.environ.get('CONNECT_CONTACT_FLOW_ID'),
                        Attributes= {
                            'username': line_user_id
                        },
                        ParticipantDetails= {
                            'DisplayName': line_display_name
                        }
                    )
            logging.info("Start Response:")
            logging.info(start_response)
            """
            ## Create Streaming Chat Connection
            streaming_response = connect.start_contact_streaming(
                InstanceId=os.environ.get('CONNECT_INSTANCE_ID'),
                ContactId=start_response['ContactId'],
                ChatStreamingConfiguration={
                    'StreamingEndpointArn': os.environ.get('SNS_TOPIC_ARN')
                },
                ClientToken=start_response['ParticipantToken']
            )
            """
            
            ## Create Participant Connection
            create_response = chat.create_participant_connection(
                        Type=['WEBSOCKET','CONNECTION_CREDENTIALS'],
                        ParticipantToken=start_response['ParticipantToken']
                    )
            logging.info("Create Participant Connection Response:")
            logging.info(create_response)
            
            
            put_record(line_user_id,start_response['ContactId'],start_response['ParticipantToken'],create_response['ConnectionCredentials']['ConnectionToken'])
            
            response = step_function.start_execution(
                    stateMachineArn=os.environ.get('STATE_MACHINE_ARN'),
                    input=json.dumps({'line_user_id': line_user_id,'start_position': 0, 'wait': 0})
                )
            logging.info(response)
        else:
            record = get_record(line_user_id)

            logging.info('Found Record: ')
            logging.info(record)
    
            create_response = chat.create_participant_connection(
                Type=['WEBSOCKET','CONNECTION_CREDENTIALS'],
                ParticipantToken=record['participant_token']
            )
    
            logging.info(create_response)
    
            ws = create_connection(create_response['Websocket']['Url'])
            ws.send('{"topic":"aws/subscribe","content":{"topics":["aws/chat"]}}')
            ws.close()
            logging.info('Closed: ' + create_response['Websocket']['Url'])
    
            response = chat.send_message(
                ContentType='text/plain',
                Content=message,
                ConnectionToken=create_response['ConnectionCredentials']['ConnectionToken']
            )
    
            logging.info(create_response)
        
    
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
    
def put_record(line_user_id, contact_id, participant_token, connection_token):
    table.put_item(
        Item= {
            'line_user_id': line_user_id,
            'contact_id': contact_id,
            'participant_token': participant_token,
            'connection_token': connection_token
        }
    )


def get_record(line_user_id):
    response = table.get_item(
        Key={
            'line_user_id': line_user_id,
        }
    )
    return response['Item']