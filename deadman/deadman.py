#!/usr/bin/env python3

#while true, ping router, if 5 sec without response, softkill
import time
import os, platform

from auvlog.client import Logger, log
import shm

IP_ADDRESS = '192.168.0.1'
INTERVAL = 1 #seconds between pings
TIMEOUT = 5 #seconds before softkill

def ping(host):
    """
    Returns True if host responds to a ping request
    """

    # Ping parameters as function of OS
    ping_str = "-n 1" if platform.system().lower()=="windows" else "-c 1"

    # Ping
    return os.system("ping " + ping_str + " " + host + '>/dev/null') == 0

walled_time = 0
def watch_voltage():
    """
    Posts a wall message to all users who are logged in when the voltage goes
    below safe levels
    """
    global walled_time

    THOR_SAFE_VOLTAGE = 21
    LOKI_SAFE_VOLTAGE = 10.5
    if time.time() - walled_time > 600: # wall only once every 10 minutes
        if os.environ['CUAUV_VEHICLE'] == "thor":
            current_voltage = shm.merge_status.total_voltage.get()
            if current_voltage < THOR_SAFE_VOLTAGE:
                msg = 'WARNING: Voltage is currently at {}. Battery change recommended!'.format(current_voltage)
                os.system('echo {} | wall'.format(msg))
                walled_time = time.time()
        elif os.environ['CUAUV_VEHICLE'] == 'loki':
            current_voltage = shm.minipower_status.vout.get()
            if current_voltage < LOKI_SAFE_VOLTAGE:
                msg = 'WARNING: Voltage is currently at {}. Battery change recommended!'.format(current_voltage)
                os.system('echo {} | wall'.format(msg))
                walled_time = time.time()

if __name__ == '__main__':
    last_contact = None
    time_start = time.time()
    os.system("> /tmp/auv-deadman")
    while True:
        watch_voltage()
        if ping(IP_ADDRESS):
            last_contact = time.time()
            log.deadman('Ping succeeded at ' + str(last_contact) + ' seconds', copy_to_stdout=True)
        else:
            if last_contact:
                time_elapsed = time.time() - last_contact
                log.deadman('Last successful ping ' + str(time_elapsed) + ' seconds ago', copy_to_stdout=True)
            else:
                time_elapsed = time.time() - time_start
                log.deadman('No successful pings ' + str(time_elapsed) + ' seconds since start', copy_to_stdout=True)

            if time_elapsed >= TIMEOUT:
                log.deadman.critical('Too long since last ping, softkilling now...', copy_to_stdout=True)
                shm.switches.soft_kill.set(True)
                os.system("echo 'Timeout at "+str(time.time())+"' > /tmp/auv-deadman")

        time.sleep(INTERVAL)
