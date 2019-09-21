#!/bin/bash

set -e

if [[ "$(whoami)" != "root" ]]; then
    echo "You need to run this script as root."
    exit 1
fi

TARGETDIR="/opt/fan_control"
if [ ! -z "$1" ]; then
    TARGETDIR="$1"
fi

echo "*** Installing packaged dependencies..."
apt-get update
apt-get install -y python-virtualenv python3-virtualenv python3-dev libsensors4-dev ipmitool

echo "*** Creating folder '$TARGETDIR'..."
mkdir -p "$TARGETDIR"

echo "*** Creating and activating Python3 virtualenv..."
virtualenv -p python3 "$TARGETDIR/venv"
source "$TARGETDIR/venv/bin/activate"

echo "*** Installing Python dependencies..."
pip3 install -r requirements.txt

echo "*** Deactivating Python3 virtualenv..."
deactivate

echo "*** Copying script and configuration in place..."
cp fan_control.conf "$TARGETDIR/"
cp fan_control.py "$TARGETDIR/"

echo "*** Creating, enabling and starting SystemD service..."
cp fan-control.service /etc/systemd/system/fan-control.service
sed -i "s#{TARGETDIR}#$TARGETDIR#g" /etc/systemd/system/fan-control.service
systemctl daemon-reload
systemctl enable fan-control
systemctl start fan-control

echo "*** Waiting for the service to start..."
sleep 3

echo -e "*** All done! Check the service's output below:\n"
systemctl status fan-control

set +e
