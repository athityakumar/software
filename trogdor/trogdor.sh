#!/bin/bash

# CONFIGURATION

ROOT=$CUAUV_SOFTWARE
LOGS=/var/log/auv/current # Should be set up by auv-pooltest
BIN=$ROOT/link-stage

# Very important variables
export PATH=$PATH:$ROOT/link-stage
export PYTHONPATH=$ROOT

# PORT MAPPINGS

GX4_PORT=/dev/ttyUSB_thor_GX4
GX1_PORT=/dev/ttyUSB_loki_GX1
DVL_PORT=/dev/ttyUSB_thor_DVL
SONAR_IP=169.254.178.66

# CONFIGS

VISION_CONFIG=$ROOT/vision/configs/master.yaml

# SERVICES

SUBMARINE=$CUAUV_VEHICLE

if [ "$SUBMARINE" = "thor" ]; then
  SERVICES=(seriald gx4d dvld kalmand navigated controld3 shmserver visiond forecam-left forecam-right downcam ueye deadman logging uptime sonard)
elif [ "$SUBMARINE" = "loki" ]; then
  SERVICES=(seriald gx1d kalmand navigated controld3 shmserver visiond downcam deadman logging uptime)
else
  echo "Unsupported submarine! Must be set to one of { thor, loki }!"
fi

# COLORS

GRAY="\033[0;30m"
CYAN="\033[0;36m"
RED="\033[1;31m"
BLUE="\033[0;34m"
YELLOW="\033[0;33m"
GREEN="\033[1;32m"
ENDCOLOR="\033[0m"

# FUNCTIONS

log () {
  STR="[$CYAN`date -u +"%Y/%m/%d %H:%M:%S UTC"`$ENDCOLOR] ($YELLOW""TROGDOR""$ENDCOLOR) $1"
  echo -e $STR
  echo $STR &>> $LOGS/trogdor.log
}

invoke () {
  log "Invoking \"$1\"."
  $1
}

fork () {
  log "Forking \"$1 &> $LOGS/$2.log\"."
  $1 &>> $LOGS/$2.log &
}

pkill () {
  log "Killing \"$1\"."
  PIDS=`pids $1`
  if [ -z "$PIDS" ]; then
      log "No PIDs found for \"$1\"."
  else
      invoke "kill $PIDS"
  fi
}

pids () {
  pgrep -fl "$1" | grep -v "grep" | grep -v "vim" | grep -v "emacs" | cut -d' ' -f1
}

usage () {
  echo "Usage: {t / trogdor} {start | stop | restart | status | assert} SERVICE"
}

servicestatus () {
  if [ -z "`pids $1`" ]; then
    log "$RED""$2""$ENDCOLOR"
  else
    log "$GREEN""$2""$ENDCOLOR"
  fi
}

assertservice () {
  if [ -z "`pids $2`" ]; then
    log "$1 seems to be ""$RED""DOWN""$ENDCOLOR""; restarting."
    trogdor start $1
  else
    log "$1 seems to be ""$GREEN""UP""$ENDCOLOR""."
  fi
}

COMMAND=$1
SERVICE=$2

if [ -z "$COMMAND" ]; then
    COMMAND="status"
fi

if [ -z "$SERVICE" ]; then
    log "No service specified; executing on all known."
    for SERVICE in ${SERVICES[@]}
    do
        trogdor $COMMAND $SERVICE
    done
    exit 0
fi

