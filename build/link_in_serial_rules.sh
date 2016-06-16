#!/bin/bash

ln -s `pwd`/50-novaserial.rules /etc/udev/rules.d/50-novaserial.rules
ln -s `pwd`/50-tritonserial.rules /etc/udev/rules.d/50-tritonserial.rules
