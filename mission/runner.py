#!/usr/bin/python3
import argparse
import functools
import os
import signal
import sys
import time
import types

from auvlog.client import log
from mission.framework.primitive import ZeroIncludingPitchRoll

parser = argparse.ArgumentParser()

parser.add_argument("-f", "--frequency", help="Target tick frequency. Default value of 60.", type=int, default=60)
# TODO: Implement the verbosity option
parser.add_argument("-v", "--verbosity", choices=["DEBUG", "INFO", "WARN", "ERROR"], default="WARN",
                    help="Lowest log level to copy to stdout by default. Default value is \"WARN\"")
parser.add_argument("-d", "--directory", default="missions",
                    help="Directory where task is found. Default value of \"missions\"")
parser.add_argument("task", help="Root task to run.")
parser.add_argument("args", nargs="*", help="Arguments passed to the task.")
parser.add_argument("--ignore-exceptions", help="Ignore any exceptions. USE WITH CAUTION.", action='store_true')

args = parser.parse_args()

full_name = "{}.{}".format(args.directory, args.task)
module_name, task_name = full_name.rsplit(".", 1)
module = __import__(module_name, fromlist=task_name)
task = getattr(module, task_name)

# If the name given is a class or function, instantiate it and pass arguments.
if isinstance(task, (type, types.FunctionType, functools.partial)):
    converted_args = []
    for arg in args.args:
        try:
            f_arg = float(arg)
        except ValueError:
            f_arg = arg

        converted_args.append(f_arg)

    task = task(*converted_args)

elif len(args.args) > 0:
    log("Arguments only supported for uninstantiated Tasks.",
        copy_to_stdout=True)
    sys.exit(1)

period = 1 / args.frequency

logger = log.mission.main

# Ensure only one mission can run at a time.
LOCK_NAME = ".mission_lock"
lock_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), LOCK_NAME)
try:
    os.mkdir(lock_dir)
except OSError:
    logger("A MISSION IS ALREADY RUNNING! Aborting...", copy_to_stdout=True)
    logger("If I am mistaken, delete %s or check permissions" % lock_dir,
        copy_to_stdout=True)
    sys.exit(1)

def release_lock():
    os.rmdir(lock_dir)

def cleanup():
    ZeroIncludingPitchRoll()()
    release_lock()

def exit_handler(signal, frame):
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, exit_handler)
signal.signal(signal.SIGTERM, exit_handler)

while True:
    begin_time = time.time()

    try:
        task()
    except Exception as e:
        if not args.ignore_exceptions:
            cleanup()
            raise
        else:
            import traceback
            traceback.print_exc()
            logger("EXCEPTION ENCOUNTERED! Continuing anyway...")

    if task.has_ever_finished:
        break

    end_time = time.time()
    duration = end_time - begin_time

    if period > duration:
        time.sleep(period - duration)
    else:
        logger("MISSION TOOK TOO LONG TO RUN; Can't maintain %d HZ" % \
               args.frequency, copy_to_stdout=True)

release_lock()
