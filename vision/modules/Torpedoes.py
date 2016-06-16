import time
from collections import namedtuple
import math

import cv2
import shm
import numpy as np

from vision.modules import ModuleBase
from vision import options
from math import hypot

COLOR_RED = (0,0,255)
SIZE_SMALL = 0
SIZE_LARGE = 1

def get_size_str(size_int):
    if size_int == SIZE_SMALL:
        return "Small"
    elif size_int == SIZE_LARGE:
        return "Large"
    else:
        return "Invalid Size"

def label_rect(img, rect, text, color=(0,0,0)):
    text_origin = (rect[0], rect[1] - 10)
    cv2.putText(img, text, text_origin, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,0,0), thickness=3)
    cv2.putText(img, text, text_origin, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255))

def distance(pt1, pt2):
    return hypot(pt1[0] - pt2[0], pt1[1] - pt2[1])

capture_source = 'forward'

options = [options.IntOption('lab_b_min',  138, 0, 255),
           options.IntOption('lab_b_max', 178, 0, 255),
           options.IntOption('yuv_v_min', 70, 0, 255),
           options.IntOption('yuv_v_max', 122, 0, 255),
           options.IntOption('hls_h_min',  25, 0, 255),
           options.IntOption('hls_h_max', 35, 0, 255),
           options.IntOption('min_area', 200),
           options.IntOption('blur_size',  11, 1, 255, lambda x: x % 2 == 1),
           options.DoubleOption('min_circularity', .35, 0, 150),
           options.DoubleOption('heuristicPower', 15),
           options.IntOption('ideal_height', 510, 0, 1020),
           options.BoolOption('debugging', True)]


