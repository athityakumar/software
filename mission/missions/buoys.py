import shm
from mission.framework.task import Task
from mission.framework.combinators import Sequential, Concurrent
from mission.framework.movement import Heading, RelativeToInitialHeading, VelocityX, VelocityY, Depth, RelativeToInitialDepth
from mission.framework.targeting import ForwardTarget
from mission.framework.timing import Timer
from mission.framework.primitive import NoOp, Zero
from mission.framework.helpers import call_if_function
from shm import red_buoy_results
from shm import green_buoy_results
from shm import yellow_buoy_results
from functools import reduce

CAM_CENTER = (shm.camera.forward_width.get() / 2,
              shm.camera.forward_height.get() / 2)

class HeadingRestore(Task):
    """
    Saves the current heading and restores it at a later time
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store the start heading of the sub
        self.start_heading = shm.kalman.heading.get()
        self.heading_task = Heading(self.start_heading, error=1)

    def on_first_run(self):
        self.logv("Starting {} task".format(self.__class__.__name__))

    def on_run(self):
        # Restore the sub's heading to the stored one
        self.logv("Running {}".format(self.__class__.__name__))
        if not self.heading_task.finished:
            self.heading_task()
        else:
            self.finish()

    def on_finish(self):
        self.logv('{} task finished in {} seconds!'.format(
            self.__class__.__name__,
            self.this_run_time - self.first_run_time))

class LocateBuoyBySpinning(Task):
    """
    Locates a buoy by spinning.
    """
    def __init__(self, validator, *args, **kwargs):
        """
        validator - a function that returns True when a buoy is found and
            False otherwise.
        """
        super().__init__(*args, **kwargs)
        self.logv("Starting {} task".format(self.__class__.__name__))
        self.validator = validator
        self.start_heading = shm.kalman.heading.get()
        self.subtasks = [Sequential(RelativeToInitialHeading(60, error=0.1), Timer(1)) for i in range(6)]
        self.spin_task = Sequential(subtasks=self.subtasks)
        self.TIMEOUT = 20

    def on_run(self):
        # Perform a search for the buoy
        # If the validator() is True, then finish
        if self.this_run_time - self.first_run_time > self.TIMEOUT:
            self.finish()
            self.loge("{} timed out!".format(self.__class__.__name__))
            return
        self.logv("Running {}".format(self.__class__.__name__))
        self.logv("Spin step: {}/{}".format(
            reduce(lambda acc, x: acc + 1 if x.finished else acc, self.subtasks, 1),
            len(self.subtasks)))
        self.spin_task()
        if self.validator() or self.spin_task.finished:
            self.finish()

    def on_finish(self):
        self.logv('{} task finished in {} seconds!'.format(
            self.__class__.__name__,
            self.this_run_time - self.first_run_time))
        Zero()()

class LocateBuoySurge(Task):
    """
    Locates a buoy in front of or behind the current position of the submarine.
    """
    def __init__(self, validator, *args, **kwargs):
        """
        validator - a function that returns True when a buoy is found and False
            otherwise.
        """
        super().__init__(*args, **kwargs)
        self.logv("Starting {} task".format(self.__class__.__name__))
        self.validator = validator
        self.surge_task = VelocityX()
        self.TIMEOUT = 5

    def on_run(self, forward=True):
        """
        forward - determines whether the submarine should move forward or
            backward during its search
        """
        # Perform a search for the buoy
        # If the validator() is True, then finish
        if self.this_run_time - self.first_run_time > self.TIMEOUT:
            self.finish()
            self.loge("{} timed out!".format(self.__class__.__name__))
            return
        self.logv("Running {}".format(self.__class__.__name__))
        velocity = 1 if forward else -1
        self.surge_task(velocity)
        if self.validator():
            self.finish()

    def on_finish(self):
        self.surge_task(0)
        self.logv('{} task finished in {} seconds!'.format(
            self.__class__.__name__,
            self.this_run_time - self.first_run_time))

class LocateBuoy(Task):
    """
    Locates a buoy using LocateBuoyBySpinning and LocateBuoySurge
    """
    def __init__(self, validator, forward=True, *args, **kwargs):
        """
        validator - a function that returns True when a buoy is found and False
            otherwise.
        forward - determines whether the submarine should move forward or
            backward during its search
        """
        super().__init__(*args, **kwargs)
        self.validator = validator
        self.task_classes = [lambda: LocateBuoyBySpinning(validator),
                             lambda: LocateBuoySurge(validator, forward)]
        self.tasks = []
        self.task_index = 0
        self.TIMEOUT = 60

    def on_first_run(self):
        self.logv("Starting {} task".format(self.__class__.__name__))
        self.tasks = [x() for x in self.task_classes]

    def on_run(self):
        if self.this_run_time - self.first_run_time > self.TIMEOUT:
            self.finish()
            self.loge("{} timed out!".format(self.__class__.__name__))
            return
        self.logv("Running {}".format(self.__class__.__name__))
        self.tasks[self.task_index]()
        if self.tasks[self.task_index].finished:
            if self.validator():
                self.finish()
            else:
                # Reinstantiate subtask, because validator is not true
                self.tasks[self.task_index] = self.task_classes[self.task_index]()
                self.task_index = (self.task_index + 1) % len(self.tasks)

    def on_finish(self):
        self.logv('{} task finished in {} seconds!'.format(
            self.__class__.__name__,
            self.this_run_time - self.first_run_time))

class AlignTarget(Task):
    """
    Aligns using ForwardTarget on a target coordinate, while ensuring that the
    target is visible
    """
    def __init__(self, validator, locator_task, target_coords, forward_target_p=0.001, *args, **kwargs):
        """
        validator - a function that returns True when the target is visible and False
            otherwise.
        locator_task - a task that locates the target
        target_coords - the coordinates of the target with which to align
        """
        super().__init__(*args, **kwargs)
        self.validator = validator
        self.locator_task = locator_task
        self.target_task = ForwardTarget(target_coords, target=CAM_CENTER,
                px=forward_target_p, py=forward_target_p)
        self.TIMEOUT = 60

    def on_first_run(self):
        self.logv("Starting {} task".format(self.__class__.__name__))

    def on_run(self):
        if self.this_run_time - self.first_run_time > self.TIMEOUT:
            self.finish()
            self.loge("{} timed out!".format(self.__class__.__name__))
            return
        self.logv("Running {}".format(self.__class__.__name__))
        if self.validator():
            self.target_task()
        else:
            self.locator_task()
        if self.target_task.finished:
            self.finish()

    def on_finish(self):
        self.logv('{} task finished in {} seconds!'.format(
            self.__class__.__name__,
            self.this_run_time - self.first_run_time))

class RamTarget(Task):
    """
    Moves forward until collision with an object at a given coordinate in the
    yz-plane.
    """
    def __init__(self, target_validator, collision_validator, locator_task, concurrent_task=NoOp(), *args, **kwargs):
        """
        target_validator - a function that returns True when a target is
            visible and False otherwise.
        collision_validator - a function that returns True when a collision is
            made and False otherwise.
        concurrent_task - an optional argument for a task to run while moving
            forward to ram the target. It may be used to continually align with
            the target while ramming it.
        """
        super().__init__(*args, **kwargs)
        self.logv("Starting {} task".format(self.__class__.__name__))
        self.target_validator = target_validator
        self.collision_validator = collision_validator
        self.ram_task = VelocityX(1.0)
        self.locator_task = locator_task
        self.concurrent_task = concurrent_task
        self.TIMEOUT = 25

    def on_run(self):
        # Move forward for ramming target
        # If the validator function returns True, then finish the task
        if self.this_run_time - self.first_run_time > self.TIMEOUT:
            self.finish()
            self.loge("{} timed out!".format(self.__class__.__name__))
            return
        self.logv("Running {}".format(self.__class__.__name__))
        if self.target_validator():
            self.ram_task()
        else:
            self.locator_task()
        if self.concurrent_task:
            self.concurrent_task()
        if self.collision_validator():
            self.finish()

    def on_finish(self):
        self.logv('{} task finished in {} seconds!'.format(
            self.__class__.__name__,
            self.this_run_time - self.first_run_time))
        Zero()()

class BuoyRam(Task):
    """
    Locates and rams a buoy.

    Precondition: The target buoy is located at a position (x-coordinate) in
    front of the position of the submarine.

    Postcondition: The submarine will have rammed the buoy and will be
    positioned at the same depth as determined by the target coordinates. The
    original heading of the submarine prior to the collision will be maintained
    after the collision is complete.
    """
    def __init__(self, location_validator, target_coordinates,
            collision_validator, ram_concurrent_task=NoOp(), *args, **kwargs):
        """
        location_validator - a function that returns True when the target has
            been found and False otherwise
        target_coordinates - a tuple representing the coordinates of the target
            in the xz-plane
        collision_validator - a function that returns True when there has been a
            collision with the target and False otherwise.
        ram_concurrent_task - an optional task to run concurrently when ramming
            the target
        """
        super().__init__(*args, **kwargs)
        self.logv("Starting {} task".format(self.__class__.__name__))
        self.location_validator = location_validator
        self.target_coordinates = target_coordinates
        self.collision_validator = collision_validator
        self.ram_concurrent_task = ram_concurrent_task
        self.locator_task = LocateBuoy(self.location_validator)
        self.align_task = AlignTarget(self.location_validator,
                self.locator_task, self.target_coordinates)
        self.ram_task = RamTarget(self.location_validator,
                self.collision_validator, self.locator_task,
                self.ram_concurrent_task)
        self.heading_task = HeadingRestore()
        self.tasks = Sequential(Zero(), self.locator_task, self.align_task,
                self.ram_task, self.heading_task)
        self.TIMEOUT = 60

    def on_run(self):
        # Locate the buoy
        # Align with the buoy
        # Ram the buoy
        # Fulfill postcondition
        if self.this_run_time - self.first_run_time > self.TIMEOUT:
            self.finish()
            self.loge("{} timed out!".format(self.__class__.__name__))
            return
        self.tasks()
        if self.tasks.finished:
            self.finish()

    def on_finish(self):
        self.logv('{} task finished in {} seconds!'.format(
            self.__class__.__name__,
            self.this_run_time - self.first_run_time))

class Buoy(Task):
    """
    Wrapper around the BuoyRam class that will specifically ram a red or green
    buoy
    """
    def __init__(self, buoy, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Instantiate the BuoyRam task
        self.buoy = buoy
        self.align_task = AlignTarget(self.location_validator,
                LocateBuoy(self.location_validator),
                (self.buoy.center_x.get, self.buoy.center_y.get))
        self.ram_task = BuoyRam(self.location_validator,
                (self.buoy.center_x.get, self.buoy.center_y.get),
                self.collision_validator, self.align_task)
        self.seen_frames = 0
        self.SEEN_FRAMES_THRESHOLD = 5
        self.last_percent_frame = 0
        self.PERCENT_FRAME_THRESHOLD = 50
        self.PERCENT_FRAME_DELTA_THRESHOLD = 10
        self.TIMEOUT = 100

    def on_first_run(self):
        self.logv("Starting {} task".format(self.__class__.__name__))

    def on_run(self):
        # Perform BuoyRam task
        if self.this_run_time - self.first_run_time > self.TIMEOUT:
            self.finish()
            self.loge("Buoy ({}) timed out!".format(self.buoy))
            return
        self.ram_task()
        if self.ram_task.finished:
            self.finish()

    def on_finish(self):
        self.logv("Buoy ({}) task finished in {} seconds!".format(
            self.buoy, self.this_run_time - self.first_run_time))
        Zero()()

    def location_validator(self):
        # TODO even more robust location validator
        if self.buoy.probability.get() != 0:
            self.seen_frames += 1
        else:
            self.seen_frames = 0
        return self.seen_frames >= self.SEEN_FRAMES_THRESHOLD

    def collision_validator(self):
        # TODO even more robust collision validator
        current = self.buoy.percent_frame.get()
        if current >= self.PERCENT_FRAME_THRESHOLD:
            if abs(self.last_percent_frame - current) <= self.PERCENT_FRAME_DELTA_THRESHOLD:
                return True
            self.last_percent_frame = current
        return False

class ScuttleYellowBuoy(Task):
    """
    Locates and scuttles a yellow buoy by dragging it down.

    Precondition: The yellow buoy is located at a position in front of the
    position of the submarine.

    Postcondition: The submarine will have dragged down the yellow buoy, and the
    submarine will be positioned above the yellow buoy.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.locator_task = LocateBuoy(self.location_validator)
        self.align_task = AlignTarget(self.location_validator,
                self.locator_task, (yellow_buoy_results.top_x.get,
            yellow_buoy_results.top_y.get), forward_target_p=0.005)
        self.concurrent_align_task = AlignTarget(self.location_validator,
                self.locator_task, (yellow_buoy_results.top_x.get,
            yellow_buoy_results.top_y.get), forward_target_p=0.005)
        self.ram_task = RamTarget(self.location_validator,
                self.collision_validator, self.locator_task,
                self.concurrent_align_task)
        self.velx_task = VelocityX(1, error=0.5)
        self.depth_task = Concurrent(RelativeToInitialDepth(1.5, error=0.01),
                self.velx_task, finite=False)
        self.tasks = Sequential(self.locator_task, self.align_task,
                self.ram_task, self.depth_task)
        self.seen_frames = 0
        self.SEEN_FRAMES_THRESHOLD = 5
        self.last_percent_frame = 0
        self.PERCENT_FRAME_THRESHOLD = 40
        self.PERCENT_FRAME_DELTA_THRESHOLD = 10
        self.TIMEOUT = 100

    def on_first_run(self):
        self.logv("Starting {} task".format(self.__class__.__name__))

    def on_run(self):
        # Locate the yellow buoy
        # Align with the yellow buoy
        # Move forward until collision with the buoy (using RamTarget)
        # Descend to drag buoy downwards
        if self.this_run_time - self.first_run_time > self.TIMEOUT:
            self.finish()
            self.loge("{} timed out!".format(self.__class__.__name__))
            return
        self.tasks()
        if self.tasks.finished:
            self.finish()

    def on_finish(self):
        self.logv('{} task finished in {} seconds!'.format(
            self.__class__.__name__,
            self.this_run_time - self.first_run_time))
        Zero()()

    def location_validator(self):
        # TODO even more robust location validator
        if yellow_buoy_results.probability.get() != 0:
            self.seen_frames += 1
        else:
            self.seen_frames = 0
        return self.seen_frames >= self.SEEN_FRAMES_THRESHOLD

    def collision_validator(self):
        # TODO even more robust collision validator
        current = yellow_buoy_results.percent_frame.get()
        if current >= self.PERCENT_FRAME_THRESHOLD:
            if yellow_buoy_results.center_y.get() > (shm.camera.forward_height.get() - 10) \
               and abs(self.last_percent_frame - current) <= self.PERCENT_FRAME_DELTA_THRESHOLD:
                return True
            self.last_percent_frame = current
        return False

red = lambda: Buoy(red_buoy_results)
green = lambda: Buoy(green_buoy_results)
ram = lambda: Sequential(Buoy(red_buoy_results), Sequential(VelocityX(-1,
    error=0.5), Timer(2)), Buoy(green_buoy_results))
scuttle = lambda: ScuttleYellowBuoy()
full = lambda: Sequential(ram(), Sequential(VelocityX(-1, error=0.5), Timer(2)),
        scuttle())
