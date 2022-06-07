import os
import shutil
import subprocess
import pathlib
import urllib.request
import zipfile
import tarfile
from crhelper import CfnResource

helper = CfnResource()

@helper.create
@helper.update
def clone_deployment(event, _):
    if os.listdir("/tmp"):
        folder = '/tmp'
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))

    url = 'https://github.com/NASA-AMMOS/AIT-Core/archive/refs/tags/2.3.5.tar.gz'
    filehandle = urllib.request.urlopen(url)
    tar = tarfile.open(fileobj=filehandle, mode="r|gz")
    tar.extractall("/tmp")
    tar.close()

    pathlib.Path("/mnt/efs/ait").mkdir(parents=True, exist_ok=True)

    shutil.copytree("/tmp/ait", "/mnt/efs/ait", dirs_exist_ok=True)

    helper.Data['message'] = str(os.listdir("/mnt/efs/"))
@helper.delete
def no_op(_, __):
    pass

def handler(event, context):
    helper(event, context)