class Torpedoes(ModuleBase.ModuleBase):
    def __init__(self, logger):
        super(Torpedoes, self).__init__(options, True)
        self.vsp_data = None
        self.times = []

    def process(self, mat):
        self.times.insert(0, time.time())
        while time.time() - self.times[-1] > 5:
            self.times.pop()
            print('fps: {}'.format(len(self.times) / 5.))

        self.post('orig', mat)

        # Split the image into various color space components
        lab_image = cv2.cvtColor(mat, cv2.COLOR_BGR2LAB)
        lab_split = cv2.split(lab_image)
        yuv_image = cv2.cvtColor(mat, cv2.COLOR_BGR2YUV)
        yuv_split = cv2.split(yuv_image)
        hls_image = cv2.cvtColor(mat, cv2.COLOR_BGR2HLS)
        hls_split = cv2.split(hls_image)

        # Threshold those image components
        lab_bthreshed = cv2.inRange(lab_split[2], self.options["lab_b_min"], self.options["lab_b_max"])
        yuv_vthreshed = cv2.inRange(yuv_split[2], self.options["yuv_v_min"], self.options["yuv_v_max"])
        hls_hthreshed = cv2.inRange(hls_split[0], self.options["hls_h_min"], self.options["hls_h_max"])

        # Combine thresholded images (effectively AND thresholds together)
        finalThreshed = hls_hthreshed & lab_bthreshed & yuv_vthreshed

        # Erode and dilate thresholded images
        kernel = np.ones((5,5),np.uint8)
        eroded = cv2.erode(finalThreshed,kernel,iterations = 1)
        finalThreshed = cv2.dilate(eroded,kernel,iterations = 1)
        
        self.post('hls', hls_hthreshed)
        self.post('lab', lab_bthreshed)
        self.post('yuv', yuv_vthreshed)
        self.post('threshed', finalThreshed) 

        _, contours, hierarchy = cv2.findContours(np.copy(finalThreshed), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
      
        allContoursDrawing = np.copy(mat)
        cv2.drawContours(allContoursDrawing, contours, -1, (255, 255, 0), 2)
        self.post('contours', allContoursDrawing)

        final_contour = np.copy(mat)

        # The largest contour is the torpedoes board, more robust logic to be added
        if len(contours) < 1:
            shm.torpedoes_results.board_prob.set(0.0)
            self.post('final', final_contour)
            return
        else:
            shm.torpedoes_results.board_prob.set(1.0)

        board_contour_index, board_contour = max(enumerate(contours), key=lambda x: cv2.contourArea(x[1])) 

        # For some reason, OpenCV wraps the hierarchy in an extraneous list
        hierarchy = hierarchy[0]
      
        # Index of the first child contour of the board contour
        index = hierarchy[board_contour_index][2]

        cutouts = []
        # Make a list of the child contours of the board, these will be the cutouts
        while index >= 0:
            cutouts.append(contours[index])

            # Index of next contour
            index = hierarchy[index][0]

        # Find the four largest child contours
        cutouts.sort(key=cv2.contourArea, reverse=True)
        cutouts = cutouts[:4]


        # Find bounding rectangle of board contour, to be used in skew
        # calculation and determining "center" of board
        # Format is list of x, y, width, height in that order
        bounding_rect = cv2.boundingRect(board_contour)

        # List of four points corresponding to corners of the bounding rectangle
        center = (int(bounding_rect[0] + bounding_rect[2]/2), int(bounding_rect[1] + bounding_rect[3]/2))

        # Find positions of the corners clockwise from top left
        corners = [(bounding_rect[0], bounding_rect[1]), (bounding_rect[0] + bounding_rect[2], bounding_rect[1]),
                   (bounding_rect[0] + bounding_rect[2], bounding_rect[1] + bounding_rect[3]),
                   (bounding_rect[0], bounding_rect[1] + bounding_rect[3])]

        shm.torpedoes_results.board_center_x.set(center[0])
        shm.torpedoes_results.board_center_y.set(center[1])

        # Report board height, used as heursitic to determine distance to the board
        shm.torpedoes_results.board_height.set(bounding_rect[3])

        # Draw bounding rectangle with dot at the center (for debugging)
        cv2.drawContours(final_contour, [np.asarray(corners)], -1, (255, 255, 255), 2)
        cv2.circle(final_contour, center, 2, (255, 255, 255), thickness=2)

        cv2.drawContours(final_contour, [board_contour], -1, (0, 255, 255), 2)
        cv2.drawContours(final_contour, cutouts, -1, (0, 0, 255), 2)

        self.post('final', final_contour)

        # Calculate skew by finding the minimum distance from each corner to a point in the contour
        corner_distances = []
        for corner in corners:
            dist = min(map(lambda x: distance(corner, x[0]), board_contour))
            corner_distances.append(dist)

        # The skew (left-right) is the sum of the left two corner distances minus the right two corner distances.
        # If this is positive, go right, if it is negative, go left
        skew = corner_distances[0] + corner_distances[3] - corner_distances[1] - corner_distances[2]
        shm.torpedoes_results.board_skew.set(skew) 

        label_rect(final_contour, bounding_rect, "skew: {}".format(skew))

        # List of data about cutouts
        cutout_data = []
        for c in cutouts:
            bound_rect = cv2.boundingRect(c)

            # X coord of center is x of top left bounding box corner plus 1/2 width
            # Y coord of center is y of top left bounding box corner plus 1/2 height
            center = (int(bound_rect[0] + bound_rect[2]/2), int(bound_rect[1] + bound_rect[3]/2))

            area = cv2.contourArea(c)
            size = SIZE_LARGE
            
            data = [bound_rect, center, area, size]
            cutout_data.append(data)

        for c in cutout_data:
            cv2.circle(final_contour, c[1], 2, (0, 0, 255), thickness=2)

        if shm.torpedoes_results.characterize_board.get() == 2:
            cutout_strs = {shm.torpedoes_cutout_top_left: "Top Left ({})", shm.torpedoes_cutout_top_right: "Top Right ({})", shm.torpedoes_cutout_bottom_left: "Bottom Left ({})", shm.torpedoes_cutout_bottom_right: "Bottom Right ({})"}
            if len(cutout_data) > 0:
                cutout_groups = [shm.torpedoes_cutout_top_left, shm.torpedoes_cutout_top_right, shm.torpedoes_cutout_bottom_left, shm.torpedoes_cutout_bottom_right]
                for d in cutout_data:
                    if len(cutout_groups) > 0:
                        group = min(cutout_groups, key=lambda g: distance((g.x.get(), g.y.get()), d[1]))
                        group.x.set(d[1][0])
                        group.y.set(d[1][1])
                        group.height.set(d[0][3])
                        
                        label_rect(final_contour, d[0], cutout_strs[group].format(get_size_str(group.flags.get())))
                        cutout_groups.remove(group)
                    else:
                        break
             
        # characterize_board 0 means no characterize requested, 1 means requested, 2 means request fulfilled
        if len(cutouts) == 4 and shm.torpedoes_results.characterize_board.get() == 1:

            # Find 2 largest cutout contours, these are the large cutouts
            cutout_data.sort(key=lambda d: d[2], reverse=True)
            cutout_data[0][3] = SIZE_LARGE
            cutout_data[1][3] = SIZE_LARGE
            cutout_data[2][3] = SIZE_SMALL
            cutout_data[3][3] = SIZE_SMALL
            
            top_left_cutout = min(cutout_data, key=lambda c: c[1][0] + c[1][1])
            cutout_data.remove(top_left_cutout)
            shm.torpedoes_cutout_top_left.x.set(top_left_cutout[1][0])
            shm.torpedoes_cutout_top_left.y.set(top_left_cutout[1][1])
            size = top_left_cutout[3] 
            shm.torpedoes_cutout_top_left.flags.set(size)
            label_rect(final_contour, top_left_cutout[0], "Top Left ({})".format(get_size_str(size)))
            shm.torpedoes_cutout_top_left.height.set(top_left_cutout[0][3])

            top_right_cutout = max(cutout_data, key=lambda c: c[1][0] - c[1][1])
            cutout_data.remove(top_right_cutout)
            shm.torpedoes_cutout_top_right.x.set(top_right_cutout[1][0])
            shm.torpedoes_cutout_top_right.y.set(top_right_cutout[1][1])
            size = top_right_cutout[3]
            shm.torpedoes_cutout_top_right.flags.set(size)
            label_rect(final_contour, top_right_cutout[0], "Top Right ({})".format(get_size_str(size)))

            bottom_left_cutout = max(cutout_data, key=lambda c: -c[1][0] + c[1][1])
            cutout_data.remove(bottom_left_cutout)
            shm.torpedoes_cutout_bottom_left.x.set(bottom_left_cutout[1][0])
            shm.torpedoes_cutout_bottom_left.y.set(bottom_left_cutout[1][1])
            size = bottom_left_cutout[3]
            shm.torpedoes_cutout_bottom_left.flags.set(size)
            label_rect(final_contour, bottom_left_cutout[0], "Bottom Left ({})".format(get_size_str(size)))

            bottom_right_cutout = cutout_data[0]
            shm.torpedoes_cutout_bottom_right.x.set(bottom_right_cutout[1][0])
            shm.torpedoes_cutout_bottom_right.y.set(bottom_right_cutout[1][1])
            size = bottom_right_cutout[3]
            shm.torpedoes_cutout_bottom_right.flags.set(size)
            label_rect(final_contour, bottom_right_cutout[0], "Bottom Right ({})".format(get_size_str(size)))

            shm.torpedoes_results.characterize_board.set(2)
            

