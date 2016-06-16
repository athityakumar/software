import shm
from shm import kalman
from mission.framework.task import Task
from mission.framework.targeting import DownwardTarget, ForwardTarget, PIDLoop
from mission.framework.combinators import Sequential, Concurrent
from mission.framework.movement import VelocityX, VelocityY, Heading, Depth, Pitch, Roll, RelativeToInitialHeading
from mission.framework.timing import Timer
from mission.framework.primitive import NoOp, FunctionTask, Zero
from scipy.signal import medfilt
from collections import deque

'''
Recovery 2016
Current Status: Somewhat implemented

Known Issues: Needs peacock tests and better failure mode handling

Strategy:
1.  Travel to pinger (need to decide exactly how to determine we're close enough).
2.  Lock onto a doubloon in vision.
3.  Travel towards the doubloon, centering on it.
4.  Attempt to pick up the doubloon.
5.  If doubloon was acquired (no longer visible in vision):
        Surface with the doubloon.
    Else:
        Attempt to pick up doubloon again. Make 3 attempts before moving on (what to do here?).
6.  Travel to the table.
7.  Lock onto the X in vision.
8.  Travel towards the X, centering on it.
9.  Attempt to drop the doubloon on the X.
10. If doubloon is visible on table:
        Attempt to pick up doubloon. Make 3 attempts before moving on (what to do here?).
        If successful, repeat 7-9.
    Else if X is visible on table and doubloon is not:
        Doubloon still falling or gripper failed to release. Wait then repeat 9.
    Else if doubloon is visible on table and X is not:
        Success! If this is the first doubloon, repeat 1-10. Else, mission win.
    Else:
        Vision results must be noisy, or we navigated to the table incorrectly.
        Sway search until we lock onto an X or a doubloon in vision, then repeat 10.
        If no lock acquired after some amount of time, mission fail; move on.
'''

'''
NOTE: MAINTAIN INVARIANT THAT THE DOUBLOONS AND MARKERS FOUND IN THE VISION
MODULE ARE NUMBERED FROM TOP LEFT.
This means that the first doubloon found in the vision module is top-left
relative to the second doubloon found.
'''


TOWER_MIN_AREA = 500
TOWER_MAX_AREA = 4000
TOWER_FORWARD_MIN_AREA = 1000
TOWER_AREA_THRESH = 1
PINGER_CONFIDENCE_THRESH = 0.8

MIN_MARKER_SCORE = 0.5
SURFACE_TIME = 3 # seconds

FORWARD_CAM_CENTER = (shm.camera.forward_width.get() / 2,
                      shm.camera.forward_height.get() / 2)
DOWNWARD_CAM_CENTER = (shm.camera.downward_width.get() / 2,
                       shm.camera.downward_height.get() / 2)

DOUBLOONS = ({'probability': shm.recovery_results.doubloon_1_probability,
              'area': shm.recovery_results.doubloon_1_area,
              'x': shm.recovery_results.doubloon_1_x,
              'y': shm.recovery_results.doubloon_1_y
              },
              {'probability': shm.recovery_results.doubloon_2_probability,
               'area': shm.recovery_results.doubloon_2_area,
               'x': shm.recovery_results.doubloon_2_x,
               'y': shm.recovery_results.doubloon_2_y
              }
            )

