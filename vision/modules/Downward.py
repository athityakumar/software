import directed

capture_source = 'downward'

class Downward(directed.DirectedModule):
    def __init__(self, auvlog, save_video_log=False):
        super().__init__(capture_source, auvlog, save_video_log)