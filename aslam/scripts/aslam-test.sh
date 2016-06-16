#!/bin/sh

LOCALE=$1
TESTFILE=$2

auv-shm RESET --hard

if [ -z $LOCALE ]; then
  echo "Please specify a locale to run in!"
  exit 1
fi

if [ -z $TESTFILE ]; then
  echo "Please specify a Peacock test file to run (should be in mission/tests)!"
  exit 1
fi

echo "Running testfile $TESTFILE in locale $LOCALE."

export CUAUV_LOCALE=$LOCALE

auv-shm-cli aslam_buoy_a_in visible 0
auv-shm-cli aslam_buoy_b_in visible 0
auv-shm-cli aslam_buoy_c_in visible 0
auv-shm-cli aslam_buoy_d_in visible 0

auv-sim-defaults

auv-shm-cli navigation_settings enabled 1
auv-shm-cli navigation_settings position_controls 1
auv-shm-cli navigation_settings optimize 1

# Start requisite daemons.

auv-navigated &
nav_pid=$!

auv-terminal auv-control-helm -e &
helm_pid=$!

auv-aslamd &
aslam_pid=$!

peck i $TESTFILE &
peacock_pid=$!

sleep 1

auv-visualizer visualizer/aslam.cfg &
viz_pid=$!

wait $peacock_pid

kill $nav_pid $helm_pid $viz_pid $aslam_pid