class Spiral(Task):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.forward_time = 1
        self.FORWARD_TIME_INCREMENT = 1
        Zero()()
        self.l_task_creator = lambda: Sequential(Concurrent(VelocityX(1, error=0.7),
                                            Timer(lambda: self.forward_time)),
                                 VelocityX(0, error=0.1),
                                 RelativeToInitialHeading(90, error=0.1),
                                 Concurrent(VelocityX(1, error=0.7),
                                            Timer(lambda: self.forward_time)),
                                 VelocityX(0, error=0.1),
                                 RelativeToInitialHeading(90, error=0.1),
                                 FunctionTask(self.increment_time),
                                 Concurrent(VelocityX(1, error=0.7),
                                            Timer(lambda: self.forward_time)),
                                 VelocityX(0, error=0.1),
                                 RelativeToInitialHeading(90, error=0.1)
                                 )
        self.l_task = self.l_task_creator()
        self.MAX_LOOPS = 10
        self.loops = 0

    def on_run(self, *args, **kwargs):
        self.logv("Running {}".format(self.__class__.__name__))
        if self.loops > self.MAX_LOOPS:
            self.logv("{} surpassed the maximum number of loops!".format(
                self.__class__.__name__))
            self.finish()
        else:
            self.l_task()
            if self.l_task.finished:
                self.l_task = self.l_task_creator()
                self.loops += 1

    def increment_time(self):
        self.forward_time += 1

# TODO: Get actuator numbers for arm and grabber
class ExtendArm(Task):
    def on_first_run(self, *args, **kwargs):
        shm.actuator_desires.trigger_01.set(True)   # the two arm actuators cannot both be on
        shm.actuator_desires.trigger_02.set(False)
    def on_run(self, *args, **kwargs):
        if shm.actuator_desires.trigger_01.get() and not shm.actuator_desires.trigger_02.get():
            self.finish()

class RetractArm(Task):
    def on_first_run(self, *args, **kwargs):
        shm.actuator_desires.trigger_01.set(False)  # the two arm actuators cannot both be on
        shm.actuator_desires.trigger_02.set(True)
    def on_run(self, *args, **kwargs):
        if not shm.actuator_desires.trigger_01.get() and shm.actuator_desires.trigger_02.get():
            self.finish()

class OpenGrabber(Task):
    def on_first_run(self, *args, **kwargs):
        shm.actuator_desires.trigger_03.set(True)   # the two grabber actuators cannot both be on
        shm.actuator_desires.trigger_04.set(False)
    def on_run(self, *args, **kwargs):
        if shm.actuator_desires.trigger_03.get() and not shm.actuator_desires.trigger_04.get():
            self.finish()

class CloseGrabber(Task):
    def on_first_run(self, *args, **kwargs):
        shm.actuator_desires.trigger_03.set(False)  # the two grabber actuators cannot both be on
        shm.actuator_desires.trigger_04.set(True)
    def on_run(self, *args, **kwargs):
        if not shm.actuator_desires.trigger_03.get() and shm.actuator_desires.trigger_04.get():
            self.finish()

