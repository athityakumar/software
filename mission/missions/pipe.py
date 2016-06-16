#!/usr/bin/env python3.4
from mission.framework.helpers import Finite
from mission.framework.primitive import *
from mission.framework.combinators import *
from mission.framework.movement import VelocityX, VelocityY, DeltaYaw, AbsoluteYaw, Depth
from mission.framework.targeting import *
from mission.framework.taskclasses import FiniteTask
from mission.framework.visiond import VisionModule
from absolute import *
import time


import shm

TORPEDO_OFFSET = -90

BuoyFail, WireFail = False, False

class Search(FiniteTask):
    def firstrun(self, timeout=45):
        self.surge_time = time.time()
        self.sway_time = time.time() - 3
        self.start = time.time()
        self.surge = VelocityX()
        self.sway = VelocityY()
        self.sway_speed = .4
        self.swaying = True
        self.surging = False
        self.begin_search = time.time()

        self.sway(self.sway_speed)
        print("IN PIPE")

    def run(self, timeout=30):
        print("Searching For Pipe")
        if not self.surging:
            self.surge_time = time.time()

        if not self.swaying:
            self.sway_time = time.time()

        if self.this_run - self.sway_time > 6:
            self.sway(0)
            self.sway_speed *= -1
            self.swaying=False
            self.surge(.25)
            self.surging = True
        
        if self.this_run - self.surge_time > 3:
            self.surge(0)
            self.surging=False
            self.sway(self.sway_speed)
            self.swaying = True

        if shm.pipe_results.heuristic_score.get() < 3000:# or shm.pipe_results.rectangularity.get() < .5:
            self.start = time.time()

        if self.this_run - self.start > .5 or self.this_run - self.begin_search > timeout:
            self.surge(0)
            self.sway(0)
            self._finish()

class SurgeToPipe(FiniteTask):
    def firstrun(self):
        self.start = time.time()
        self.surge = VelocityX(.3)
        self.count = time.time()

        self.surge()
    def run(self):
        if shm.pipe_results.heuristic_score.get() < 3000:
            self.start = time.time()

        if self.this_run - self.start > .4 or self.this_run - self.count > 10:
            self.surge(0)
            self._finish()

class SwayToPipe(FiniteTask):
    def firstrun(self):
        self.start = time.time()
        self.surge = VelocityX(.2)
        self.sway = VelocityY(.2)

        self.surge()
        self.sway()
    def run(self):
        if shm.pipe_results.heuristic_score.get() < 3000:
            self.start = time.time()

        if self.this_run - self.start > .6:
            self.surge(0)
            self.sway(0)
            self._finish()

class ToBuoy(FiniteTask):
    def firstrun(self, timeout=10):
        self.start = time.time()
        self.counter = time.time()

    def run(self, timeout=10):
        print("Looking for buoy")
        if self.this_run - self.counter > timeout:
            self._finish
            return

        if not (shm.red_buoy_results.area.get() > 2000):
            self.start = time.time()

        if self.this_run - self.start > .7:
            self._finish()

class ToTorpedoes(FiniteTask):
    def firstrun(self):
        self.start = time.time()
        self.counter = time.time()

    def firstrun(self):
        
        if self.this_run - self.counter > 35:
            self._finish
            return
        
        if shm.torpedo_results.target_center_x.get() < 1:
            self.start = time.time()

        if self.this_run - self.start > 1.7:
            self._finish()

class ToBins(FiniteTask):
    def firstrun(self):
        self.start = time.time()
        self.shmstuff = [shm.shape_banana.p, shm.shape_bijection.p, shm.shape_lightning.p, shm.shape_soda.p, shm.shape_handle.p]
        self.count = time.time()

    def run(self):
        if not any(map(lambda x: x.get() > .5, self.shmstuff)):
            self.start = time.time()

        if self.this_run - self.start > 1 or self.this_run - self.count > 20:
            self._finish()

class ToWire(FiniteTask):
    def firstrun(self):
        self.start = time.time()
        #shm.desires.depth.set(2.4)
        self.counter = time.time()

    def run(self):
        if self.this_run - self.counter > 28:
            self._finish()
            global WireFail
            WireFail = True
            return

        print("Going to wire")
        if shm.wire_results.area.get() < 18000:
            self.start = time.time()

        if self.this_run - self.start > 1:
            self._finish()

