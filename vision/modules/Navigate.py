import time
from collections import namedtuple
import math

import cv2
import shm
import numpy as np

from vision.modules import ModuleBase
from vision import options

capture_source = 'forward'

options = [
        options.IntOption('lab_a_min', 0, 0, 255),
        options.IntOption('lab_a_max', 124, 0, 255),
        options.IntOption('lab_b_min', 0, 0, 255),
        options.IntOption('lab_b_max', 126, 0, 255),
        options.IntOption('lab_l_min', 0, 0, 255),
        options.IntOption('lab_l_max', 255, 0, 255),
        options.IntOption('min_area', 500),
        options.IntOption('kernel_size', 11, 1, 255),
        options.DoubleOption('height_width_ratio', 3.0, 1.0, 6.0),
        options.BoolOption('debugging', True)
]

HEIGHT_WIDTH_RATIO = 5.0

class Navigate(ModuleBase.ModuleBase):
    def __init__(self, logger):
        super(Navigate, self).__init__(options, True)

    def process(self, mat):
        self.post('original', mat)
        lab_image = cv2.cvtColor(mat, cv2.COLOR_RGB2LAB)
        lab_l, lab_a, lab_b = cv2.split(lab_image)
        lab_a_threshed = cv2.inRange(lab_a, self.options['lab_a_min'], self.options['lab_a_max'])
        lab_b_threshed = cv2.inRange(lab_b, self.options['lab_b_min'], self.options['lab_b_max'])
        lab_l_threshed = cv2.inRange(lab_l, self.options['lab_l_min'], self.options['lab_l_max'])

        if self.options['debugging']:
            self.post('a threshed', lab_a_threshed)
            self.post('b threshed', lab_b_threshed)
            self.post('l threshed', lab_l_threshed)

        threshed = lab_a_threshed & lab_b_threshed & lab_l_threshed

        kernel_size = self.options['kernel_size'] * 2 + 1
        kernel = np.ones(kernel_size, np.uint8)
        eroded = cv2.erode(threshed, kernel, iterations=1)
        dilated = cv2.dilate(eroded, kernel, iterations=1)

        self.post('eroded', eroded)
        self.post('dilated', dilated)

        processed = dilated

        contours_img = processed.copy() # make copy since findContours alters original image

        _, contours, hierarchy = cv2.findContours(contours_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        contours_mat = mat.copy()
        cv2.drawContours(contours_mat, contours, -1, (255, 0, 255), 2)
        self.post('all contours', contours_mat)

        contours_mat = mat.copy()
        filtered_contours = []
        for contour in contours:
            contour_area = cv2.contourArea(contour)
            x, y, w, h = cv2.boundingRect(contour)
            if contour_area > self.options['min_area'] and \
                    h / w >= self.options['height_width_ratio']:
                filtered_contours.append(contour)
        cv2.drawContours(contours_mat, filtered_contours, -1, (255, 0, 255), 2)
        self.post('filtered contours', contours_mat)

        #get two largest yellow contours and assume they are vertical bars
        #break into two arrays of points, then combine into one array
        #get min bounding rect and min bounding circle
        sorted_contours = sorted(filtered_contours, key=lambda c: cv2.contourArea(c))
        if len(sorted_contours) >= 2:
            vbar1 = sorted_contours[0]
            x1, y1, w1, h1 = cv2.boundingRect(vbar1)
            vbar2 = sorted_contours[1]
            x2, y2, w2, h2 = cv2.boundingRect(vbar2)
            height_difference = (h1 - h2) / max(h1, h2) * 90
            if x1 < x2:
                # vbar1 is the left vertical bar
                shm.navigate_results.left_x.set(x1 + (w1 / 2))
                shm.navigate_results.left_y.set(y1 + (h1 / 2))
                shm.navigate_results.left_area.set(cv2.contourArea(vbar1))
                # vbar2 is the right vertical bar
                shm.navigate_results.right_x.set(x2 + (w2 / 2))
                shm.navigate_results.right_y.set(y2 + (h2 / 2))
                shm.navigate_results.right_area.set(cv2.contourArea(vbar2))
                shm.navigate_results.angle.set(-height_difference)
            else:
                # vbar2 is the left vertical bar
                shm.navigate_results.left_x.set(x2 + (w2 / 2))
                shm.navigate_results.left_y.set(y2 + (h2 / 2))
                shm.navigate_results.left_area.set(cv2.contourArea(vbar2))
                # vbar1 is the right vertical bar
                shm.navigate_results.right_x.set(x1 + (w1 / 2))
                shm.navigate_results.right_y.set(y1 + (h1 / 2))
                shm.navigate_results.right_area.set(cv2.contourArea(vbar1))
                shm.navigate_results.angle.set(height_difference)
            shm.navigate_results.left_prob.set(1)
            shm.navigate_results.right_prob.set(1)
        elif len(sorted_contours) == 1:
            # TODO: find a way to get better information
            # we could just rotate either way since we just need to go through the channel
            pass
        else:
            # we don't see the navigate channel in view
            shm.navigate_results.left_prob.set(0)
            shm.navigate_results.right_prob.set(0)
