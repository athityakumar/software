#will add import statements here later
from mission.framework.targeting import DownwardTarget
# from mission.framework.task import Task
from mission.framework.task import *
from mission.framework.timing import Timer
from mission.framework.combinators import Sequential, Concurrent, MasterConcurrent

# from mission.framework.movement import VelocityX, VelocityY, RelativeToCurrentHeading
from mission.framework.movement import *
# from mission.framework.position import MoveX, MoveY
from mission.framework.position import *

FAST_RUN = False
#may simply drop markers into open bin if running out of time

"""shm fields to be added (not yet in shm, but we can just work with these fields for now as placeholders, feel free to add more if you want)
shm.bin1.x
shm.bin1.y

#boolean value
shm.bin1.covered

#probability
shm.bin1.p

#same for second
shm.bin2.x
shm.bin2.y
shm.bin2.covered
shm.bin2.p"""

#import shm.bin1 as bin1
#import shm.bin2 as bin2

import shm

bin1 = shm.bin1
bin2 = shm.bin2

# CAMERA_WIDTH = shm.camera.downward_width.get()
# CAMERA_HEIGHT = shm.camera.downward_height.get()

CAMERA_WIDTH = 512
CAMERA_HEIGHT = 512

CAMERA_CENTER_X = CAMERA_WIDTH / 2
CAMERA_CENTER_Y = CAMERA_HEIGHT / 2

GIVEN_DISTANCE = 2 # meters
BIN_CONFIDENCE = .7
 
PERCENT_GIVEN_DISTANCE_SEARCH = .2 # percent of given distance to back up and check
SEARCH_SIDE_DISTANCE = 3 # meters side to side
SEARCH_ADVANCE_DISTANCE = 1 # meters to advance with each zigzag


#actuators = [shm.actuator_1.trigger, shm.actuator_2.trigger]
actuators = [shm.actuator_desires.trigger_01, shm.actuator_desires.trigger_02]


def check_uncovered():
    """Actually, this is really rough, this function should probably store the sub's current postion, move the sub to a position where both bins are visible, and then return to the original position"""
    return not bin1.covered and not bin2.covered

class BinsTask(Task):
    """Drops markers into target bin

    Current setup:
    Search for bins
    Center over target bin (assume covered bin initially)
    Try two times to remove lid
    If succeed, center over bin and drop markers in
        If fail twice, switch target bin to uncovered bin and drop markers

    Start: near bins (used pinger to locate), any position
    Finish: centered over target bin, both markers dropped
    """
    def on_first_run(self, *args, **kwargs):
        print("Starting bins task!")
        self.logv("Starting BinsTask task")
        self.init_time = self.this_run_time

        
        self.search_and_identify = Sequential(SearchBinsTask(), IdentifyBins())

        self.search_and_identify()
        
        self.try_removal = None
        self.drop_task = DropMarkers()
        #add CheckDrop task later if considered relevant/useful

    def on_run(self):
        # self.logv("running bt")
        if not self.search_and_identify.has_ever_finished:
            self.search_and_identify()

        if self.search_and_identify.has_ever_finished and not self.drop_task.has_ever_finished:
            self.drop_task()

        if self.drop_task.has_ever_finished:
            self.finish()
            # SearchBinsTask()

        # if not self.try_removal:
        #     self.try_removal = TwoTries()
        # elif not self.try_removal.has_ever_finished:
        #     self.try_removal()
        
        # #completed and succeded in removing lid
        # elif self.try_removal.success:
        #     self.drop_task = DropMarkers()
        
        # #did not remove lid after two tries, search and center over uncovered bin
        # else:
        #     FAST_RUN = True
        #     self.search_and_identify = Sequential(SearchBinsTask(), IdentifyBins())
        #     self.drop_task = DropMarkers()

        # #drop task either created after successfully uncovered bin OR doing simple run
        # if self.search_and_identify.has_ever_finished and self.drop_task and not self.drop_task.has_ever_finished:
        #     self.drop_task()

        # if self.drop_task.has_ever_finished:
        #     self.finish()

    def on_finish(self):
        print("Task completed!")
        self.logv('BinsTask task finished in {} seconds!'.format(
            self.this_run_time - self.init_time))

