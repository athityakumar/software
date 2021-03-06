import cv2
import time

import CaptureSource

class GenericVideoCapture(CaptureSource.CaptureSource):
    def __init__(self, direction, index=0):
        super().__init__(direction)
        self.camera = cv2.VideoCapture(index)

    def acquire_next_image(self):
        _, image = self.camera.read()
        acq_time = time.time()
        return image, acq_time
