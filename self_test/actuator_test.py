#!/usr/bin/env python2

import signal
import shm
from time import sleep
from sys import exit
from auval.vehicle import shared_vars

def get_actuator(trigger):
    s = trigger.__module__
    return shm.__getattribute__(s.split(".")[1])

class ActuatorTest(object):
    # Air time in milliseconds
    TEST_DURATION = 50
    actuators = [get_actuator(shared_vars[act]) for act in ["torpedo_left", "torpedo_right", \
                                      "marker_dropper_1", "marker_dropper_2"]]
    durations = [act.duration.get() for act in actuators]

    @classmethod
    def run_test(cls):
        for act in cls.actuators:
            act.duration.set(cls.TEST_DURATION)
            print "Firing %s" % act
            act.trigger.set(1)
            sleep(0.8)

        cls.cleanup()

    @classmethod
    def cleanup(cls):
        for act, dur in zip(cls.actuators, cls.durations):
            act.duration.set(dur)
            act.trigger.set(0)


if __name__ == "__main__":
    def interrupt(signal, frame):
        ActuatorTest.cleanup()
        exit(0)

    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)

    print "ATTENTION: This will fire both torpedos and markers!"
    print "\tBe sure that grabbers have not been reassigned"
    print "\tPress ENTER to continue or Control-C to quit"
    raw_input()

    ActuatorTest.run_test()
