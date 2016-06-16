import CaptureSource

class BVTSonar(CaptureSource.CaptureSource):
    def __init__(self, direction):
        super(BVTSonar, self).__init__(direction, persistent=False)

    def acquisition_loop(self):
        pass
                                
