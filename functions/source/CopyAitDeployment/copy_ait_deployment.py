import cfnresponse
import json
import os
import shutil
import pathlib
from urllib.request import urlopen
import tarfile
import boto3
import logging

# Setup basic configuration for logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Initite S3 Resource
s3_resource = boto3.resource("s3")

def download_tar_gz(url, path):
    """ ""
    Function to downlaod dependencies in local path
    """
    filehandle = urlopen(url)
    tar = tarfile.open(fileobj=filehandle, mode="r|gz")
    tar.extractall(path)
    tar.close()
    logger.info("File from %s downloaded from %s", url, path)

def download_directory_from_s3(bucket_name, remote_path, dir_path):
    """Function to download a directory from s3"""
    bucket = s3_resource.Bucket(bucket_name)
    # Download each of the files
    for obj in bucket.objects.filter(Prefix=remote_path):
        # Check if the path already exists locally on the lambda file system
        if not os.path.exists(os.path.dirname(obj.key)):
            logger.info(f"Creating directory {os.path.dirname(obj.key)}")
            pathlib.Path(os.path.dirname(obj.key)).mkdir(parents=True, exist_ok=True)
            # Check if the files exist on the EFS system
            efs_path = "/mnt/efs/" + os.path.dirname(obj.key)
            if not os.path.exists(efs_path):
                dir_path = dir_path + str(obj.key)
                bucket.download_file(obj.key, obj.key, dir_path)

def handler(event, context):
    """Lambda Handler for dealing with bootstrapping EFS and downloading dependencies for running the AIT server

    Args:
        event (dict): Event dictionary from custom resource
        context (obj): Context manager
    """

    print(json.dumps(event, default=str, indent=2))
    responseData = {}
    status = cfnresponse.FAILED
    dir_path = "/tmp"

    if event["RequestType"] == "Create":
        responseData["RequestType"] = "Create"
        BUCKET_NAME = event["ResourceProperties"]["BucketName"]
        ## AIT Core
        # Build directory AIT core directory
        logging.info("Downloading AIT-Core")
        pathlib.Path("/mnt/efs/ait/AIT-Core/").mkdir(parents=True, exist_ok=True)
        # Download and place into AIT
        ait_url = (
            "https://github.com/NASA-AMMOS/AIT-Core/archive/refs/tags/2.3.5.tar.gz"
        )
        download_tar_gz(ait_url, path=dir_path)
        shutil.copytree(
            "/tmp/AIT-Core-2.3.5", "/mnt/efs/ait/AIT-Core", dirs_exist_ok=True
        )

        ## AIT GUI
        # Build directory AIT GUI directory
        logging.info("Downloading AIT GUI")
        pathlib.Path("/mnt/efs/ait/AIT-GUI/").mkdir(parents=True, exist_ok=True)
        # Download and place into AIT
        ait_url = "https://github.com/NASA-AMMOS/AIT-GUI/archive/refs/tags/2.3.1.tar.gz"
        download_tar_gz(ait_url, path=dir_path)
        shutil.copytree(
            "/tmp/AIT-GUI-2.3.1", "/mnt/efs/ait/AIT-GUI", dirs_exist_ok=True
        )

        ## AIT DSN
        # Build directory AIT DSN directory
        logging.info("Downloading AIT DSN Plugin")
        pathlib.Path("/mnt/efs/ait/AIT-DSN/").mkdir(parents=True, exist_ok=True)
        # Download and place into AIT
        ait_url = "https://github.com/NASA-AMMOS/AIT-DSN/archive/refs/tags/2.0.0.tar.gz"
        download_tar_gz(ait_url, path=dir_path)
        shutil.copytree(
            "/tmp/AIT-DSN-2.0.0", "/mnt/efs/ait/AIT-DSN", dirs_exist_ok=True
        )

        # Build necessary folders for the AIT DSN plugin
        datasink_dir = pathlib.Path("/mnt/efs/ait/AIT-Core/ait/dsn/cfdp/datasink/outgoing")
        for dir in ["outgoing", "incoming", "tempfiles", "pdusink"]:
           (datasink_dir / dir).mkdir(parents=True, exist_ok=True)

        ## Configuration files from S3
        logging.info("Downloading Configuration files")
        s3 = boto3.client("s3")
        bucket = s3.list_objects(Bucket=BUCKET_NAME)
        for content in bucket["Contents"]:
            key = content["Key"]
            filename = f"/tmp/{key}"
            path, _ = os.path.split(filename)
            # Make directories
            pathlib.Path(path).mkdir(parents=True, exist_ok=True)
            print(f"Downloading {key} into {filename}")

            # Download file into relavent paths
            s3.download_file(BUCKET_NAME, key, filename)

        # Copy configuration files into mounted EFS
        shutil.copytree(
            "/tmp/configs/ait", "/mnt/efs/ait/setup/configs", dirs_exist_ok=True
        )

        # Extract and open OpenMCT Application 
        tar = tarfile.open("/tmp/configs/modules/openmct-static.tgz", mode="r|gz")
        tar.extractall(path="/mnt/efs/ait")
        tar.close()

        logging.info("All downloads completed...")
        status = cfnresponse.SUCCESS

    elif event["RequestType"] in ["Delete", "Update"]:
        # No action needs to be taken for delete or update events
        status = cfnresponse.SUCCESS
        responseData["LambaTest"] = "Not Create"
    else:
        responseData = {"Message": "Invalid Request Type"}

    path = "/mnt/efs/ait/"
    logging.info(f"Listing directories in place {path}")
    
    # Send response back to CFN
    cfnresponse.send(event, context, status, responseData)
