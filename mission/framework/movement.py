from functools import partial

from mission.framework.helpers import call_if_function, within_deadband
from mission.framework.task import Task
from shm import kalman
from shm import navigation_desires as desires

class Setter(Task):
    """Generic setter which also checks the end condition"""

    def on_run(self, target, desire_setter, current, error=-1, modulo_error=False, *args, **kwargs):
        """
        Note: This does not 0 the desire when completed.

        :param target: A Number or function that when called with no arguments returns a Number that represents the
        value to be targeted.
        :param desire_setter: A SHM variable (object with a set method) that will be called with a single argument to target.
        :param current: A Number or function that when called with no arguments returns the current value as a Number.
        :param error: A Number representing the allowed error before a wrapper is finished.
        :param modulo_error: a Boolean that is true only if the error calculated should be with respect to modulo 360.
        """

        target, current = call_if_function(target), call_if_function(current)

        if within_deadband(target, current, error, use_mod_error=modulo_error):
            self.finish()
        else:
            desire_setter(target)


class RelativeToInitialSetter(Task):
    """Generic setter relative to initial value"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.initial_value = None

    def on_first_run(self, *args, **kwargs):
        self.initial_value = call_if_function(kwargs['current'])

    def on_run(self, offset, desire_setter, current, error=-1, modulo_error=False, *args, **kwargs):
        """
        Note: This does not 0 the desire when completed.

        :param offset: A Number or function that when called with no arguments returns a Number that represents the
        value to be targeted. This offset will be added to the current value on the first run.
        :param desire_setter: A SHM variable (object with a set method) that will be called with a single argument to target.
        :param current: A Number or function that when called with no arguments returns the current value as a Number.
        :param error: A Number representing the allowed error before a wrapper is finished.
        :param modulo_error: a Boolean that is true only if the error calculated should be with respect to modulo 360.
        """

        offset, current = call_if_function(offset), call_if_function(current)

        if within_deadband(self.initial_value + offset, current, error, use_mod_error=modulo_error):
            self.finish()
        else:
            desire_setter(self.initial_value + offset)


class RelativeToCurrentSetter(Task):
    """Generic setter relative to current value"""

    def on_run(self, offset, desire_setter, current, error=-1, modulo_error=False, *args, **kwargs):
        """
        Note: This does not 0 the desire when completed.

        :param offset: A Number or function that when called with no arguments returns a Number that represents the
        value to be targeted. This offset will be added to the current value.
        :param desire_setter: A SHM variable (object with a set method) that will be called with a single argument to
        target.
        :param current: A Number or function that when called with no arguments returns the current value as a Number.
        :param error: A Number representing the allowed error before a wrapper is finished.
        :param modulo_error: a Boolean that is true only if the error calculated should be with respect to modulo 360.
        """

        offset, current = call_if_function(offset), call_if_function(current)

        if within_deadband(current + offset, current, error, use_mod_error=modulo_error):
            self.finish()
        else:
            desire_setter(current + offset)


class VelocitySetter(Task):
    """Generic setter that simulates velocity controller using a positional controller"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.relative_to_current_setter = None

    def on_first_run(self, *args, **kwargs):
        self.relative_to_current_setter = RelativeToCurrentSetter()

    def on_run(self, velocity, desire_setter, current, target=None, error=-1, modulo_error=False, *args, **kwargs):
        """
        Note: This does not 0 the desire when completed.

        :param velocity: A Number or function that when called with no arguments returns a Number that represents the
        value to be targeted. This target will be multiplied with the time in seconds from the last call and be added to
        the current value.
        :param desire_setter: A SHM variable (object with a set method) that will be called with a single argument to
        target.
        :param current: A Number or function that when called with no arguments returns the current value as a Number.
        :param target: A Number (or function) that represents the target velocity (units/second).
        :param error: A Number representing the allowed error before a wrapper is finished.
        :param modulo_error: a Boolean that is true only if the error calculated should be with respect to modulo 360.
        """

        velocity, current, target = call_if_function(velocity), call_if_function(current), call_if_function(target)

        target_for_velocity = velocity * (self.this_run_time - self.last_run_time)

        self.relative_to_current_setter.on_run(offset=target_for_velocity, desire_setter=desire_setter, current=current,
                                               error=error, modulo_error=modulo_error)

        if target is not None or within_deadband(target, current, error, use_mod_error=modulo_error):
            self.finish()
        else:
            desire_setter()


def generate_setters(desire_setter, current, modulo_error):
    return partial(Setter, desire_setter=desire_setter, current=current, modulo_error=modulo_error), \
           partial(RelativeToInitialSetter, desire_setter=desire_setter, current=current, modulo_error=modulo_error), \
           partial(RelativeToCurrentSetter, desire_setter=desire_setter, current=current, modulo_error=modulo_error), \
           partial(VelocitySetter, desire_setter=desire_setter, current=current, modulo_error=modulo_error)


Heading, RelativeToInitialHeading, RelativeToCurrentHeading, VelocityHeading = \
    generate_setters(desire_setter=desires.heading.set, current=kalman.heading.get, modulo_error=True)

Pitch, RelativeToInitialPitch, RelativeToCurrentPitch, VelocityPitch = \
    generate_setters(desire_setter=desires.pitch.set, current=kalman.pitch.get, modulo_error=True)

Roll, RelativeToInitialRoll, RelativeToCurrentRoll, VelocityRoll = \
    generate_setters(desire_setter=desires.roll.set, current=kalman.roll.get, modulo_error=True)

Depth, RelativeToInitialDepth, RelativeToCurrentDepth, VelocityDepth = \
    generate_setters(desire_setter=desires.depth.set, current=kalman.depth.get, modulo_error=False)

VelocityX, RelativeToInitialVelocityX, RelativeToCurrentVelocityX, VelocityVelocityX = \
    generate_setters(desire_setter=desires.speed.set, current=kalman.velx.get, modulo_error=False)

VelocityY, RelativeToInitialVelocityY, RelativeToCurrentVelocityY, VelocityVelocityY = \
    generate_setters(desire_setter=desires.sway_speed.set, current=kalman.vely.get, modulo_error=False)

PositionN, RelativeToInitialPositionN, RelativeToCurrentPositionN, VelocityPositionN = \
    generate_setters(desire_setter=desires.north.set, current=kalman.north.get, modulo_error=False)

PositionE, RelativeToInitialPositionE, RelativeToCurrentPositionE, VelocityPositionE = \
    generate_setters(desire_setter=desires.east.set, current=kalman.east.get, modulo_error=False)