class TrackPinger(Task):
    """
    Locates the pinger and aligns the sub in the correct heading

    Should stop the sub so that hydrophones don't have interference from the motors.
    Adjusts the heading of the sub to point to the pinger.

    To assure the best readings:
        - Make sure we're normal to the pool surface
        - Make sure we're at least 3 feet away from the edges of the pool (TODO)
        - Try to slow down or stop

    Readings are median filtered. 

    Code to retrieve hydrophones from stdout:
    https://gitlab.com/CUAUV/hydrocode/blob/master/sub_code/heading.c
    """
    def on_first_run(self):
        self.logv("Beginning to track pinger")
        # can't be pitched or rolled for this!
        Pitch(0)()
        Roll(0)()
        self.velx = VelocityX()
        self.vely = VelocityY()
        self.velx(0)
        self.vely(0)
        self.heading = Heading()
        self.last_pinger_read_time = 0
        self.PINGER_READ_INTERVAL = 10
        self.PINGER_FOLLOW_TIME = 5

        self.FILTER_WINDOW_SIZE = 5
        self.MAX_READINGS = 100
        self.read_timer = None
        self.ping_confidence = None
        self.ping_heading = None
        self.pinger_readings = deque()

    def on_run(self):
        # TODO - ensure that we're not within 2-3 feet of the edges of the pool
        # should probably use positional controller for that - would probably need
        # to coordinate with obstacle avoidance mission
        if self.this_run_time - self.last_pinger_read_time > self.PINGER_READ_INTERVAL:
            self.logv("Resetting timer")
            # Not as important to not be moving during pinger measurements
            #self.velx(0)
            #self.vely(0)
            self.last_pinger_read_time = self.this_run_time
            self.read_timer = Timer(self.PINGER_READ_INTERVAL - self.PINGER_FOLLOW_TIME)
        if not self.read_timer.finished:
            self.logv("in read stage")
            Pitch(0)()
            Roll(0)()
            self.ping_confidence = shm.recovery_results.pinger_confidence.get()
            self.pinger_readings.append(shm.recovery_results.pinger_heading.get())
            if len(self.pinger_readings) > self.MAX_READINGS:
                self.pinger_readings.popleft()
            self.read_timer()
            self.logv("Collecting pinger readings: {}".format(self.pinger_readings[-1]))
        else:
            self.logv("Following pinger")
            # for now, it's not clear that confidence will be useful at all, so we should
            # ignore it; TODO consider incorporating in future if it appears to be useful
            #if self.ping_confidence > PINGER_CONFIDENCE_THRESH:
            filtered = medfilt(self.pinger_readings, self.FILTER_WINDOW_SIZE)
            # maybe take a heading average on top of this if the last value of
            # the median filter ends up being noisy
            self.ping_heading = filtered[-1]
            self.heading(self.ping_heading)
            self.velx(0.5)

            # might want to have a different search pattern to lock onto the
            # table visually; depends on how good pinger data is
            if shm.recovery_results.tower_downward_area.get() > TOWER_MIN_AREA:
                self.logi('Found table in downward camera')
                self.finish()
            if shm.recovery_results.tower_forward_area.get() > TOWER_FORWARD_MIN_AREA:
                self.logi('Found table in forward camera')
                self.finish()

    def on_finish(self):
        Zero()()
        self.logv("Done tracking pinger!")

class ForwardAlignTower(Task):
    """Aligns the sub with the tower using the forward camera

    Uses the forward camera to horizontally (maybe vertically as well) center
    the sub. Makes sure that the sub's downward camera will be able to see the
    tower.

    Precondition: The tower is either in the forward camera view or in the
    downward camera view
    """
    def on_first_run(self):
        Zero()()
        self.logv("Beginning to align with tower")
        self.align_tower = ForwardTarget((shm.recovery_results.tower_forward_center_x.get,
                    shm.recovery_results.tower_forward_center_y.get),
                    target=FORWARD_CAM_CENTER)
        self.forward = VelocityX(1)
        self.horizontal_align = PIDLoop(output_function=VelocityY())
        self.DOWNWARD_TOWER_AREA_THRESHOLD = 100

    def on_run(self):
        # TrackPinger() stopped because it saw the tower in the down cam, this task is not needed
        if shm.recovery_results.tower_downward_area.get() > self.DOWNWARD_TOWER_AREA_THRESHOLD:
            self.logv("{} not needed".format(self.__class__.__name__))
            self.finish()
            return
        if not self.align_tower.has_ever_finished:
            self.logv("Continuing to align with tower")
            if shm.recovery_results.tower_forward_area.get() > 0:
                self.align_tower()
            else:
                self.loge("ForwardAlignTower did not see a tower!")
                self.finish()
                return
        else:
            # move forward until downward camera sees tower
            self.forward()
            # Continually align with tower if it still in the field of view
            if shm.recovery_results.tower_forward_area.get() > 0:
                self.horizontal_align(input_value=shm.recovery_results.tower_forward_center_x.get(),
                        p=.01, i=0, d=0, target=FORWARD_CAM_CENTER[1],
                        deadband=1, negate=True)
            if shm.recovery_results.tower_downward_area.get() > TOWER_MIN_AREA:
                self.finish()
                return

    def on_finish(self):
        Zero()()
        self.logv("Positioned on top of tower!")

