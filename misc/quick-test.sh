#!/bin/sh

TESTFILE=$1

if [ -z $TESTFILE ]; then
  echo "Please specify a Peacock test file to run (should be in mission/tests)!"
  exit 1
fi

# Ported from auv-simulate

if [ -z ${CUAUV_SOFTWARE} ]; then
  echo "Please set CUAUV_SOFTWARE to the root of the repo," \
       "with a trailing slash."
  exit 1
fi

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

peck i $1 &
peacock_pid=$!

sleep 1

auv-visualizer &
viz_pid=$!

wait $peacock_pid

kill $nav_pid $helm_pid $viz_pid $aslam_pid
