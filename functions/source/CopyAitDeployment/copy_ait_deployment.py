import cfnresponse
import json
import os
import shutil
import pathlib
import urllib.request
from urllib.request import urlretrieve
import tarfile
import boto3


def download_tar_gz(url, path):
    """ ""
    Function to downlaod dependencies in local path
    """
    filehandle = urllib.request.urlopen(url)
    tar = tarfile.open(fileobj=filehandle, mode="r|gz")
    tar.extractall(path)
    tar.close()
    print(f"File from {url} downloaded into {path}")


def download_file(url, filename):
    urlretrieve(url, filename)


def download_directory_from_s3(bucket_name, remote_path, dir_path):
    """Funciton to downlaod a directory from s3"""
    s3_resource = boto3.resource("s3")
    bucket = s3_resource.Bucket(bucket_name)

    # Download each of the files
    for obj in bucket.objects.filter(Prefix=remote_path):
        if not os.path.exists(os.path.dirname(obj.key)):
            os.makedirs(os.path.dirname(obj.key))
        dir_path = dir_path + str(obj.key)
        bucket.download_file(obj.key, obj.key, dir_path)


def handler(event, context):
    """Lambda Handler for dealing with creating a new cognito user using AWS Cognito

    Args:
        event (dict): Event dictionary from custom resource
        context (obj): Context manager
    """

    print(json.dumps(event, default=str))
    responseData = {}
    status = cfnresponse.FAILED
    dir_path = "/tmp"
    BUCKET_NAME = os.getenv("ConfigBucketName")

    if event["RequestType"] == "Create":
        responseData["LambaTest"] = "Create"
        status = cfnresponse.SUCCESS

        ## AIT Core
        # Build directory AIT core directory
        print("Downloading AIT-Core")
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
        print("Downloading AIT GUI")
        pathlib.Path("/mnt/efs/ait/AIT-GUI/").mkdir(parents=True, exist_ok=True)
        # Download and place into AIT
        ait_url = "https://github.com/NASA-AMMOS/AIT-GUI/archive/refs/tags/2.3.1.tar.gz"
        download_tar_gz(ait_url, path=dir_path)
        shutil.copytree(
            "/tmp/AIT-GUI-2.3.1", "/mnt/efs/ait/AIT-GUI", dirs_exist_ok=True
        )

        ## AIT DSN
        # Build directory AIT DSN directory
        print("Downloading AIT DSN Plugin")
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

        # Download influx dB
        print("Downloading Influx DB RPM")
        download_file(
            url="https://repos.influxdata.com/rhel/6/amd64/stable/influxdb-1.2.4.x86_64.rpm",
            filename="/tmp/influxdb-1.2.4.x86_64.rpm",
        )
        pathlib.Path("/mnt/efs/ait/setup").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(
            "/tmp/influxdb-1.2.4.x86_64.rpm",
            "/mnt/efs/ait/setup/influxdb-1.2.4.x86_64.rpm",
        )

        ## Configuration files from S3
        print("Downloading CONFIG files")
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
            "/tmp/configs", "/mnt/efs/ait/setup/configs", dirs_exist_ok=True
        )

        print("All downloads completed...")

    elif event["RequestType"] in ["Delete", "Update"]:
        # No action needs to be taken for delete or update events
        status = cfnresponse.SUCCESS
        responseData["LambaTest"] = "Not Create"
    else:
        responseData = {"Message": "Invalid Request Type"}

    path = "/mnt/efs/ait/"
    print(f"Listing directories in place {path}")
    print(os.listdir(path))
    # Send response back to CFN
    cfnresponse.send(event, context, status, responseData)
