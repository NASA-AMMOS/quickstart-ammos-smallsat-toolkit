import cfnresponse
import boto3
import json
import random
import string


def lambda_handler(event, context):
    """Lambda Handler for dealing with creating a new cognito user using AWS Cognito

    Args:
        event (dict): Event dictionary from custom resource
        context (obj): Context manager
    """
    try:
        user_pool_id = event['ResourceProperties']['UserPoolId']
        username = 'admin'
       
        # Generate random word using secrets for 20 characters long
        length = 20
        lower = string.ascii_lowercase
        upper = string.ascii_uppercase
        num = string.digits
        symbols = string.punctuation
        all = lower + upper + num + symbols
def rand_seq(seq, at_least: int, at_most: int) -> list:
    n = secrets.choice(range(at_least, at_most + 1))
    return [secrets.choice(seq) for _ in range(n)]

pw = []
pw += rand_seq(string.punctuation, 1, 3)
pw += rand_seq(string.digits, 1, 3)
pw += rand_seq(string.ascii_uppercase, 3, 9)
n = length - len(pw)
pw += rand_seq(string.ascii_lowercase, n, n)
pw = "".join(pw)
        password = "".join(temp)
        

        if event['RequestType'] in ['Create', 'Delete', 'Update']:      
            # Run in the cloud to make cognito user
            client = boto3.client('cognito-idp') 
            cidp_response = client.admin_create_user(
                UserPoolId = user_pool_id,
                Username = username,
                TemporaryPassword = password
            )

            cfn_response_from_cidp = json.dumps(cidp_response, indent=4, sort_keys=True, default=str)
            cfn_response_from_cidp = json.loads(cfn_response_from_cidp)
            cfn_response_from_cidp['TemporaryPassword'] = password

            # Send response back with CIDP Response to CFN
            cfnresponse.send(event, context, cfnresponse.SUCCESS, cfn_response_from_cidp)

    except Exception as err:
        print("Lambda execution failed to create AWS Cognito user")
        print(err)
        cfnresponse.send(event, context, cfnresponse.FAILED, {'responseValue': 400})