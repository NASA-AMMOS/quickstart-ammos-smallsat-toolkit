#!/bin/bash
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
function exitTrap(){
exitCode=$?
/opt/aws/bin/cfn-signal \
--stack ${AWS::StackName} \
--resource AitAutoScalingGroup \
--region ${AWS::Region} -e $exitCode || echo 'Failed to send Cloudformation Signal'
}
trap exitTrap EXIT
CONFIG_BUCKET_NAME=${ConfigBucketName}

function boostrap_aws_stuff(){
# rpms and stuff
yum install -y -q python3 wget unzip
wget -nv https://s3.amazonaws.com/cloudformation-examples/aws-cfn-bootstrap-py3-latest.tar.gz
wget -nv https://s3.amazonaws.com/amazoncloudwatch-agent/redhat/amd64/latest/amazon-cloudwatch-agent.rpm
curl  "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip " -o  "awscliv2.zip"
pip3 install aws-cfn-bootstrap-py3-latest.tar.gz

# directories
mkdir -p /opt/aws/bin
ln -s /usr/local/bin/cfn-* /opt/aws/bin

# Cloudwatch and SSM agent
sudo rpm -U ./amazon-cloudwatch-agent.rpm
yum install -y -q https://s3.amazonaws.com/ec2-downloads-windows/SSMAgent/latest/linux_amd64/amazon-ssm-agent.rpm

# AWS CLI
unzip -qq awscliv2.zip
./aws/install > /dev/null && echo "Installed AWS CLI"
}

function bootstrap_ait(){
# Install basic system tools needed for AIT Server
# install python 3.7
yum install -y -q @development gcc openssl-devel bzip2-devel libffi-devel sqlite-devel httpd mod_ssl vim policycoreutils-python-utils
cd /opt
wget -nv https://www.python.org/ftp/python/3.7.9/Python-3.7.9.tgz
tar xzf Python-3.7.9.tgz
cd Python-3.7.9
./configure --enable-optimizations --enable-loadable-sqlite-extensions > /dev/null && echo "Configured Python 3.7"
make altinstall > /dev/null && echo "Installed Python 3.7"

systemctl enable httpd
curl -SL https://github.com/stedolan/jq/relepermanently/deleteases/download/jq-1.5/jq-linux64  -o /usr/bin/jq
chmod +x /usr/bin/jq
}

function bootstrap_data(){
# Adding functionality to mount an EFS
echo "Bootstrapping EFS and Mounting it"
sudo yum -y update  
sudo yum -y install nfs-utils

# Installing EFS Amazon Utilss
echo "Downloading and installing Amazon EFS Utils"
sudo yum -y install git rpm-build make
sudo git clone https://github.com/aws/efs-utils
cd efs-utils
sudo make rpm
sudo yum -y install build/amazon-efs-utils*rpm
# cd back to root dir
cd /

# Install botocore libraries
pip3 install botocore
# Define mount location and efs id
DIR_TGT=/mnt/efs/
EC2_REGION=${AWS::Region}
EFS_FILE_SYSTEM_ID=${FileSystem}
echo "Mounting directory to EFS: $EFS_FILE_SYSTEM_ID"
mkdir -p $DIR_TGT
echo "Mounting $EFS_FILE_SYSTEM_ID to $DIR_TGT"
sudo mount -t efs  $EFS_FILE_SYSTEM_ID $DIR_TGT
}

