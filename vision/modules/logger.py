import os
import cv2
import time
import shm

# log_base_path = os.path.join(os.environ['CUAUV_SOFTWARE'], 'vision', 'video_logs')
log_base_path = '/var/log/auv/current'

class VideoWriter:
    def __init__(self, direction):
        self.fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        self.video_writer = None
        self.frame_count = 0
        self.direction = direction
        self.log_path = os.path.join(log_base_path,
                                     '{}_{}.avi'.format(direction, time.time()))

    def log_image(self, mat):
        # write the current frame number to shm. this is useful for shm logging,
        #  and shm log playback
        getattr(shm.camera, 'frame_num_{}'.format(self.direction)).set(self.frame_count)
        self.frame_count += 1
        if self.video_writer == None:
            self.video_writer = cv2.VideoWriter(self.log_path, self.fourcc, 10.,
                                                (mat.shape[1], mat.shape[0]))

        try:
            self.video_writer.write(mat)
        except:
            pass