class FindDoubloon(Task):
    """Locates a doubloon"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spiral_task = Spiral()

    def on_run(self):
        self.logv("Running {}".format(self.__class__.__name__))
        if not self.spiral_task.finished:
            self.spiral_task()
            if DOUBLOONS[0]['probability'].get() > 0 or\
               DOUBLOONS[1]['probability'].get() > 0:
                self.finish()
        else:
            self.logv("finished finding doubloon")
            self.finish()

    def on_finish(self):
        Zero()()

class DiveTask(Task):
    """Dives and attempts to grab a doubloon"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.DIVE_DEPTH = 4.5
        self.target_task = DownwardTarget(target=DOWNWARD_CAM_CENTER)
        self.grab_task = Sequential(OpenGrabber(), Depth(self.DIVE_DEPTH, error=0.1),
                CloseGrabber())
        self.task = Sequential(self.grab_task, Depth(2, error=0.1))
        self.logv("Starting {}".format(self.__class__.__name__))

    def on_first_run(self, target):
        Zero()()

    def on_run(self, target):
        self.logv("Running {}".format(self.__class__.__name__))
        if not self.task.finished:
            #self.target_task(target)
            self.task()
        else:
            self.finish()

    def on_finish(self):
        self.logv('{} task finished in {} seconds!'.format(
            self.__class__.__name__,
            self.this_run_time - self.first_run_time))
        Zero()()

class GrabDoubloon(Task):
    """Detects a doubloon on the table, aligns with it, then grab it

    Identifies doubloon and goes down a depth so that the grabber picks up the
    doubloon. Retries until the downward camera does not see the doubloon

    NOTE: Doubloons returned by vision MUST be differentiated and ordered
    consistently, i.e. DOUBLOONS[0] should never be DOUBLOONS[1] at any moment
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.locator_task = FindDoubloon()
        self.target = None
        self.target_task = DownwardTarget(
                (lambda: self.target['x'].get(), lambda:
                    self.target['y'].get()), px=.01, py=.01, target=DOWNWARD_CAM_CENTER)
        self.grab_task = DiveTask()
        self.tries = 0
        self.MAX_TRIES = 10
        self.logv("Starting {}".format(self.__class__.__name__))

    def on_first_run(self):
        Zero()()

    def on_run(self):
        if self.tries > self.MAX_TRIES:
            self.logv("{} surpassed maximum number of retries!".format(
                self.__class__.__name__))
            self.finish()

        if self.target is None:
            target = None
            if DOUBLOONS[0]['probability'].get() > 0:
                target = DOUBLOONS[0]
            elif DOUBLOONS[1]['probability'].get() > 0:
                target = DOUBLOONS[1]
            if target is None:
                self.locator_task()
            else:
                self.logv("acquired target")
                self.target = target
        else:
            if not self.target_task.has_ever_finished:
                if self.target['probability'].get() > 0:
                    self.logv("Downward cam targeting doubloon at {},{}".format(self.target['x'].get(), self.target['y'].get()))
                    self.target_task()
                else:
                    self.target = None
            else:
                self.grab_task((self.target['x'].get, self.target['y'].get))
                if self.grab_task.finished:
                    if self.target['probability'].get() <= 0:
                        self.finish()
                    else:
                        self.tries += 1
                        self.grab_task = DiveTask()

    def on_finish(self):
        self.logv('{} task finished in {} seconds!'.format(
            self.__class__.__name__, self.this_run_time - self.first_run_time))
        Zero()()

class Surface(Task):
    """Surfaces for SURFACE_TIME (default = 3 seconds)

    The sub should be directly over the tower before surfacing to stay in octagon
    """

    def on_first_run(self, *args, **kwargs):
        maintain_align = DownwardTarget((shm.recovery_results.tower_downward_center_x.get,
                                         shm.recovery_results.tower_downward_center_y.get),
                                         target=DOWNWARD_CAM_CENTER, px=.01,
                                         py=.01)

        self.surface = Sequential(maintain_align, Zero(), Depth(-0.5, error=.1),
                Timer(SURFACE_TIME), Depth(1, error=.1))
        Zero()()

    def on_run(self, *args, **kwargs):
        self.logv("Running {}".format(self.__class__.__name__))
        if not self.surface.finished:
            self.surface()
        else:
            self.finish()

    def on_finish(self):
        self.logv('{} task finished in {} seconds!'.format(
            self.__class__.__name__, self.this_run_time - self.first_run_time))
        Zero()()

class SearchTable(Task):
    """
    Searches for the table using a outwards spiral movement.
    The location of the table should be recorded so that this only needs to be done once.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spiral_task = Spiral()

    def on_run(self):
        self.logv("Running {}".format(self.__class__.__name__))
        if not self.spiral_task.finished:
            self.spiral_task()
            if shm.recovery_results.table_area.get() > 0:
                # TODO record coordinates of table
                self.finish()
        else:
            self.finish()

    def finish(self):
        Zero()()

