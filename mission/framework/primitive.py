from mission.framework.task import Task
from mission.framework.movement import Heading, Pitch, Roll, \
                                       Depth, VelocityX, VelocityY, \
                                       PositionN, PositionE
import shm

class NoOp(Task):
    """Do nothing - useful to use as a default argument instead of None. Similar to the Empty of an Option type."""

    def on_run(self, *args, **kwargs):
        pass

class FunctionTask(Task):
    """Runs a function and finishes"""

    def on_run(self, func, *args, **kwargs):
        func()
        self.finish()

class Zero(Task):
    """Zeroes desires - Sets velocities to zero and maintains current orientation of the submarine"""
    def on_run(self):
        Heading(shm.kalman.heading.get())()
        Depth(shm.kalman.depth.get())()
        PositionN(shm.kalman.north.get())()
        PositionE(shm.kalman.east.get())()
        Pitch(shm.kalman.pitch.get())()
        Roll(shm.kalman.roll.get())()
        VelocityX(0)()
        VelocityY(0)()
        self.finish()

class ZeroIncludingPitchRoll(Task):
    """Zeroes desires - Sets velocities to zero and sets pitch and roll to zero; Maintains heading and depth"""
    def on_run(self):
        Heading(shm.kalman.heading.get())()
        Depth(shm.kalman.depth.get())()
        PositionN(shm.kalman.north.get())()
        PositionE(shm.kalman.east.get())()
        Pitch(0)()
        Roll(0)()
        VelocityX(0)()
        VelocityY(0)()
        self.finish()

