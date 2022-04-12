import cfnresponse
import boto3
import json
import random
import string

from datetime import datetime


def lambda_handler(event, context):
    """Lambda Handler for dealing with creating a new cognito user using AWS Cognito

    Args:
        event (dict): Event dictionary from custom resource
        context (obj): Context manager
    """
    try:
        userId = event['ResourceProperties']['UserPoolId']
        username = 'admin'
       
        # Generate random word using secrets for 20 characters long
        length = 20
        lower = string.ascii_lowercase
        upper = string.ascii_uppercase
        num = string.digits
        symbols = string.punctuation
        all = lower + upper + num + symbols
        temp = random.sample(all,length)
        password = "".join(temp)
        

        if event['RequestType'] in ['Create', 'Delete', 'Update']:      
            # Run in the cloud to make cognito user
            client = boto3.client('cognito-idp') 
            cidp_response = client.admin_create_user(
                UserPoolId = userId,
                Username = username,
                TemporaryPassword = password
            )

            cfn_response_from_cidp = json.dumps(cidp_response, indent=4, sort_keys=True, default=str)
            cfn_response_from_cidp = json.loads(cfn_response_from_cidp)

            # Send response back with CIDP Response to CFN
            cfnresponse.send(event, context, cfnresponse.SUCCESS, cfn_response_from_cidp)

    except Exception as err:
        print("Lambda execution failed to create AWS Cognito user")
        print(err)
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {'responseValue': 400})