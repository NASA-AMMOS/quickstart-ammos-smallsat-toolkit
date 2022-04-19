from operator import length_hint
import cfnresponse
import boto3
import botocore
import json
import random
import string
import secrets
import logger

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def rand_seq(seq, at_least: int, at_most: int) -> list:
    n = secrets.choice(range(at_least, at_most + 1))
    return [secrets.choice(seq) for _ in range(n)]

def lambda_handler(event, context):
    """Lambda Handler for dealing with creating a new cognito user using AWS Cognito

    Args:
        event (dict): Event dictionary from custom resource
        context (obj): Context manager
    """

    user_pool_id = event['ResourceProperties']['UserPoolId']
    username = 'admin'
    
    # Generate random word using secrets for 20 characters long
    length = 20
    password = []
    password += rand_seq(string.punctuation, 1, 3)
    password += rand_seq(string.digits, 1, 3)
    password += rand_seq(string.ascii_uppercase, 3, 9)
    n = length - len(password)
    password += rand_seq(string.ascii_lowercase, n, n)
    password = "".join(password)
    

    if event['RequestType'] in ['Create', 'Delete', 'Update']:      
        # Run in the cloud to make cognito user
        client = boto3.client('cognito-idp') 

        try:
            cidp_response = client.admin_create_user(
                UserPoolId = user_pool_id,
                Username = username,
                TemporaryPassword = password
            )

            responseData = {}
            responseData["Username"] = username
            responseData['TemporaryPassword'] = password

            # Send response back with CIDP Response to CFN
            cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData)

        except botocore.exceptions.ClientError as e:
            logger.error("Error: {}".format(e))
            cfn_response = {}
            cfnresponse.send(event, context, cfnresponse.FAILED, cfn_response)
    else:
        responseData = {"message": "Invalid Request Type"}
        cfnresponse.send(event, context, cfnresponse.FAILED, )