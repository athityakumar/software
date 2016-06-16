import shm
import CaptureSource

class UEyeCamera(CaptureSource.CaptureSource):
    def __init__(self, direction):
        super(UEyeCamera, self).__init__(direction, persistent=False)

    def acquisition_loop(self):
        pass
