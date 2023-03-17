# Line Pinpoint Integration Project

## Architecture

This solution uses [Amazon Pinpoint](https://aws.amazon.com/pinpoint/),[AWS Lambda](https://aws.amazon.com/lambda/), [Amazon API Gateway](https://aws.amazon.com/api-gateway/), [Amazon Simple Storage Service (Amazon S3)](https://aws.amazon.com/s3/), [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/) and [LINE Messaging API](https://developers.LINE.biz/en/docs/messaging-api/overview/)
![Alt text](images/Pasted%20image%2020230306180624.png)

The solution architecture can be broken up into two main sections:

- Steps 1-4 cover handling inbound user events and managing user data within Amazon Pinpoint.
- Steps 5-7 cover how to send outbound campaigns via Amazon Pinpoint Custom Channel.

1. The customer subscribes to the business' LINE channel.
2. The subscribe/unsubscribe event is received and checked via Amazon API Gateway.
3. The [edge-optimized](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-endpoint-types.html) Amazon API Gateway passes valid requests via a [proxy integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-set-up-simple-proxy.html) to the backend Lambda.
4. The backend Lambda compares the request body with the `x-LINE-signature` request header to confirm that the request was sent from the LINE Platform, as recommended by [LINE API document](https://developers.LINE.biz/en/reference/messaging-api/#signature-validation). Afterwards, the Lambda function processes the user events:
   1. If the user _subscribes_ to the channel, a new endpoint will be added to Amazon Pinpoint's user database.
   2. If the user _unsubscribes_ from the channel, the corresponding endpoint (identified by the LINE User ID) is deleted from Amazon Pinpoint's user database.
5. Amazon Pinpoint initiates a call to a Lambda function via [Custom Channel](https://docs.aws.amazon.com/pinpoint/latest/developerguide/channels-custom.html). Of particular importance would be the `Data` field, which can be specified within the Amazon Pinpoin console to modify the content of the message.
6. If the message contains image/audio/video files, the Lambda will request the file from the corresponding Amazon S3 buckets to be included in the payload for step 7.
7. The Lambda function puts the message in the correct format expected by the LINE Messaging API and sends it over to the LINE Platform.
8. The LINE Messaging API receives the request and processes the message content, finally sending the message to the corresponding user on the LINE Mobile App.

## Step-by-Step Deployment Guide

### Prerequisites

To deploy this solution, you must have the following:

1. An [AWS account](https://aws.amazon.com/premiumsupport/knowledge-center/create-and-activate-aws-account/), with the appropriate AWS CLI profile.
   - [Named Profile](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html): Run `aws configure` with the `--profile` option. The following steps assumed you have created a profile called `line-integration` to use with AWS CDK.
2. Minimum Python v3.7, with [`pip` and `venv`](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/)
3. [AWS CDK v2](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) installed.
4. Docker Engine installed. You can download and install the appropriate Docker Desktop Distribution for your system via this [link](https://docs.docker.com/engine/install/)
5. A LINE Account.
   - If you have never worked with LINE Messaging API before, you should login to to [LINE Developers Console](https://developers.LINE.biz/console/) using one of the following accounts.
     - LINE account
     - Business account
   - Afterwards, you should create a new **provider**.![Alt text](images/Pasted%20image%2020230306180319.png)
   - Within the provider page, you can then choose to create a new channel. For our Integration purposes, we will be choosing **Messaging API** channel type. ![Alt text](images/Pasted%20image%2020230306180427.png)

### Preparation

1. Fork this GitHub Repo into your account. This way you can experiment with changes as necessary to fit your workload.
2. In your local compute environment, clone the GitHub Repository and `cd` into the project directory.
3. Run the following commands to create a virtual environment, activate it and install required dependencies.

```bash
python3 -m venv env \
&& source env/bin/activate \
&& python -m pip install -r requirements.txt
```

### Deploy the CDK

4. We can set the AWS CLI profile in CDK commands by adding the `--profile` flag. Run the following commands to bootstrap your AWS environment, synthesize the CDK template and deploy to your environment.

```shell
cdk bootstrap --profile LINE-integration \
&& cdk synth --profile LINE-integration  \
&& cdk deploy --profile LINE-integration
```

5. After the deployment is done, the CDK template will output the API Gateway endpoint URL which takes the form of `https://[********].execute-api.[region].amazonaws.com/prod/`. Copy down this information as you will need it to set up the webhook connection later on.

### Getting LINE Official Account Credentials

6. Log in to [LINE developer console](https://account.LINE.biz/login).![Alt text](images/Pasted%20image%2020230306173912.png)
7. Once inside, choose the channel you'd like to have integrated with Amazon Pinpoint. This assumes that you've created a **provider** and a **channel** as mentioned in the **Prerequisite** section.
   ![Alt text](images/Pasted%20image%2020230306174012.png)
8. In the **Basic settings** tab, scroll down and note down the **Channel Secret**.
9. In the **Messaging API** tab, scroll down and click on **Edit** under Webhook URL and enter the **API Gateway endpoint URL** you have noted down in step 5. Click on **Update** to save the changes.

> **Note**
> Once you have finished entering your Channel Secret token in step 14, you can return to this page to **Verify** your webhook URL is set up correctly).

10. Finally, issue a **Channel Access Token** (at the bottom of the **Messaging API** tab) and note it down.

### Registering Secrets in AWS Secrets Manager

11. Navigate to the [AWS Secrets Manager](https://console.aws.amazon.com/secretsmanager) console. Make sure you're in the same region as your CDK deployment region.
12. Click on **Secrets** in the left side pane. You should find a secret with the name **LINE_secrets**
13. Click on **Retrieve Secret Value**
14. Then click on **Edit**:
    - Replace **YOUR_CHANNEL_SECRET** secret value with the channel secret you issued in step 10.
    - Replace **YOUR_CHANNEL_ACCESS_TOKEN** secret value with the access token you issued in step 10

## Marketing Operations Demonstration

Once you've successfully deployed the CDK and configured your secrets, you can immediately get started sending communications campaign to your customers.

LINE supports multimedia messaging formats, meaning that you can choose to send texts, images, audio and even video files to your customers as part of your campaigns. You just need to make sure that your customers have subscribed to your channel.

### Create a segment of subscribed users

The deployed solution has integrated user database management with Amazon Pinpoint so once users start subscribing to your LINE channel, they will be added as [**endpoints**](https://docs.aws.amazon.com/pinpoint/latest/apireference/apps-application-id-endpoints.html). To start filtering out _who_ we should send to, you can create [**segments**](https://docs.aws.amazon.com/pinpoint/latest/apireference/apps-application-id-segments-segment-id.html) of your subscribers.

1.  Navigate to the [Amazon Pinpoint console](http://console.aws.amazon.com/pinpoint/).
2.  On the **All projects** page, a project named **Line-Pinpoint-Project** has been created for you.
3.  On the left-side pane, choose **Segments** and then **Create a segment**
4.  Give your segment a descriptive name and add the appropriate criteria to filter down to your target audience (E.g.: filter down to customers who have **Custom** channel type)
5.  Confirm the number of endpoints that you will be sending in the **Segment estimate** section matches your expectations and then choose **Create segment**.

### Upload media files for campaign

If you'd like to use your own image, audio and video files for the campaign, follow along with this section. Otherwise, proceed to the [**Create Campaigns**](#Create-campaigns) section (step 9).

> **Note**
> Depending on the media type, there are restrictions imposed such as maximum file size and file format extensions. You can find more information [here](https://developers.LINE.biz/en/reference/messaging-api/).

6. Navigate to the [Amazon S3](http://console.aws.amazon.com/s3/) console.
7. Here you will find a list of buckets which corresponds to the type of media files you want to upload:
   - `part-1-stack-images3bucket...`: contains image files.
   - `part-1-stack-audios3bucket...`: contains audio files.
   - `part-1-stack-videos3bucket...`: contains **both** video and image cover files.
8. Upload the corresponding files that you want to use for your campaign by choosing **Upload**.

### Create campaigns

9. In the navigation pane, choose **Campaigns**, and then choose **Create a campaign**.
10. Give your campaign a descriptive name. Under **Campaign Type** choose **Standard campaign** and under **Channel**, choose **Custom**. Click **Next** to confirm.
11. On the **Choose a segment** page, choose the segment that you created in step 5, and then choose **Next**.
12. In **Create your message**, depending on the type of message that you want to send, choose the corresponding Lambda function. Your function should be named `part-1-stack-send[text/image/audio/video]lambda...`
13. In the custom data section, you can choose to leave it blank, which will trigger the campaign to send the sample message.
14. Otherwise, depending on the type of message, you can customize your campaigns to send the content that you want by inputting the following values into **Custom Data**.
    - **Text Campaign:** Enter the Text Message that you want to send.
    - **Image Campaign:** Enter the name of the image file you've uploaded in step 8 _including the extension name_ (E.g.: sample_image.png)
    - **Audio Campaign**: Enter the name of the audio file you've uploaded in step 8 _including the extension name_ and the duration of the audio file in _milliseconds_ separated by a comma (E.g.: sample_audio.mp3,5000)
    - **Video Campaign**: Enter the name of the video file you've uploaded in step 8 _including the extension name_ and the name of the image file you've uploaded in step 8 _including the extension name_, separated by a comma (E.g.: sample_video.mp4,sample_image.png)
15. Choose **Next** and configure when to send the campaign depending on your needs. Once done, choose **Next** again.
16. On the **Review and launch** page, verify all your information is correct and then click on **Launch campaign**.

## Cleanup

To delete the sample application that you created, use the **AWS CDK**.

```shell
cdk destroy
```

You’ll be asked:

```shell
Are you sure you want to delete: part-1-stack (y/n)?
```

Hit “y” and you’ll see your stack being destroyed.
