import directed

capture_source = 'sonar'

class Sonar(directed.DirectedModule):
    def __init__(self, auvlog, save_video_log=True):
        super().__init__(capture_source, auvlog, save_video_log)
