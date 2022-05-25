import cfnresponse
import json

def handler(event, context):
    """Lambda Handler for dealing with creating a new cognito user using AWS Cognito

    Args:
        event (dict): Event dictionary from custom resource
        context (obj): Context manager
    """

    print(json.dumps(event, default=str))

    responseData = {}
    status = cfnresponse.FAILED
    if event["RequestType"] == "Create":
        responseData["LambaTest"] = "Create"
        status = cfnresponse.SUCCESS
    elif event["RequestType"] in ["Delete", "Update"]:
        # No action needs to be taken for delete or update events
        status = cfnresponse.SUCCESS
        responseData["LambaTest"] = "Not Create"
    else:
        responseData = {"Message": "Invalid Request Type"}

    cfnresponse.send(event, context, status, responseData)