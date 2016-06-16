import os
import time

import cv2
import shm

import CaptureSource


class Video(CaptureSource.CaptureSource):
    def __init__(self, direction, filename, loop=True, shmlog=False):
        super().__init__(direction)
        self.filename = filename
        if os.environ.get('VISION_TEST_PATH'):
            self.filename = os.path.join(os.environ.get('VISION_TEST_PATH'), filename)
        if not os.path.exists(self.filename):
            raise OSError('Could not find video file {}'.format(self.filename))
        self.loop = loop
        self.cap = cv2.VideoCapture(self.filename)
        self.last_time = 0

    def acquire_next_image(self):
        _, next_image = self.cap.read()
        if next_image is None:
            if self.loop:
                self.cap.release()
                self.cap = cv2.VideoCapture(self.filename)
                return self.acquire_next_image()
        _time = 1. / self.cap.get(cv2.CAP_PROP_FPS) - (time.time() - self.last_time)
        if _time > 0:
            time.sleep(_time)

        self.last_time = time.time()
        return next_image, self.last_time
