import cfnresponse
import json
import os
import shutil
import pathlib
import urllib.request
from urllib.request import urlretrieve
import tarfile

def download_tar_gz(url, path):
    """""
    Function to downlaod dependencies in local path
    """
    filehandle = urllib.request.urlopen(url)
    tar = tarfile.open(fileobj=filehandle, mode="r|gz")
    tar.extractall(path)
    tar.close()
    print(f"File from {url} downloaded into {path}")

def download_file(url, filename):
    urlretrieve(url, filename)

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
        dirpath = "/tmp"
        
        
        ## AIT Core
        # Build directory AIT core directory
        print("Downloading AIT-Core")
        pathlib.Path("/mnt/efs/ait/AIT-Core/").mkdir(parents=True, exist_ok=True)
        # Download and place into AIT 
        ait_url = "https://github.com/NASA-AMMOS/AIT-Core/archive/refs/tags/2.3.5.tar.gz"
        download_tar_gz(ait_url, path=dirpath)
        shutil.copytree("/tmp/AIT-Core-2.3.5", "/mnt/efs/ait/AIT-Core", dirs_exist_ok=True)
        
        ## AIT GUI
        # Build directory AIT GUI directory
        print("Downloading AIT GUI")
        pathlib.Path("/mnt/efs/ait/AIT-GUI/").mkdir(parents=True, exist_ok=True)
        # Download and place into AIT 
        ait_url = "https://github.com/NASA-AMMOS/AIT-GUI/archive/refs/tags/2.3.1.tar.gz"
        download_tar_gz(ait_url, path=dirpath)
        shutil.copytree("/tmp/AIT-GUI-2.3.1", "/mnt/efs/ait/AIT-GUI", dirs_exist_ok=True)
        
        ## AIT DSN
        # Build directory AIT DSN directory
        print("Downloading AIT DSN Plugin")
        pathlib.Path("/mnt/efs/ait/AIT-DSN/").mkdir(parents=True, exist_ok=True)
        # Download and place into AIT 
        ait_url = "https://github.com/NASA-AMMOS/AIT-DSN/archive/refs/tags/2.0.0.tar.gz"
        download_tar_gz(ait_url, path=dirpath)
        shutil.copytree("/tmp/AIT-DSN-2.0.0", "/mnt/efs/ait/AIT-DSN", dirs_exist_ok=True)
        
        # Build necessary folders for the AIT DSN plugin
        pathlib.Path("/mnt/efs/ait/AIT-Core/ait/dsn/cfdp/datasink/outgoing").mkdir(parents=True, exist_ok=True)
        pathlib.Path("/mnt/efs/ait/AIT-Core/ait/dsn/cfdp/datasink/incoming").mkdir(parents=True, exist_ok=True)
        pathlib.Path("/mnt/efs/ait/AIT-Core/ait/dsn/cfdp/datasink/tempfiles").mkdir(parents=True, exist_ok=True)
        pathlib.Path("/mnt/efs/ait/AIT-Core/ait/dsn/cfdp/datasink/pdusink").mkdir(parents=True, exist_ok=True)
        
        # Download influx dB
        print("Downloading Influx DB RPM")
        download_file(url="https://repos.influxdata.com/rhel/6/amd64/stable/influxdb-1.2.4.x86_64.rpm", filename="/tmp/influxdb-1.2.4.x86_64.rpm")
        pathlib.Path("/mnt/efs/ait/setup").mkdir(parents=True, exist_ok=True)
        shutil.copyfile("/tmp/influxdb-1.2.4.x86_64.rpm", "/mnt/efs/ait/setup/influxdb-1.2.4.x86_64.rpm")
        

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