class SearchBinsTask(Task):
    """Uses SearchBinsTaskHelper in a MasterConcurrent with CheckBinsInSight"""
    def on_first_run(self, *args, **kwargs):
        print("Looking for bins...")
        self.logv("Starting SearchBinsTask")
        self.init_time = self.this_run_time
        # self.task = MasterConcurrent(SearchBinsTaskHelper(), CheckBinsInSight())
        self.task = MasterConcurrent(CheckBinsInSight(), SearchBinsTaskHelper())
        self.task()
    def on_run(self):
        self.task()
        if self.task.has_ever_finished:
            VelocityX(0.0)()
            self.finish()
    def on_finish(self):
        print("Found bin!")
        self.logv('SearchBins task finished in {} seconds!'.format(
            self.this_run_time - self.init_time))

class SearchBinsTaskHelper(Task):
    """Looks around for bins, either covered or uncovered depending on FAST_RUN

    Suggestion: look around until the probabilities are > 0 for each bin? (see above for values imported from shm)

    Start: near bins (used pinger to locate), any position
    Finish: both bins visible in downward cam 
    """
    def on_first_run(self, *args, **kwargs):
        self.logv("Starting SearchHelperTask task")
        self.init_time = self.this_run_time
        self.count = 0
#        self.zigzag = Sequential(Finite(MoveY(-SEARCH_SIDE_DISTANCE * 2)),
#                                  Finite(MoveX(SEARCH_ADVANCE_DISTANCE)),
#                                  Finite(MoveY(SEARCH_SIDE_DISTANCE * 2)),
#                                  Finite(MoveX(SEARCH_ADVANCE_DISTANCE)))

        # self.zigzag = Sequential(MoveY(-SEARCH_SIDE_DISTANCE * 2),
        #                         MoveX(SEARCH_ADVANCE_DISTANCE),
        #                         MoveY(SEARCH_SIDE_DISTANCE * 2),
        #                         MoveX(SEARCH_ADVANCE_DISTANCE))

        self.zigzag = VelocityX(0.5)
        self.stop = VelocityX(0.0)

        self.zigzag()

    def on_run(self):
        # self.logv("in sbth!")
        self.zigzag()

        if self.zigzag.has_ever_finished:
            self.count += 1
            if self.cycleCount < ((given_distance * PERCENT_GIVEN_DISTANCE_SEARCH * 2) / SEARCH_ADVANCE_DISTANCE) + 1:
                self.zigzag()
            else:
                self.loge("Failed to find bins")
                self.finish()

    def on_finish(self):
        self.stop()
        self.logv('SearchHelperTask task finished in {} seconds!'.format(
            self.this_run_time - self.init_time))

class CheckBinsInSight(Task):
    """ Checks if both bins are in sight of the cameras
    Used in SearchBinsTask as MasterConcurrent's end condition"""
    def on_first_run(self, *args, **kwargs):
        self.logv("Checking if bins in sight")
        self.init_time = self.this_run_time

    def on_run(self):
        # self.logv("running cbis")
        if shm.bin1.p.get() > 0.1 and shm.bin2.p.get() > 0.1:
            self.logv("probabilities work!")
            self.finish()
        pass

    def on_finish(self):
        VelocityX(0.0)()
        self.logv('CheckBinsInSight task finished in {} seconds!'.format(
            self.this_run_time - self.init_time))

class IdentifyBins(Task):
    """Identifies which bin to drop markers into, centers over it

    Start: Both bins visible in downward cam
    Finish: Centered over chosen bin 
    """
    def on_first_run(self, *args, **kwargs):
        print("Centering over bins...")
        self.logv("Starting IdentifyBins task")
        self.init_time = self.this_run_time

        if bin1.covered == FAST_RUN:
            self.target_bin = bin1
        else:
            self.target_bin = bin2

    def on_run(self):
       # self.center = DownwardTarget(lambda: (shm.pipe_results.center_x.get(), shm.pipe_results.center_y.get()), deadband=(35,35))

        self.task = DownwardTarget(lambda: (shm.bin1.x.get(), shm.bin2.y.get()), target = (CAMERA_WIDTH / 2, CAMERA_HEIGHT / 2), deadband=(35,35))
        
        self.task()

        if self.task.finished:
            VelocityX(0)()
            VelocityY(0)()
            self.finish()

    def on_finish(self):
        print("Centered!")
        self.logv('IdentifyBins task finished in {} seconds!'.format(
            self.this_run_time - self.init_time))


