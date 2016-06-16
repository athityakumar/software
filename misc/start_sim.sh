#!/bin/sh

if [ -z ${CUAUV_SOFTWARE} ]; then
  echo "Please set CUAUV_SOFTWARE to the root of the repo," \
       "with a trailing slash."
  exit 1
fi

auv-sim-defaults

auv-fishbowl &
fishbowl_pid=$!

auv-controld3 &
control_pid=$!

auv-navigated &
nav_pid=$!

# Wait for fishbowl to come online and accept the unpause command.
sleep 1

# Unpause the simulator.
auv-fishbowl-unpause

auv-terminal auv-control-helm -e &
# TODO gnome-terminal can't be killed because of how it spawns.
# See misc/auv_terminal.sh
helm_pid=$!

# Enable the controller.
auv-shm-cli settings_control enabled 1

auv-visualizer

# The visualizer has been closed; clean up everything.
kill $fishbowl_pid $control_pid $helm_pid $nav_pid
