#!/bin/bash

which python
cd /home/rpi4/sort2sip
pwd

git pull

activate() {
    . /home/rpi4/sort2sip/.venv/bin/activate
}

activate
which python
python /home/rpi4/sort2sip/sort2sip.py