class FindTable(Task):
    """Starts with the sub surfaced, finds the table and goes towards it
    """
    def on_first_run(self, *args, **kwargs):
        self.search_table = SearchTable()
        self.mark_target_task = DownwardTarget(target=DOWNWARD_CAM_CENTER, px=0.01, py=0.01)

    def on_run(self, *args, **kwargs):
        first_mark_x = shm.recovery_results.first_mark_x.get()
        first_mark_y = shm.recovery_results.first_mark_y.get()
        first_mark_score = shm.recovery_results.first_mark_score.get()
        second_mark_x = shm.recovery_results.second_mark_x.get()
        second_mark_y = shm.recovery_results.second_mark_y.get()
        second_mark_score = shm.recovery_results.second_mark_score.get()
        if first_mark_score > MIN_MARKER_SCORE and second_mark_score > MIN_MARKER_SCORE:
            avg_x = (first_mark_x + second_mark_x) / 2
            avg_y = (first_mark_y + second_mark_y) / 2
            self.mark_target_task((avg_x, avg_y))
        elif first_mark_score > MIN_MARKER_SCORE:
            self.logi("FindTable targeting {},{}".format(first_mark_x, first_mark_y))
            self.mark_target_task((first_mark_x, first_mark_y))
        elif second_mark_score > MIN_MARKER_SCORE:
            self.logi("FindTable targeting {},{}".format(second_mark_x, second_mark_y))
            self.mark_target_task((second_mark_x, second_mark_y))
        else:
            self.search_table()
        if self.mark_target_task.finished:
            self.finish()

    def on_finish(self):
        Zero()()