function install_ait_and_dependents(){
# Set variables for system install
PROJECT_HOME=/mnt/efs/ait
SETUP_DIR=/mnt/efs/ait/setup
USER=ec2-user
GROUP=ec2-user
AWS_REGION=${AWS::Region}
python3.7 -m pip install virtualenv virtualenvwrapper
cd $PROJECT_HOME

# Prepare python environment for AIT work
tee -a /root/.bashrc $PROJECT_HOME/.bashrc << EOM
export VIRTUALENVWRAPPER_PYTHON=/usr/local/bin/python3.7
export WORKON_HOME=$PROJECT_HOME/.virtualenvs
export PROJECT_HOME=$PROJECT_HOME
export CONFIG_BUCKET_NAME=$CONFIG_BUCKET_NAME
source /usr/local/bin/virtualenvwrapper.sh
EOM
source /root/.bashrc


tee -a > $PROJECT_HOME/.virtualenvs/postactivate << EOM
if [ \$VIRTUAL_ENV ==  "$PROJECT_HOME/.virtualenvs/ait" ]; then
export AIT_ROOT=$PROJECT_HOME/AIT-Core
export AIT_CONFIG=$PROJECT_HOME/AIT-Core/config/config.yaml
fi
EOM

mkvirtualenv ait
workon ait

# Pull assets, config, and secrets from s3/sm (NEEDS TO MOVE)
mkdir -p $SETUP_DIR
/usr/local/aws-cli/v2/current/bin/aws --region $AWS_REGION s3 sync s3://$CONFIG_BUCKET_NAME/configs/ait/ $SETUP_DIR/
/usr/local/aws-cli/v2/current/bin/aws --region $AWS_REGION s3 cp s3://"$CONFIG_BUCKET_NAME"/configs/modules/openmct-static.tgz - | tar -xz -C /var/www/html

# Install open-source AIT components
cd $PROJECT_HOME/AIT-Core/
git checkout 2.3.5
pip install .
/usr/bin/cp -r $SETUP_DIR/config $PROJECT_HOME/AIT-Core

cd $PROJECT_HOME/AIT-GUI/
git checkout 2.3.1
pip install .

cd $PROJECT_HOME/AIT-DSN
git checkout 2.0.0
pip install .

cd $PROJECT_HOME

# Copy necessary apache configs
cp $SETUP_DIR/httpd_proxy.conf /etc/httpd/conf.d/proxy.conf

# Inject FQDN from Cloudformation for proper virtual host configuration
mv /etc/httpd/conf.d/proxy.conf{,.bak}
sed 's/<CFN_FQDN>/${FQDN}/g' /etc/httpd/conf.d/proxy.conf.bak > /etc/httpd/conf.d/proxy.conf
rm /etc/httpd/conf.d/proxy.conf.bak

# Inject FQDN from Cloudformation into OpenMCT file
mv /var/www/html/openmct/index.html{,.bak}
sed 's/<CFN_FQDN>/${FQDN}/g' /var/www/html/openmct/index.html.bak > /var/www/html/openmct/index.html
rm /var/www/html/openmct/index.html.bak

# Install InfluxDB and data plugin
yum localinstall -y $SETUP_DIR/influxdb-1.2.4.x86_64.rpm

pip install influxdb
systemctl enable influxdb
service influxdb start

# Start AIT Server
tee > /etc/systemd/system/ait-server.service << EOM
[Unit]
Description=AIT-Core Server
#After=influxdb.service

[Service]
Type=simple
User=root
Environment=AIT_ROOT=$PROJECT_HOME/AIT-Core
Environment=AIT_CONFIG=$PROJECT_HOME/AIT-Core/config/config.yaml
ExecStart=/home/ec2-user/.virtualenvs/ait/bin/ait-server

[Install]
WantedBy=multi-user.target
EOM
systemctl enable ait-server.service

# https://serverfault.com/questions/1006417/selinux-blocking-execution-in-systemd-unit
semanage fcontext -a -t bin_t '/home/ec2-user/.virtualenvs/ait/bin.*'
chcon -Rv -u system_u -t bin_t '/home/ec2-user/.virtualenvs/ait/bin'
restorecon -R -v /home/ec2-user/.virtualenvs/ait/bin

systemctl start ait-server.service

# change SELinux file context so that apache can read specific files (e.g certs)
# semanage fcontext -a -t httpd_sys_content_t "/ammos(/.*)?"

# allow apache to make outbound connections
# (for proxying requests to AIT server)
setsebool -P httpd_can_network_connect 1

systemctl start httpd

# Configure and start the CloudWatch Agent
mv $SETUP_DIR/cloudwatch-agent-ait.json /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

# Give user ownership of all the things placed in project home during this setup script
chown -R $USER $PROJECT_HOME
chgrp -R $GROUP $PROJECT_HOME

deactivate
}

boostrap_aws_stuff
bootstrap_data
bootstrap_ait
install_ait_and_dependents
