import cv2
import numpy as np

import shm
from shm import kalman

from vision.modules import ModuleBase
from vision import options

capture_source = 'forward'
options = []

class RecoveryForward(ModuleBase.ModuleBase):
    def __init__(self, logger):
        super(RecoveryForward, self).__init__(options, True)

    def process(self, mat):
        pass