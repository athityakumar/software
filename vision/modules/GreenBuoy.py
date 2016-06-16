import shm
from vision.modules import ModuleBase, buoy_common
from vision import options

capture_source = 'forward'
options = [options.IntOption('hls_h_min', 105, 0, 255),
           options.IntOption('hls_h_max', 143, 0, 255),
           options.IntOption('lab_a_min', 127, 0, 255),
           options.IntOption('lab_a_max', 235, 0, 255),
           options.IntOption('lab_b_min', 3, 0, 255),
           options.IntOption('lab_b_max', 123, 0, 255),
           options.IntOption('min_area', 100, 0, 1000000),
           options.IntOption('blur_size', 4, 1, 50),
           options.IntOption('min_heuristic_score', 0, 0, 1000),
           options.DoubleOption('min_circularity', 0.5, 0, 1),
           options.BoolOption('verbose', False)
          ]

class GreenBuoy(ModuleBase.ModuleBase):
    def __init__(self, logger):
        super(GreenBuoy, self).__init__(options, True)

    def process(self, mat):
        buoy_common.process(self, mat, shm.green_buoy_results)
