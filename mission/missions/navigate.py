import shm
from shm import kalman
from mission.framework.task import Task
from mission.framework.combinators import Concurrent, Sequential, MasterConcurrent
from mission.framework.movement import Heading, Roll, Pitch, Depth, VelocityY
from mission.framework.position import MoveX, MoveY
from mission.framework.targeting import PIDLoop, HeadingTarget
from mission.framework.timing import Timer

CAMERA_WIDTH = shm.camera.forward_width.get()
CAMERA_HEIGHT = shm.camera.forward_height.get()

# TODO: Remove these lines when the shm camera variables are set correctly
CAMERA_WIDTH = 512
CAMERA_HEIGHT = 512

CAMERA_CENTER_X = CAMERA_WIDTH / 2
CAMERA_CENTER_Y = CAMERA_HEIGHT / 2
CAMERA_CENTER = (CAMERA_CENTER_X, CAMERA_CENTER_Y)

class NavigateChannel(Task):
    """Passes through gate (optional: with style)

    Start: facing general direction of gate after completing Buoy
    Finish: facing away from gate
    """
    def on_first_run(self, style, *args, **kwargs):
        self.logd("Starting NavigateChannel task")
        self.movement = None
        if not isinstance(style, Style):
            print("Invalid style passed into NavigateChannel!")
            self.loge("Invalid style passed into NavigateChannel!")
        self.style = style

    def on_run(self, *args, **kwargs):
        if not self.movement:
            restore = Concurrent(Heading(kalman.heading.get(), error=1), Pitch(0, error=1), Roll(0,error=1))
            self.movement = Sequential(self.style, restore)

        elif not self.movement.has_ever_finished:
            self.movement()

        else:
            self.finish()

    def on_finish(self, *args, **kwargs):
        self.logd('NavigateChannel task finished in {} seconds!'.format(
            self.this_run_time - self.first_run_time))

class Style(Task):
    """Base class for all styles

    Start: facing center of gate
    Finish: facing away from center of gate
    """
    def on_first_run(self, *args, **kwargs):
        # `self.__class__.__name__` gets the name of the class from an instance
        self.logd("Starting Style task: {}".format(self.__class__.__name__))
        self.style_on_first_run(*args, **kwargs)

    def on_run(self, *args, **kwargs):
        self.style_on_run(*args, **kwargs)

    def on_finish(self, *args, **kwargs):
        self.style_on_finish(*args, **kwargs)
        self.logd('Style task finished in {} seconds!'.format(
            self.this_run_time - self.first_run_time))

    """
    These should be overridden by child style classes
    """
    def style_on_first_run(self, *args, **kwargs):
        pass
    def style_on_run(self, *args, **kwargs):
        pass
    def style_on_finish(self, *args, **kwargs):
        pass

class StyleBasic(Style):
    """Simply moves forward
    """
    def style_on_first_run(self):
        self.movement = MoveX(5)

    def style_on_run(self):
        if not self.movement.has_ever_finished:
            self.movement()
        else:
            self.finish()

class StyleSideways(Style):
    """Heading changes 90 degrees starboard, so that sub is facing either right or left

    If `starboard` is False, then heading changes 90 degrees port
    """
    def style_on_first_run(self, starboard=True, *args, **kwargs):
        current_heading = kalman.heading.get()
        if starboard:
            change_heading = Heading(current_heading + 90, error=1)
            movement = MoveY(-5)
        else:
            change_heading = Heading(current_heading - 90, error=1)
            movement = MoveY(5)
        heading_restore = Heading(current_heading, error=1)
        self.style_sideways = Sequential(change_heading, movement, heading_restore)

    def style_on_run(self, *args, **kwargs):
        if not self.style_sideways.has_ever_finished:
            self.style_sideways()
        else:
            self.finish()

class StyleUpsideDown(Style):
    """Roll changes 180 degrees, so that sub is upside down
    """
    def style_on_first_run(self, *args, **kwargs):
        change_roll = Roll(180, error=1)
        movement = MoveX(5)
        restore_roll = Roll(0, error=1)
        self.style_upside_down = Sequential(change_roll, movement, restore_roll)

    def style_on_run(self, *args, **kwargs):
        if not self.style_upside_down.has_ever_finished:
            self.style_upside_down()
        else:
            self.finish()