class DownwardAlignTable(Task):
    """Aligns with one of the x's on the table

    The x closer to the top left of the camera image should be the first x
    returned from the vision system.
    """

    def on_first_run(self, *args, **kwargs):
        self.mark_targeting = NoOp()
        self.target_score = None
        Zero()()

    def on_run(self, locator_task, *args, **kwargs):
        self.logv("Running {}".format(self.__class__.__name__))
        if self.target_score is None or self.target_score.get() <= 0:
            doubloon_1_p = DOUBLOONS[0]['probability'].get
            doubloon_1_x = DOUBLOONS[0]['x'].get
            doubloon_1_y = DOUBLOONS[0]['y'].get
            doubloon_2_p = DOUBLOONS[1]['probability'].get
            doubloon_2_x = DOUBLOONS[1]['x'].get
            doubloon_2_y = DOUBLOONS[1]['y'].get
            doubloons = [(doubloon_1_p, doubloon_1_x, doubloon_1_y),
                        (doubloon_2_p, doubloon_2_x, doubloon_2_y)]
            if doubloons[0][0]() > 0:
                self.logv("Doubloon found at ({}, {})".format(doubloons[0][1](),
                    doubloons[0][2]()))
            if doubloons[1][0]() > 0:
                self.logv("Doubloon found at ({}, {})".format(doubloons[1][1](),
                    doubloons[1][2]()))

            first_mark_x = shm.recovery_results.first_mark_x.get
            first_mark_y = shm.recovery_results.first_mark_y.get
            self.first_mark_target = DownwardTarget((first_mark_x, first_mark_y),
                    target=DOWNWARD_CAM_CENTER, px=0.01, py=0.01)
            first_mark_score = shm.recovery_results.first_mark_score.get()
            if first_mark_score > MIN_MARKER_SCORE:
                self.logi('Found first marker at (%d, %d)' % (first_mark_x(),
                    first_mark_y()))
            # reduce the score of aligning with the first mark if there is a doubloon near it already
            if self.is_close((first_mark_x, first_mark_y), doubloons, 20):
                first_mark_score /= 4

            second_mark_x = shm.recovery_results.second_mark_x.get
            second_mark_y = shm.recovery_results.second_mark_y.get
            second_mark_score = shm.recovery_results.second_mark_score.get()
            self.second_mark_target = DownwardTarget((second_mark_x, second_mark_y),
                    target=DOWNWARD_CAM_CENTER)
            if second_mark_score > MIN_MARKER_SCORE:
                self.logi('Found second marker at (%d, %d)' % (second_mark_x(),
                    second_mark_y()))
            # Reduce the score of aligning with the second mark if there is a doubloon near it already
            if self.is_close((second_mark_x, second_mark_y), doubloons, 20):
                second_mark_score /= 4

            if first_mark_score == second_mark_score == 0:
                locator_task()
            else:
                # higher scores means there is no doubloon near the mark, so we want to align to it
                if first_mark_score >= second_mark_score:
                    self.mark_targeting = self.first_mark_target
                    self.target_score = shm.recovery_results.first_mark_score
                    self.logi('Targeting first marker at {},{}'.format(first_mark_x(), first_mark_y()))
                else:
                    self.mark_targeting = self.second_mark_target
                    self.target_score = shm.recovery_results.second_mark_score
                    self.logi('Targeting second marker at {},{}'.format(second_mark_x(), second_mark_y()))
        else:
            if not self.mark_targeting.has_ever_finished:
                self.logi('First mark: {},{}'.format(shm.recovery_results.first_mark_x.get(), shm.recovery_results.first_mark_x.get()))
                self.logi('Second mark: {},{}'.format(shm.recovery_results.second_mark_x.get(), shm.recovery_results.second_mark_y.get()))
                self.mark_targeting()
            else:
                self.finish()

    def is_close(self, goal, doubloons, tolerance):
        """
        Calculates if there are any doubloons that are close to the given goal
        :param goal: tuple with x,y coordinates of the goal mark
        :param doubloons: any doubloons to check distance of
        :param tolerance: distance at which to mark objects as close
        """
        for obj in doubloons:
            if obj[0]() > 0:
                if ((goal[0]() - obj[1]()) ** 2 + (goal[1]() - obj[2]()) ** 2) < tolerance ** 2:
                    return True
        return False

    def on_finish(self):
        self.logv("Finished {}".format(self.__class__.__name__))
        Zero()()

