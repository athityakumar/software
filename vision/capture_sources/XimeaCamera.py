import shm

import CaptureSource


width = 1020
height = 1020

shm.camera.forward_width.set(width)
shm.camera.forward_height.set(height)


class XimeaCamera(CaptureSource.CaptureSource):
    def __init__(self, direction):
        super(XimeaCamera, self).__init__(direction, persistent=False)
