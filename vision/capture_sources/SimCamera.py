import CaptureSource

class SimCamera(CaptureSource.CaptureSource):
    def __init__(self, direction):
        super().__init__(direction, persistent=False)