class DropDoubloon(Task):
    """Drops doubloon and waits to confirm that the doubloon is on the x. Otherwise
    retries the drop/realign the doubloon
    """
    def on_first_run(self, *args, **kwargs):
        self.first_mark_ok = self.second_mark_ok = False
        self.check_mark_status()
        #doubloon_1_p = DOUBLOONS[0]['probability'].get()
        #doubloon_1_x = DOUBLOONS[0]['x'].get()
        #doubloon_1_y = DOUBLOONS[0]['y'].get()
        #doubloon_2_p = DOUBLOONS[1]['probability'].get()
        #doubloon_2_x = DOUBLOONS[1]['x'].get()
        #doubloon_2_y = DOUBLOONS[1]['y'].get()
        #doubloons = [(doubloon_1_p, doubloon_1_x, doubloon_1_y),
        #            (doubloon_2_p, doubloon_2_x, doubloon_2_y)]
        #print(doubloons)
        self.drop_task_creator = lambda: Sequential(OpenGrabber(), Timer(3), CloseGrabber()) 
        self.drop = self.drop_task_creator()
        self.grab_task = GrabDoubloon()
        Zero()()

    def on_run(self, *args, **kwargs):
        self.logv("Running {}".format(self.__class__.__name__))
        if not self.drop.has_ever_finished:
            self.logv("Dropping doubloon")
            self.drop()
        else:
            prev_first_mark_ok = self.first_mark_ok
            prev_second_mark_ok = self.second_mark_ok
            self.check_mark_status()
            #doubloon_1_p = DOUBLOONS[0]['probability'].get()
            #doubloon_1_x = DOUBLOONS[0]['x'].get()
            #doubloon_1_y = DOUBLOONS[0]['y'].get()
            #doubloon_2_p = DOUBLOONS[1]['probability'].get()
            #doubloon_2_x = DOUBLOONS[1]['x'].get()
            #doubloon_2_y = DOUBLOONS[1]['y'].get()
            #doubloons = [(doubloon_1_p, doubloon_1_x, doubloon_1_y),
            #         (doubloon_2_p, doubloon_2_x, doubloon_2_y)]
            #print(doubloons)
            # status has changed for one of the markers, so we're done
            if not self.first_mark_ok and not self.second_mark_ok:
                self.logv("No marks found!")
                self.finish()
            elif prev_first_mark_ok and not self.first_mark_ok:
                self.logv("Dropped on first mark")
                self.finish()
            elif prev_second_mark_ok and not self.second_mark_ok:
                self.logv("Dropped on second mark")
                self.finish()
            else:
                self.grab_task()
                if self.grab_task.finished:
                    self.drop = self.drop_task_creator()

    def check_mark_status(self):
        doubloon_1_p = DOUBLOONS[0]['probability'].get()
        doubloon_1_x = DOUBLOONS[0]['x'].get()
        doubloon_1_y = DOUBLOONS[0]['y'].get()
        doubloon_2_p = DOUBLOONS[1]['probability'].get()
        doubloon_2_x = DOUBLOONS[1]['x'].get()
        doubloon_2_y = DOUBLOONS[1]['y'].get()
        doubloons = [(doubloon_1_p, doubloon_1_x, doubloon_1_y),
                     (doubloon_2_p, doubloon_2_x, doubloon_2_y)]

        first_mark_score = shm.recovery_results.first_mark_score.get()
        first_mark_x = shm.recovery_results.first_mark_x.get()
        first_mark_y = shm.recovery_results.first_mark_y.get()
        self.first_mark_ok = not self.is_close((first_mark_score, first_mark_x, first_mark_y), doubloons, 20)
        second_mark_score = shm.recovery_results.second_mark_score.get()
        second_mark_x = shm.recovery_results.second_mark_x.get()
        second_mark_y = shm.recovery_results.second_mark_y.get()
        self.second_mark_ok = not self.is_close((second_mark_score, second_mark_x, second_mark_y), doubloons, 20)

    def is_close(self, goal, doubloons, tolerance):
        """
        Calculates if there are any doubloons that are close to the given goal
        :param goal: tuple with x,y coordinates of the goal mark
        :param doubloons: any doubloons to check distance of
        :param tolerance: distance at which to mark objects as close
        """
        for obj in doubloons:
            if obj[0] > 0 and goal[0] > 0:
                if ((goal[1] - obj[1]) ** 2 + (goal[2] - obj[2]) ** 2) < tolerance ** 2:
                    return True
        return False

    def on_finish(self):
        Zero()()

#mission =  lambda: Sequential(TrackPinger(), ForwardAlignTower(),
#        GrabDoubloon(), Surface(), FindTable(), DownwardAlignTable(FindTable()), DropDoubloon())
mission =  lambda: Sequential(GrabDoubloon(), Surface(), FindTable(),
                              DownwardAlignTable(FindTable()), DropDoubloon())
