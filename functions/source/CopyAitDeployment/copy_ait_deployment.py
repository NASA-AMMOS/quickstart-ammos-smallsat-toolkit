import json
import logging
import os
import shutil
import tarfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.request import urlopen

import boto3

from crhelper import CfnResource

# Setup basic configuration for logging
logger = logging.getLogger(__name__)
LOGLEVEL = os.getenv("LOGLEVEL", logging.DEBUG)
logger.setLevel(LOGLEVEL)
helper = CfnResource(json_logging=False, log_level=LOGLEVEL, boto_level='CRITICAL', sleep_on_delete=120)

try:
    # Initialize S3 Resource
    s3_resource = boto3.resource("s3")
except Exception as e:
    helper.init_failure(e)

# Define standard file locations
class LOCAL:
    tmp = Path("/tmp")
    tmp_config = tmp / "configs"
    modules = tmp_config / "modules"


class EFS:
    ait = Path("/mnt/efs/ait")
    ait_core = ait / "AIT-CORE"
    ait_gui = ait / "AIT-GUI"
    ait_dsn = ait / "AIT-DSN/"
    setup = ait / "setup"


# Define Software resources (github url and version)
@dataclass
class Software:
    name: str
    version: str
    repo: str
    archive_url: str

    def __post_init__(self):
        self.repo = f"https://github.com/NASA-AMMOS/{self.name}"
        self.archive_url = f"{self.repo}/archive/refs/tags/{self.version}.tar.gz"


# TODO: Get Software version from event properties to download specified version
AIT = Software("AIT-Core", "2.3.5")
AIT_GUI = Software("AIT-GUI", "2.3.1")
AIT_DSN = Software("AIT-DSN", "2.0.0")


def download_tar_gz(url: str, path: os.PathLike):
    """Download and extract a .tar.gz artifact to a local path

    :param url: url to download the artifact
    :param path: local path for extracting the artifact
    """
    file_handle = urlopen(url)
    with tarfile.open(fileobj=file_handle, mode="r|gz") as tar:
        tar.extractall(path)
    logger.info("File from %s downloaded from %s", url, path)


def download_software(software: Software, location: Path):
    """Download a software artifact as a tgz and extract to EFS

    :param software: The Software to be downloaded
    :param location: The location on EFS to extract the downloaded Software
    """
    logger.info(f"Downloading {software.name}")
    # Download to local temp storage
    download_tar_gz(software.archive_url, path=LOCAL.tmp)
    # Place on EFS in desired location
    location.mkdir(parents=True, exist_ok=True)
    shutil.copytree(LOCAL.tmp / f"{software.name}-{software.version}", location, dirs_exist_ok=True)


def download_directory_from_s3(bucket_name, remote_path, dir_path):
    """Function to download a directory from s3"""
    bucket = s3_resource.Bucket(bucket_name)
    # Download each of the files
    for obj in bucket.objects.filter(Prefix=remote_path):
        # Check if the path already exists locally on the lambda file system
        path = Path(obj.key)
        if not path.parent.exists():
            logger.info(f"Creating directory {os.path.dirname(obj.key)}")
            Path(os.path.dirname(obj.key)).mkdir(parents=True, exist_ok=True)
            # Check if the files exist on the EFS system
            efs_path = "/mnt/efs/" + os.path.dirname(obj.key)
            if not os.path.exists(efs_path):
                dir_path = dir_path + str(obj.key)
                bucket.download_file(obj.key, obj.key, dir_path)


@helper.create
def bootstrap(event, context):
    """Lambda Handler for dealing with bootstrapping EFS and downloading dependencies for running the AIT server

    Args:
        event (dict): Event dictionary from custom resource
        context (obj): Context manager
    """
    logger.info("Create")
    logger.debug(json.dumps(event, default=str, indent=2))
    responseData = {}

    responseData["RequestType"] = "Create"
    BUCKET_NAME = event["ResourceProperties"]["BucketName"]

    ## Download Software artifacts
    download_software(AIT, EFS.ait_core)
    download_software(AIT_GUI, EFS.ait_gui)
    download_software(AIT_DSN, EFS.ait_dsn)

    # Build necessary folders for the AIT DSN plugin
    datasink_dir = EFS.ait_core / "ait/dsn/cfdp/datasink"
    for dir in ["outgoing", "incoming", "tempfiles", "pdusink"]:
        (datasink_dir / dir).mkdir(parents=True, exist_ok=True)

    ## Configuration files from S3
    logger.info("Downloading Configuration files")
    # TODO: use s3 downloader function from above?
    s3 = boto3.client("s3")
    bucket = s3.list_objects(Bucket=BUCKET_NAME)
    for content in bucket["Contents"]:
        key = content["Key"]
        location: Path = LOCAL.tmp_config / key
        # Make directories
        location.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Downloading {key} into {location}")

        # Download file into relevant paths
        s3.download_file(BUCKET_NAME, key, location)

    # Copy configuration files into mounted EFS
    shutil.copytree(LOCAL.tmp_config / "ait", EFS.setup / "configs", dirs_exist_ok=True)

    # Copy AIT configuration files into AIT-Core directory
    shutil.copytree(
        LOCAL.tmp_config / "ait" / "config", EFS.ait_core / "config", dirs_exist_ok=True
    )

    # Extract and open OpenMCT Application
    with tarfile.open(LOCAL.modules / "openmct-static.tgz", mode="r|gz") as openmct_tar:
        openmct_tar.extractall(path=EFS.ait)

    logger.info("All downloads completed...")

    path = Path("/mnt/efs/ait/")
    logger.info("Listing directories in: %s", str(path.absolute()))
    logger.info("\n\t" + "\n\t".join(path.glob("*")))

    helper.Data.update(responseData)