class StylePitched(Style):
    """
    Pitch changes 75 degrees, so that sub is facing either down or up
    The reason for 75 degrees is so that the sub does not rapidly twist back
    and forth, in an attempt to maintain a stable heading

    If `up` is False, then sub pitches downwards
    """
    def style_on_first_run(self, up=True, *args, **kwargs):
        if up:
            change_pitch = Pitch(75, error=1)
        else:
            change_pitch = Pitch(-75, error=1)
        movement = MoveX(5)
        restore_pitch = Pitch(0, error=1)
        self.style_pitched = Sequential(change_pitch, movement, restore_pitch)

    def style_on_run(self, *args, **kwargs):
        if not self.style_pitched.has_ever_finished:
            self.style_pitched()
        else:
            self.finish()

class StyleLoop(Style):
    """Does a loop around the center bar of the channel

    Goes forward and under, backwards and over, then forwards and over
    """
    def style_on_first_run(self, *args, **kwargs):
        move_distance = 5 # meters
        depth_offset = 1 # offset to go up or down

        def generate_curve(distance, depth_offset, depth, iterations):
            #TODO: Make this curve more 'curvy'
            movement = []
            dist_tick = distance / iterations
            current_depth = depth
            depth_tick = depth_offset / (iterations - 1)
            for t in range(iterations):
                movement.append(Concurrent(MoveX(dist_tick), Depth(current_depth, error=.1)))
                current_depth += depth_tick
            return Sequential(subtasks=movement)

        current_depth = kalman.depth.get()
        forward_and_down = generate_curve(move_distance / 2, depth_offset, current_depth, 3)
        forward_and_up = generate_curve(move_distance / 2, -depth_offset, current_depth + depth_offset, 3)
        backward_and_up = generate_curve(-move_distance / 2, -depth_offset, current_depth, 3)
        backward_and_down = generate_curve(-move_distance / 2, depth_offset, current_depth - depth_offset, 3)
        forward = Sequential(generate_curve(move_distance / 2, -depth_offset, current_depth, 3),
                             generate_curve(move_distance / 2, depth_offset, current_depth - depth_offset, 3))
        self.style_loop = Sequential(forward_and_down, forward_and_up, backward_and_up,
                                     backward_and_down, forward)

    def style_on_run(self, *args, **kwargs):
        if not self.style_loop.has_ever_finished:
            self.style_loop()
        else:
            self.finish()

class AlignChannel(Task):
    """Position perpendicular with the gate

    Starts: with gate in view
    Finish: facing normal to the gate and centered to the bars
    """
    def on_first_run(self, *args, **kwargs):
        self.logv("Starting alignment")
        avg_x = lambda: (shm.navigate_results.left_x.get() + shm.navigate_results.right_x.get()) / 2
        avg_y = lambda: (shm.navigate_results.left_y.get() + shm.navigate_results.right_y.get()) / 2
        self.forward_align = HeadingTarget(point=(avg_x, avg_y), target=CAMERA_CENTER, px=.05)
        self.pid_loop = PIDLoop(output_function=VelocityY())

    def on_run(self, *args, **kwargs):
        self.logv("Aligning ...")
        if not self.pid_loop.has_ever_finished:
            self.forward_align()
            self.pid_loop(input_value=shm.navigate_results.angle.get, target=0, p=.05, i=0, d=0, deadband=1)
        else:
            self.finish()

    def on_finish(self, *args, **kwargs):
        self.logv("DoneEeeeeeee aligning")
        VelocityY(0)()

align = lambda: AlignChannel()
basic = lambda: NavigateChannel(StyleBasic())
pitched = lambda: NavigateChannel(StylePitched())
sideways = lambda: NavigateChannel(StyleSideways())
upside_down = lambda: NavigateChannel(StyleUpsideDown())
loop = lambda: NavigateChannel(StyleLoop())

class Flip180(Task):
    def on_first_run(self, *args, **kwargs):
        #heading = Heading((kalman.heading.get() + 180) % 360, error=1)
        self.flip = Sequential(Pitch(0, error=1), Roll(0, error=1), Timer(1.5), Heading(lambda: kalman.heading.get() + 180, error=1), Timer(1))
    def on_run(self, *args, **kwargs):
        self.flip()
        if self.flip.has_ever_finished:
            self.finish()

test_all = lambda: Sequential(basic(), Heading(90, error=1), pitched(), Heading(270, error=1), sideways(), Heading(90, error=1), upside_down(), Heading(270, error=1), Depth(2.1, error=.1), loop())
