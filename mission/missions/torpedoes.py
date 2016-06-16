import shm
from framework.targeting import ForwardTarget, HeadingTarget, PIDLoop
from framework.helpers import within_deadband
from framework.task import Task
from framework.movement import VelocityX, VelocityY, RelativeToCurrentHeading
from framework.combinators import Sequential, MasterConcurrent
from framework.timing import Timer

direction = ["N", "W"]
cutouts = [shm.torpedoes_cutout_top_left, shm.torpedoes_cutout_top_right, shm.torpedoes_cutout_bottom_left, shm.torpedoes_cutout_bottom_right]
CAMERA_CENTER = (512/2, 512/2)
CAMERA_AREA = 512*512
CAMERA_HEIGHT = 512
LOCATE_SWEEP_ANGLE = 135
board_coords = (shm.torpedoes_results.board_center_x.get, shm.torpedoes_results.board_center_y.get)
heading_target_board = HeadingTarget()

# Currently selected target, set by SelectTarget task
target = None

'''
Rotates the sub until it sees the torpedoes board
'''
class LocateBoard(Task):
    def on_first_run(self):
        # TODO: Only look within a specified angle and consider the board
        # to be at the angle where vision reported the highest board
        # heursitic score
        self.target_heading = shm.kalman.heading.get() + LOCATE_SWEEP_ANGLE
        self.heading_vel = RelativeToCurrentHeading(10)

    def on_run(self):
        if (shm.torpedoes_results.board_prob.get() > 0.7):
            if heading_target_board.finished:
                self.finish() 
            else:
                heading_target_board.run(board_coords, target=CAMERA_CENTER)
        else:
            self.heading_vel() 
            pass

'''
Moves forward until the board is a certain distance from the sub
Perhaps not necessary because the bins are so close to torpedoes
'''
class ApproachBoard(Task):
    def on_first_run(self):
        self.logi("Started ApproachBoard")
        print("Started ApproachBoard")

        self.target_board = ForwardTarget()
        self.zero_vel_x = VelocityX(0.0)
        self.zero_vel_y = VelocityY(0.0)

        self.pid_loop_x = PIDLoop(output_function=VelocityX())

    def on_run(self):
        if self.pid_loop_x.finished:
            # Zero speed so the sub doesn't keep moving after finish
            self.zero_vel_x()
            self.zero_vel_y()

            self.logi("Finished ApproachBoard")
            print("Finished ApproachBoard")
            self.finish()
        else:
            self.target_board(board_coords, target=CAMERA_CENTER)
            self.pid_loop_x(input_value=shm.torpedoes_results.board_height.get, p=.005, i=0, d=0, target=CAMERA_HEIGHT*0.8, deadband=10)

'''
Aligns the sub to face normal to the board
'''
class AlignToBoard(Task):
    def on_first_run(self):
        print("Started AlignToBoard")
        self.pid_loop_y = PIDLoop(output_function=VelocityY())
        self.zero_vel_y = VelocityY(0.0)
        
    def on_run(self):
        if self.pid_loop_y.finished:
            self.zero_vel_y()
            print("Finished AlignToBoard")
            self.finish()
        else:
            # By keeping the board centered in the camera (via heading adjusment)
            # and swaying until skew is zero, we will align normal to the board
            heading_target_board.run(board_coords, target=CAMERA_CENTER, px=0.05)
            self.pid_loop_y(input_value=shm.torpedoes_results.board_skew.get, p=0.005, i=0, target=0, deadband=0.5)


'''
Attempts to remove the cover from the covered cutout
'''
class RemoveCover(Task):
    def on_first_run(self):
        # Not the real one! Placeholder for video purposes
        self.remove_cover = Sequential(MasterConcurrent(Timer(1.5), VelocityY(-1)), MasterConcurrent(Timer(1.5), VelocityY(1)))

    def on_run(self):
        if self.remove_cover.finished:
            print("Removed Cover!")
            self.finish()
        else:
            self.remove_cover()

'''
Select the covered cutout as the target
'''
class SelectCoveredCutout(Task):
    def on_run(self):
        global target
        # For now, just select the top left cutout (All cutouts have covers currently!)
        target = shm.torpedoes_cutout_top_left
        self.finish()

'''
Decides which cutout should be targeted, the preference order is:
    1. Uncovered small cutout, with specified letter
    2. Big cutout, with specified letter
    3. Small cutout
    4. Big cutout
'''
class SelectTarget(Task):
    def on_run(self):
        # For now, ignore the letters since we can't classify them yet

        global cutouts
        global target
        small_cutouts = [c for c in cutouts if c.flags.get() == 0]
        large_cutouts = [c for c in cutouts if c.flags.get() == 1]
        
        flags = [c.flags.get() for c in cutouts]

        if len(small_cutouts) > 0:
            global targets
            target = small_cutouts[0]
            cutouts.remove(target)
        elif len(large_cutouts) > 0:
            global targets
            target = large_cutouts[0]
            cutouts.remove(target)
        elif len(cutouts) > 0:
            global targets
            target = cutouts[0]
            cutouts.remove(target)
        else:
            print("Can't find a suitable target!")

        self.finish()

'''
Targets the selected cutout and shoots a torpedo thought it
'''
class TargetCutout(Task):
    def on_first_run(self):
        self.forward_target = ForwardTarget()
        self.zero_vel_y = VelocityY(0.0)
        self.pid_loop_x = PIDLoop(output_function=VelocityX())
        self.zero_vel_x = VelocityX(0.0)

    def on_run(self):
        global target

        if self.forward_target.finished and self.pid_loop_x.finished:
            self.zero_vel_y()
            self.zero_vel_x()
            self.finish()
        else:
            coords = (target.x.get(), target.y.get())
            self.forward_target(coords, target=CAMERA_CENTER)
            self.pid_loop_x(input_value=target.height.get, p=.001, i=0, d=0, target=CAMERA_HEIGHT*0.8, deadband=10)
        
'''
Moves from targeting one cutout to another
'''
class TransitionToCutout(Task):
    def on_run(self):
        # Not implemented yet!
        pass
'''
Requests boad characterization from vision and continues once it has been done
'''
class CharacterizeBoard(Task):
    def on_first_run(self):
        shm.torpedoes_results.characterize_board.set(1)

    def on_run(self):
        if shm.torpedoes_results.characterize_board.get() == 2:
            self.finish()
'''
Fires a torpedo!
'''
class FireTorpedo(Task):
    def on_run(self):
        # For now, just print a message
        print("Fired torpedo!")
        self.finish()

'''
Task which runs the Set Course mission
'''
def locate_align_characterize():
    return Sequential(LocateBoard(), ApproachBoard(), AlignToBoard(), CharacterizeBoard())

def select_and_target():
    return Sequential(SelectTarget(), TargetCutout())

class SetCourse(Task):
    def on_first_run(self):
        self.task = Sequential(locate_align_characterize(), SelectCoveredCutout(), TargetCutout(), RemoveCover(), locate_align_characterize(), select_and_target(), FireTorpedo(), locate_align_characterize(), select_and_target(), FireTorpedo())

    def on_run(self):
        if self.task.finished:
            self.finish()
        else:
            self.task()
