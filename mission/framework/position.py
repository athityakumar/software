import shm

from auv_python_helpers.math_utils import rotate
from mission.framework.combinators import Concurrent
from mission.framework.movement import RelativeToInitialPositionN, RelativeToInitialPositionE
from mission.framework.task import Task
from shm import kalman

class MoveAngle(Task):
    def on_first_run(self, angle, distance, *args, **kwargs):
        self.initial_position_controls_setting = shm.navigation_settings.position_controls.get()
        shm.navigation_settings.position_controls.set(1) # change to positional controls at start

        delta_north, delta_east = rotate(rotate((distance, 0), angle),
                                         kalman.heading.get())

        n_position = RelativeToInitialPositionN(offset=delta_north, error=.01)
        e_position = RelativeToInitialPositionE(offset=delta_east, error=.01)
        self.motion = Concurrent(n_position, e_position, finite=False)

    def on_run(self, *args, **kwargs):
        self.motion()

        if self.motion.has_ever_finished:
            self.finish()

    def on_finish(self, *args, **kwargs):
        shm.navigation_settings.position_controls.set(self.initial_position_controls_setting)

def MoveX(distance):
    return MoveAngle(0, distance)

def MoveY(distance):
    return MoveAngle(90, distance)
