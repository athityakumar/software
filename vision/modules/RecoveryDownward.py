import cv2
import numpy as np

import shm
from shm import kalman

from vision.modules import ModuleBase
from vision import options

capture_source = 'downward'
options = []

class RecoveryDownward(ModuleBase.ModuleBase):
    def __init__(self, logger):
        super(RecoveryDownward, self).__init__(options, True)

    def process(self, mat):
        pass