case $COMMAND in
    start)
        case $SERVICE in
            visiond|vision) fork "auv-visiond start -d $VISION_CONFIG" "visiond";;
            cameras) 
                if [ "$SUBMARINE" = "thor" ]; then
                    fork "auv-camera ueyeleft" "camera_ueyeleft"
                    fork "auv-camera ueyeright" "camera_ueyeright"
                    fork "auv-camera ueyedown" "camera_ueyedown"
                elif [ "$SUBMARINE" = "loki" ]; then
                    fork "auv-camera ximea" "camera_ximea"
                fi ;;
            forecam-left) fork "auv-camera ueyeleft" "camera_ueyeleft" ;;
            forecam-right) fork "auv-camera ueyeright" "camera_ueyeright" ;;
            downcam)
                if [ "$SUBMARINE" = "thor" ]; then
                    fork "auv-camera ueyedown" "camera_ueyedown"
                elif [ "$SUBMARINE" = "loki" ]; then
                    fork "auv-camera ximea" "camera_ximea"
                fi ;;
            seriald|serial) auv-led off; fork "auv-seriald" "seriald" ;;
            sonard|sonar) fork "auv-sonard NET $SONAR_IP" "sonard" ;;
            gx4d|gx4) fork "auv-3dmgx4d $GX4_PORT" "gx4d" ;;
            gx1d|gx1) fork "auv-3dmgd $GX1_PORT" "gx1d" ;;
            dvld|dvl) fork "auv-dvld $DVL_PORT" "dvld" ;;
            kalmand|kalman) fork "auv-kalmand" "kalmand" ;;
            navigated|navigate) fork "auv-navigated" "navigated" ;;
            controld3|controld|control) fork "auv-controld3" "controld3" ;;
            shmserver) fork "auv-shm server" "shmserver" ;;
            log|logs|logger|logging) fork "auv-ld" "auv-ld" ;;
            ueye) invoke "sudo /etc/init.d/ueyeethdrc start" ;;
            led) fork "auv-led daemon" "led" ;;
            deadman) fork "auv-deadman" "deadman" ;;
            uptime) fork "auv-uptimed" "uptime" ;;
            *) log "Service \"$SERVICE\" not found; aborting." ;;
        esac
    ;;

    stop)
        case $SERVICE in
            visiond|vision) invoke "auv-visiond stop" ;;
            cameras) 
                if [ "$SUBMARINE" = "thor" ]; then
                    pkill "auv-camera ueyeleft"
                    pkill "auv-camera ueyeright"
                    pkill "auv-camera ueyedown"
                elif [ "$SUBMARINE" = "loki" ]; then
                    pkill "auv-camera ximea"
                fi ;;
            forecam-left) pkill "auv-camera ueyeleft" ;;
            forecam-right) pkill "auv-camera ueyeright" ;;
            downcam)
                if [ "$SUBMARINE" = "thor" ]; then
                    pkill "auv-camera ueyedown"
                elif [ "$SUBMARINE" = "loki" ]; then
                    pkill "auv-camera ximea"
                fi ;;
            seriald|serial) auv-led on; pkill "auv-seriald" ;;
            sonard|sonar) pkill "auv-sonard" ;;
            gx4d|gx4) pkill "auv-3dmgx4d" ;;
            gx1d|gx1) pkill "auv-3dmgd" ;;
            dvld|dvl) pkill "auv-dvld" ;;
            kalmand|kalman) pkill "auv-kalmand" ;;
            navigated|navigate) pkill "auv-navigated" ;;
            controld3|controld|control) pkill "auv-controld3" ;;
            shmserver) pkill "auv-shm server" ;;
            log|logs|logger|logging) pkill "auv-ld" ;;
            ueye) invoke "sudo /etc/init.d/ueyeethdrc stop" ;;
            led) pkill "/home/software/misc/led.py" ;;
            deadman) pkill "auv-deadman" ;;
            uptime) pkill "auv-uptimed" ;;
            *) log "Service \"$SERVICE\" not found; aborting." ;;
        esac
    ;;

    restart)
        case $SERVICE in
          seriald|serial)
            trogdor stop $SERVICE
            sleep 3
            trogdor start $SERVICE
          ;;
          *)
            trogdor stop $SERVICE
            trogdor start $SERVICE
          ;;
        esac
    ;;

    status)
        case $SERVICE in
            visiond|vision) servicestatus "auv-visiond" "visiond" ;;
            forecam-left) servicestatus "auv-camera ueyeleft" "forecam-right" ;;
            forecam-right) servicestatus "auv-camera ueyeright" "forecam-left" ;;
            downcam)
                if [ "$SUBMARINE" = "thor" ]; then
                    servicestatus "auv-camera ueyedown" "downcam"
                elif [ "$SUBMARINE" = "loki" ]; then
                    servicestatus "auv-camera ximea" "downcam"
                fi ;;
            seriald|serial) servicestatus "auv-seriald" "seriald" ;;
            sonard|sonar) servicestatus "auv-sonard" "sonard" ;;
            gx4d|gx4) servicestatus "auv-3dmgx4d" "gx4d" ;;
            gx1d|gx1) servicestatus "auv-3dmgd" "gx1d" ;;
            dvld|dvl) servicestatus "auv-dvld" "dvld" ;;
            kalmand|kalman) servicestatus "auv-kalmand" "kalmand" ;;
            navigated|navigate) servicestatus "auv-navigated" "navigated" ;;
            controld3|controld|control) servicestatus "auv-controld3" "controld3" ;;
            log|logs|logger|logging) servicestatus "auv-ld" "logging" ;;
            ueye) servicestatus "ueyeethd" "ueye" ;;
            shmserver) servicestatus "auv-shm server" "shmserver" ;;
            led) servicestatus "/home/software/trunk/misc/hydro_reset.py" "led" ;;
            deadman) servicestatus "auv-deadman" "deadman" ;;
            uptime) servicestatus "auv-uptimed" "uptime" ;;
            *) log "Service \"$SERVICE\" not found; aborting." ;;
        esac
    ;;

    assert)
        case $SERVICE in
            visiond|vision) assertservice "visiond" "auv-visiond start $VISION_CONFIG" ;;
            cameras) 
                if [ "$SUBMARINE" = "thor" ]; then
                    assertservice "forecam-left" "auv-camera ueyeleft" 
                    assertservice "forecam-right" "auv-camera ueyeright" 
                    assertservice "downcam" "auv-camera ueyedown"
                elif [ "$SUBMARINE" = "loki" ]; then
                    assertservice "downcam" "camera_ximea"  
                fi ;;
            forecam-left) assertservice "forecam-left" "auv-camera ueyeleft" ;;
            forecam-right) assertservice "forecam-right" "auv-camera ueyeright" ;;
            downcam)
                if [ "$SUBMARINE" = "thor" ]; then
                    assertservice "downcam" "auv-camera ueyedown"
                elif [ "$SUBMARINE" = "loki" ]; then
                    assertservice "downcam" "auv-camera ximea"
                fi ;;
            seriald|serial) assertservice "serial" "seriald" ;;
            sonard|sonar) assertservice "sonard" "auv-sonard NET $SONAR_IP" ;;
            gx4d|gx4) assertservice "gx4d" "auv-3dmgx4d $GX4_PORT" ;;
            gx1d|gx1) assertservice "gx1d" "auv-3dmgd $GX1_PORT" ;;
            dvld|dvl) assertservice "dvld" "auv-dvld $DVL_PORT" ;;
            kalmand|kalman) assertservice "kalmand" "auv-kalmand" ;;
            navigated|navigate) assertservice "navigated" "auv-navigated" ;;
            controld3|controld|control) assertservice "controld3" "auv-controld3" ;;
            log|logs|logger|logging) assertservice "logging" "auv-ld" ;;
            shmserver) assertservice "shmserver" "auv-shm server" ;;
            led) assertservice "led" "auv-led daemon" ;;
            deadman) assertservice "deadman" "auv-deadman" ;;
            uptime) assertservice "uptime" "auv-uptimed" ;;
            ueye)
                if [ -z "`pids ueyeethd`" ]; then
                    trogdor stop ueye
                    trogdor start ueye
                else
                    log "ueye seems to be ""$GREEN""UP""$ENDCOLOR""."
                fi
            ;;
            *) log "Service \"$SERVICE\" not found; aborting." ;;
        esac
    ;;

    *)
        usage
    ;;
esac
