import shm

import CaptureSource


width = 1024
height = 768

shm.camera.forward_width.set(width)
shm.camera.forward_height.set(height)


class FirewireCamera(CaptureSource.CaptureSource):
    def __init__(self, direction):
        super(FirewireCamera, self).__init__(direction, persistent=False)