class center(FiniteTask):
    def firstrun(self):
        self.center = DownwardTarget(lambda: (shm.pipe_results.center_x.get(), shm.pipe_results.center_y.get()), deadband=(35,35))
        print("Centering on pipe")
        self.start = time.time()

    def run(self):
        print("Centering on pipe")
        self.center()

        if self.center.finished or self.this_run - self.start > 12:
            VelocityX(0)()
            VelocityY(0)()
            self.center._finish()
            self._finish()

class align(FiniteTask):
    def firstrun(self):
        self.align = PIDLoop(output_function=DeltaYaw(), target=0, input_value=lambda: shm.pipe_results.angle.get(), negate=True, deadband=2)
        self.start = time.time()

    def run(self):
        print("Aligning to pipe")
        self.align()

        if self.align.finished or self.this_run - self.start > 9:
            self._finish()

class turn(FiniteTask):
    def firstrun(self):
        
        self.yaw = AbsoluteYaw(TORPEDO_OFFSET)
        self.yaw()
    
    def run(self):
        
        if self.yaw.finished:
            self.yaw._finish()
            self._finish()

        self.yaw()


class Pause(FiniteTask):
    def firstrun(self, wait):
        self.start = time.time()

    def run(self, wait=4):
        if self.this_run - self.start > wait:
            self._finish()

class CheckBuoy(FiniteTask):
    def firstrun(self):
        if BuoyFail is False:
            self._finish()
            return
        self.go = ToRedBuoy

    def run(self):
        print("Navigating to buoy")
        self.go()

class CheckWire(FiniteTask):
    def firstrun(self):
        if WireFail is False:
            self._finish()
            return
        self.go = ToPortal

    def run(self):
        print("Navigating to wire")
        self.go()

class Forward(FiniteTask):
    def firstrun(self):
        self.go = VelocityX()
        self.start = time.time()

    def run(self):
        self.go(.7)
        if self.this_run - self.start > 6:
            self.go(0)
            self.go._finish()
            self._finish()

class CheckPipe(FiniteTask):
    def firstrun(self):
        self.c = center()
        self.a = align()
        self.state = 'c'
        self.start = time.time()
        if not (shm.pipe_results.heuristic_score.get() > 3000 and shm.pipe_results.rectangularity.get() > .75):
            self._finish()

    def run(self):
        if self.state is 'c':
            self.c()
            if self.this_run - self.start > 10:
                self.c._finish()
                self.start = time.time()
                self.state = 'a'
                return
        if self.state is 'a':
            self.a()
            if self.this_run - self.start > 6:
                self.a._finish()
                self._finish()



HeadingCenter = lambda: None
PipeCenter = center()
search = Search()
lineup = align()
test1 = Sequential(PipeCenter, lineup, VelocityX(.3))

check = CheckBuoy()

PipeNV = Sequential(Search(), center(), align(), VelocityX(.25))
PipeQ = Sequential(VisionModule("Recovery"), Pause(3), Search(20), center(), align())
Pipe = lambda begin, end: Sequential(VisionModule(begin), VisionModule(end, stop=True), Search(), center(), align(), Finite(Depth(2.2)))
Vision = lambda begin, end: Sequential(VisionModule(begin), VisionModule(end, stop=True))
BPipe = lambda begin, end: Sequential(VisionModule(begin), VisionModule(end, stop=True), center(), align(), Finite(Depth(2.4)))
PipeNoSearch = lambda begin, end: Sequential(VisionModule(begin), VisionModule(end, stop=True), Pause(2), SurgeToPipe(), center(), align())
FirstPipe = Sequential(VisionModule("redbuoy"), center(), align())


tobuoy = Sequential(FirstPipe, Forward(), MasterConcurrent(ToBuoy(), VelocityX(.6)), VelocityX(0))#, CheckBuoy())
towire = Sequential(Vision(begin="portal", end="redbuoy"), CheckPipe(), Finite(Depth(2.2)), MasterConcurrent(ToWire(), VelocityX(.35)), VelocityX(0))#, CheckWire())
totorpedoes = Sequential(PipeNoSearch(begin="torpedoes", end="portal"), MasterConcurrent(ToTorpedoes(), VelocityX(.25)), VelocityX(0))
tobins = Sequential(turn(), VisionModule("bins"), VisionModule("torpedoes", stop=True), MasterConcurrent(ToBins(), VelocityX(.3)), VelocityX(0))


start = Sequential(Finite(Depth(.35)), MasterConcurrent(ToBuoy(timeout=70), VelocityX(.3)), VelocityX(0))
