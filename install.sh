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
if [ -x "$(command -v apt-get)" ]; then
	apt-get update
	apt-get install -y build-essential python3-virtualenv python3-dev libsensors4-dev ipmitool
elif [ -x "$(command -v dnf)" ]; then
	dnf groupinstall -y "Development Tools"
	dnf install -y python3-virtualenv python3-devel lm_sensors-devel ipmitool
fi

echo "*** Creating folder '$TARGETDIR'..."
if [ ! -d "$TARGETDIR" ]; then
    mkdir -p "$TARGETDIR"
fi

echo "*** Creating and activating Python3 virtualenv..."
if [ -d "$TARGETDIR/venv" ]; then
    echo "*** Existing venv found, purging it."
    rm -r "$TARGETDIR/venv"
fi
virtualenv -p python3 "$TARGETDIR/venv"
source "$TARGETDIR/venv/bin/activate"

echo "*** Installing Python dependencies..."
pip3 install -r requirements.txt

echo "*** Deactivating Python3 virtualenv..."
deactivate

echo "*** Copying script and configuration in place..."
if [ -f "$TARGETDIR/fan_control.yaml" ]; then
    mv "$TARGETDIR/fan_control.yaml"{,.old}
fi
cp fan_control.yaml "$TARGETDIR/"
cp fan_control.py "$TARGETDIR/"

echo "*** Creating, (re)starting and enabling SystemD service..."
cp fan-control.service /etc/systemd/system/fan-control.service
sed -i "s#{TARGETDIR}#$TARGETDIR#g" /etc/systemd/system/fan-control.service
systemctl daemon-reload
systemctl restart fan-control
systemctl enable fan-control

echo "*** Waiting for the service to start..."
sleep 3

echo -e "*** All done! Check the service's output below:\n"
systemctl status fan-control

set +e
