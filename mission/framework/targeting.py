from control.pid import DynamicPID
from mission.framework.helpers import call_if_function, within_deadband
from mission.framework.movement import VelocityY, VelocityX, RelativeToCurrentDepth, RelativeToCurrentHeading
from mission.framework.task import Task


# TODO: Documentation!
class PIDLoop(Task):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.pid = None  # type: DynamicPID

    def on_first_run(self, input_value, *args, **kwargs):
        self.pid = DynamicPID()

    def on_run(self, input_value, output_function, target=0, modulo_error=False, deadband=1, p=1, d=0, i=0,
               negate=False, *args, **kwargs):
        # TODO: minimum_output too?
        input_value = call_if_function(input_value)
        target = call_if_function(target)

        output = self.pid.tick(value=input_value, desired=target, p=p, d=d, i=i)
        output_function(-output if negate else output)

        if within_deadband(input_value, target, deadband=deadband, use_mod_error=modulo_error):
            # TODO: Should this zero on finish? Or set to I term?
            self.finish()


class ForwardTarget(Task):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.pid_loop_x = None  # type: PIDLoop
        self.pid_loop_y = None  # type: PIDLoop

    def on_first_run(self, *args, **kwargs):
        self.pid_loop_x = PIDLoop(output_function=VelocityY())
        self.pid_loop_y = PIDLoop(output_function=RelativeToCurrentDepth())

    # TODO: Default target should be center of forward camera image
    def on_run(self, point, deadband=(15, 15), px=.001, ix=0, dx=0, py=.001, iy=0, dy=0, target=(510, 510)):
        point = call_if_function(point)
        self.logd('Running ForwardTarget on ({0}, {1}).'.format(point[0], point[1]))
        self.pid_loop_x(input_value=point[0], p=px, i=ix, d=dx, target=target[0], deadband=deadband[0], negate=True)
        self.pid_loop_y(input_value=point[1], p=py, i=iy, d=dy, target=target[1], deadband=deadband[1], negate=True)

        if self.pid_loop_x.finished and self.pid_loop_y.finished:
            # TODO: Should the output be zeroed on finish?1
            self.finish()


class DownwardTarget(Task):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.pid_loop_x = None  # type: PIDLoop
        self.pid_loop_y = None  # type: PIDLoop

    def on_first_run(self, *args, **kwargs):
        # x-axis on the camera corresponds to sway axis for the sub
        self.pid_loop_x = PIDLoop(output_function=VelocityY(), negate=True)
        self.pid_loop_y = PIDLoop(output_function=VelocityX(), negate=False)

    # TODO: Default target should be center of downward camera image-- Should be dynamic?
    def on_run(self, point, deadband=(15, 15), px=.0005, ix=0, dx=0, py=.001, iy=0, dy=0, target=(512, 384), min_out=None):
        point = call_if_function(point)
        self.pid_loop_x(input_value=point[0], p=px, i=ix, d=dx, target=target[0], deadband=deadband[0], min_out=min_out)
        self.pid_loop_y(input_value=point[1], p=py, i=iy, d=dy, target=target[1], deadband=deadband[1], min_out=min_out)

        if self.pid_loop_x.finished and self.pid_loop_y.finished:
            # TODO: Should the output be zeroed on finish?1
            self.finish()


class HeadingTarget(Task):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.pid_loop_x = None  # type: PIDLoop
        self.pid_loop_y = None  # type: PIDLoop

    def on_first_run(self, *args, **kwargs):
        self.pid_loop_y = PIDLoop(output_function=RelativeToCurrentDepth())
        self.pid_loop_x = PIDLoop(output_function=RelativeToCurrentHeading())

    # TODO: Default target should be center of forward camera image
    def on_run(self, point, deadband=(15, 15), px=.01, ix=0, dx=0, py=.001, iy=0, dy=0, target=(510, 510), modulo_error=False):
        point = call_if_function(point)
        self.logd('Running HeadingTarget on ({0}, {1}).'.format(point[0], point[1]))
        self.pid_loop_x(input_value=point[0], p=px, i=ix, d=dx, target=target[0], deadband=deadband[0], negate=True)
        self.pid_loop_y(input_value=point[1], p=py, i=iy, d=dy, target=target[1], deadband=deadband[1], negate=True)

        if self.pid_loop_x.finished and self.pid_loop_y.finished:
            # TODO: Should the output be zeroed on finish?1
            self.finish()


class DownwardAlign(Task):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.pid_loop_heading = None  # type: PIDLoop

    def on_first_run(self, *args, **kwargs):
        self.pid_loop_heading = PIDLoop(output_function=RelativeToCurrentHeading(), modulo_error=True)

    def on_run(self, angle, deadband=3, p=.001, i=0, d=0, target=0, modulo_error=True):
        angle = call_if_function(angle)
        self.pid_loop_heading(input_value=angle, p=p, i=i, d=d, target=target, deadband=deadband, negate=True)

        if self.pid_loop_heading.finished:
            self.finish()
