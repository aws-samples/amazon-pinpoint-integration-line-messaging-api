import os
import json
from aws_cdk import (
    Stack,
    aws_lambda_python_alpha as _python,
    aws_lambda as _lambda,
    aws_secretsmanager as _secrets,
    aws_pinpoint as _pinpoint,
    aws_iam as _iam,
    SecretValue,
    aws_s3 as _s3,
    aws_s3_deployment as _s3_deploy,
    aws_cloudfront as _cloudfront,
    RemovalPolicy
)
from constructs import Construct

from aws_solutions_constructs.aws_cloudfront_apigateway_lambda import CloudFrontToApiGatewayToLambda

class Part1Stack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Initialize Bucket
        image_bucket = _s3.Bucket(self,"image_s3_bucket",block_public_access=_s3.BlockPublicAccess.BLOCK_ALL,enforce_ssl=True,versioned=True,access_control=_s3.BucketAccessControl.LOG_DELIVERY_WRITE,server_access_logs_prefix='access-logs',removal_policy=RemovalPolicy.DESTROY)
        audio_bucket = _s3.Bucket(self,"audio_s3_bucket",block_public_access=_s3.BlockPublicAccess.BLOCK_ALL,enforce_ssl=True,versioned=True,access_control=_s3.BucketAccessControl.LOG_DELIVERY_WRITE,server_access_logs_prefix='access-logs',removal_policy=RemovalPolicy.DESTROY)
        video_bucket = _s3.Bucket(self,"video_s3_bucket",block_public_access=_s3.BlockPublicAccess.BLOCK_ALL,enforce_ssl=True,versioned=True,access_control=_s3.BucketAccessControl.LOG_DELIVERY_WRITE,server_access_logs_prefix='access-logs',removal_policy=RemovalPolicy.DESTROY)
        # Deploy Sample Files onto Buckets
        image_bucket_deployment = _s3_deploy.BucketDeployment(self,"image_bucket_deploy",destination_bucket=image_bucket,sources=[_s3_deploy.Source.asset("./assets/files/image_files/")])
        audio_bucket_deployment = _s3_deploy.BucketDeployment(self,"audio_bucket_deploy",destination_bucket=audio_bucket,sources=[_s3_deploy.Source.asset("./assets/files/audio_files/")])
        video_bucket_deployment = _s3_deploy.BucketDeployment(self,"video_bucket_deploy",destination_bucket=video_bucket,sources=[_s3_deploy.Source.asset("./assets/files/video_files/")])

        # Initialize Pinpoint Project
        pinpoint_project = _pinpoint.CfnApp(self,"line-pinpoint-project",name="Line-Pinpoint-Project")
        # Create Line credential Placeholder Secrets in AWS Secret Manager
        line_credentials = _secrets.Secret(self,"line-credentials",secret_name="line_secrets",secret_object_value={
            "YOUR_CHANNEL_ACCESS_TOKEN": SecretValue.unsafe_plain_text("INSERT_CHANNEL_TOKEN"),
            "YOUR_CHANNEL_SECRET": SecretValue.unsafe_plain_text("INSERT_CHANNEL_SECRET")
        })

        # Create a lambda layer that is shared between different functions
        shared_lambda_layer = _python.PythonLayerVersion(self,"shared_lambda_layer",entry="./assets/lambda_layers",compatible_runtimes=[_lambda.Runtime.PYTHON_3_9])
        # Create sendText Lambda Function
        send_text_lambda = _python.PythonFunction(self,"send_text_lambda",entry="./assets/lambda_functions",runtime=_lambda.Runtime.PYTHON_3_9,index="sendText.py",handler="lambda_handler",description="Lambda function used by Amazon Pinpoint to send Text messages via LINE",layers=[shared_lambda_layer],environment={
                                        "secret_arn": line_credentials.secret_arn,
                                        "secret_region": os.environ["CDK_DEFAULT_REGION"]
                                    })
        # Create sendImage Lambda Function
        send_image_lambda = _python.PythonFunction(self,"send_image_lambda",entry="./assets/lambda_functions",runtime=_lambda.Runtime.PYTHON_3_9,index="sendImage.py",handler="lambda_handler",description="Lambda function used by Amazon Pinpoint to send Image messages via LINE",layers=[shared_lambda_layer],environment={
                                        "secret_arn": line_credentials.secret_arn,
                                        "secret_region": os.environ["CDK_DEFAULT_REGION"],
                                        "image_bucket": image_bucket.bucket_name
                                    })
        # Create sendAudio Lambda Function
        send_audio_lambda = _python.PythonFunction(self,"send_audio_lambda",entry="./assets/lambda_functions",runtime=_lambda.Runtime.PYTHON_3_9,index="sendAudio.py",handler="lambda_handler",description="Lambda function used by Amazon Pinpoint to send Audio messages via LINE",layers=[shared_lambda_layer],environment={
                                        "secret_arn": line_credentials.secret_arn,
                                        "secret_region": os.environ["CDK_DEFAULT_REGION"],
                                        "audio_bucket": audio_bucket.bucket_name

                                    })
        # Create sendVideo Lambda Function
        send_video_lambda = _python.PythonFunction(self,"send_video_lambda",entry="./assets/lambda_functions",runtime=_lambda.Runtime.PYTHON_3_9,index="sendVideo.py",handler="lambda_handler",description="Lambda function used by Amazon Pinpoint to send Video messages via LINE",layers=[shared_lambda_layer],environment={
                                        "secret_arn": line_credentials.secret_arn,
                                        "secret_region": os.environ["CDK_DEFAULT_REGION"],
                                        "video_bucket": video_bucket.bucket_name
                                    })
        # Create receive event Lambda Function
        receive_event_lambda = _python.PythonFunction(self,"receive_event_lambda",entry="./assets/lambda_functions",runtime=_lambda.Runtime.PYTHON_3_9,index="receiveEvent.py",handler="lambda_handler",description="Lambda function used to receive user events from LINE",layers=[shared_lambda_layer],environment={
                                        "secret_arn": line_credentials.secret_arn,
                                        "secret_region": os.environ["CDK_DEFAULT_REGION"],
                                        "pinpoint_app_id":pinpoint_project.ref
                                    })
        # Grant receive event lambda access to Pinpoint to update endpoints
        receive_event_lambda.role.add_to_principal_policy(_iam.PolicyStatement(
            effect=_iam.Effect.ALLOW,
            resources=[pinpoint_project.attr_arn+"/endpoints/*"],
            actions=["mobiletargeting:UpdateEndpoint",
                     "mobiletargeting:UpdateEndpointsBatch",
                     "mobiletargeting:DeleteEndpoint"]
            ))
        # Grant Pinpoint Campaigns ability to invoke send Text/Image/Audio/Video lambda
        send_text_lambda.grant_invoke(_iam.ServicePrincipal(service="pinpoint.amazonaws.com",conditions={"ArnLike":{
          "aws:SourceArn": pinpoint_project.attr_arn+"/campaigns/*",
        }}))
        send_image_lambda.grant_invoke(_iam.ServicePrincipal(service="pinpoint.amazonaws.com",conditions={"ArnLike":{
          "aws:SourceArn": pinpoint_project.attr_arn+"/campaigns/*",
        }}))
        send_audio_lambda.grant_invoke(_iam.ServicePrincipal(service="pinpoint.amazonaws.com",conditions={"ArnLike":{
          "aws:SourceArn": pinpoint_project.attr_arn+"/campaigns/*",
        }}))
        send_video_lambda.grant_invoke(_iam.ServicePrincipal(service="pinpoint.amazonaws.com",conditions={"ArnLike":{
          "aws:SourceArn": pinpoint_project.attr_arn+"/campaigns/*",
        }}))
        # Grant Pinpoint Journeys ability to invoke send Text/Image/Audio/Video lambda
        send_text_lambda.grant_invoke(_iam.ServicePrincipal(service="pinpoint.amazonaws.com",conditions={"ArnLike":{
          "aws:SourceArn": pinpoint_project.attr_arn+"/journeys/*",
        }}))
        send_image_lambda.grant_invoke(_iam.ServicePrincipal(service="pinpoint.amazonaws.com",conditions={"ArnLike":{
          "aws:SourceArn": pinpoint_project.attr_arn+"/journeys/*",
        }}))
        send_audio_lambda.grant_invoke(_iam.ServicePrincipal(service="pinpoint.amazonaws.com",conditions={"ArnLike":{
          "aws:SourceArn": pinpoint_project.attr_arn+"/journeys/*",
        }}))
        send_video_lambda.grant_invoke(_iam.ServicePrincipal(service="pinpoint.amazonaws.com",conditions={"ArnLike":{
          "aws:SourceArn": pinpoint_project.attr_arn+"/journeys/*",
        }}))
        # Grant Lambdas access to corresponding S3 buckets
        image_bucket.grant_read(send_image_lambda)
        audio_bucket.grant_read(send_audio_lambda)
        video_bucket.grant_read(send_video_lambda)
        ## Grant Lambdas access to Secret
        line_credentials.grant_read(grantee=send_text_lambda)
        line_credentials.grant_read(grantee=send_image_lambda)
        line_credentials.grant_read(grantee=send_audio_lambda)
        line_credentials.grant_read(grantee=send_video_lambda)
        line_credentials.grant_read(grantee=receive_event_lambda)

        # Generate CloudFront APIGateway To Lambda Architecture
        CloudFrontToApiGatewayToLambda(self,"cloudfront-apigateway-lambda",existing_lambda_obj=receive_event_lambda,cloud_front_logging_bucket_props=_s3.BucketProps(server_access_logs_prefix='access-logs'))
        