class TwoTries(Task):
    """Keeps track of how many times sub tried to uncover bin, changes variable FAST_RUN to True if sub was unable to take off bin cover

    Note: tried to keep logic as generic as possible, with self.attempt_task and self.check_done so can be reused for other missions

    Start: centered over covered bin, no markers dropped
    Finish: centered over covered bin, either both or no markers dropped
    """
    def on_first_run(self, *args, **kwargs):
        self.logv("Starting TwoTries task")
        self.init_time = self.this_run_time

        self.attempt_task = UncoverBin()
        self.check_done = check_uncovered

        self.success = False
        self.tries_completed = 0

    def on_run(self): 
        if self.tries_completed==0:
            if not self.attempt_task.has_ever_finished:
                self.attempt_task()
            else:
                if self.check_done():
                    self.success = True
                    self.finish()
                else:
                    self.tries_completed = 1
                    self.attempt_task = UncoverBin()
        else: #one completed try, one try left
            if not self.attempt_task.has_ever_finished:
                self.attempt_task()
            else:
                self.success = self.check_done()
                self.finish()

    def on_finish(self):
        self.logv('TwoTries task finished in {} seconds!'.format(
            self.this_run_time - self.init_time))

class UncoverBin(Task):
    """Uses arm to remove bin cover (will most likely be Sequential?)

    LEAVE AS STUB UNTIL WE FIND OUT MORE ABOUT DOWNWARD MANIPULATION

    Start: centered over covered bin, no markers dropped
    Finish: centered over now-uncovered bin
    """
    def on_first_run(self, *args, **kwargs):
        self.logv("Starting UncoverBin task")
        self.init_time = self.this_run_time

    def on_run(self):
        pass

    def on_finish(self):
        self.logv('UncoverBin task finished in {} seconds!'.format(
            self.this_run_time - self.init_time))

class SetActuator(Task):
    """ Assigns a value to an actuator"""
    def on_first_run(self, actuator, value):
        actuator.set(value)
        self.finish()

    def on_run(self):
        self.finish()        


class DropMarkers(Task):
    """Drops markers into target bin

    Will need to lower self towards bin for better dropping accuracy

    Start: centered over target bin, no markers dropped
    Finish: centered over target bin, both markers dropped
    """
    def on_first_run(self, *args, **kwargs):
        print("Dropping markers...")
        self.logv("Starting DropMarkers task")
        self.init_time = self.this_run_time

        # self.setDepth = Depth(shm.kalman.depth.get() + shm.dvl.savg_altitude.get() - 0.5) # go to 0.5m above bin
        # self.task1 = Sequential(SetActuator(actuators[0], 1), Timer(0.5), SetActuator(actuators[0], 0))
        # self.task2 = Sequential(SetActuator(actuators[1], 1), Timer(0.5), SetActuator(actuators[1], 0))

        # self.task1 = Sequential(actuators[0].set(1), Timer(0.5), actuators[0].set(0))
        # self.task2 = Sequential(actuators[1].set(1), Timer(0.5), actuators[1].set(0))

        self.timer = Timer(2.0)
        actuators[0].set(1)
        actuators[1].set(1)

        self.timer()

        # self.dropsTask = Concurrent(self.task1, self.task2)
        # self.task = Sequential(self.setDepth, self.dropsTask)
        # self.task = self.dropsTask

        # self.task = SetActuator(actuators[0], 1)


    def on_run(self):
        if self.timer.has_ever_finished:
            actuators[0].set(0)
            actuators[1].set(0)

            self.finish()
        else:
            self.timer()
        # self.task()


    def on_finish(self):
        print("Dropped markers!")
        self.logv('DropMarkers task finished in {} seconds!'.format(
            self.this_run_time - self.init_time))

class CheckDrop(Task):
    """Confirm marker dropped into target bin

    LEAVE AS STUB FOR NOW, SERVES NO REAL USE IN MISSION

    Start: centered over target bin, some? markers dropped
    Finish: Know if markers have actually been dropped.
    """
    def on_first_run(self, *args, **kwargs):
        self.logv("Starting CheckDrop task")
        self.init_time = self.this_run_time

    def on_run(self):
        pass

    def on_finish(self):
        self.logv('CheckDrop task finished in {} seconds!'.format(
            self.this_run_time - self.init_time))
