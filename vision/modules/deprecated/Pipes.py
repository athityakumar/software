from collections import namedtuple
import cv2
import numpy as np

from vision.modules import ModuleBase
import gui_options
import shm

vision_options = [gui_options.IntOption('lab_b_min', 41, 0, 255),
                  gui_options.IntOption('lab_b_max', 150, 0, 255),
                  gui_options.IntOption('yuv_v_min', 107, 0, 255),
                  gui_options.IntOption('yuv_v_max', 210, 0, 255),
                  gui_options.IntOption('hsv_h_min', 64, 0, 255),
                  gui_options.IntOption('hsv_h_max', 128, 0, 255),
                  gui_options.IntOption('erode_size', 2, 0, 50),
                  gui_options.IntOption('dilate_size', 2, 0, 50),
                  gui_options.IntOption('min_pipe_area', 100),
                  gui_options.IntOption('min_invader_area', 1000),
                  gui_options.FloatOption('min_rectangularity', 1000),
                  gui_options.FloatOption('heuristic_power', 5),
                  gui_options.BooleanOption('debugging', False)]

capture_source = 'downward'

class Pipes(ModuleBase.ModuleBase):
    def __init__(self):
        super(Pipes, self).__init__(True)

    def process(self, mat):
        self.post('orig', mat)
        
        lab_image = cv2.cvtColor(mat, cv2.COLOR_BGR2LAB)
        lab_split = cv2.split(lab_image)
        yuv_image = cv2.cvtColor(mat, cv2.COLOR_BGR2YUV)
        yuv_split = cv2.split(yuv_image)
        hsv_image = cv2.cvtColor(mat, cv2.COLOR_BGR2HSV)
        hsv_split = cv2.split(hsv_image)

        lab_bthreshed = cv2.inRange(lab_split[2], self.options["lab_b_min"], self.options["lab_b_max"])
        yuv_vthreshed = cv2.inRange(yuv_split[2], self.options["yuv_v_min"], self.options["yuv_v_max"])
        hsv_hthreshed = cv2.inRange(hsv_split[0], self.options["hsv_h_min"], self.options["hsv_h_max"])

        final_threshed = lab_bthreshed & yuv_vthreshed & hsv_hthreshed 

        erode_size = self.options['erode_size']
        dilate_size = self.options['dilate_size']
        erode_element = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (erode_size * 2 + 1, erode_size * 2 + 1),
                                                  (erode_size, erode_size))
        dilate_element = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_size * 2 + 1, dilate_size * 2 + 1),
                                                   (dilate_size, dilate_size))

        eroded = cv2.erode(final_threshed, erode_element)
        dilated = cv2.dilate(eroded, dilate_element)

        if self.options['debugging']:
            self.post('lab b Threshed', lab_bthreshed)
            self.post('yuv v Threshed', yuv_vthreshed)
            self.post('hsv h Threshed', hsv_hthreshed)
            self.post("Threshed", final_threshed)
            self.post("Masked", cv2.bitwise_and(mat, mat, mask=final_threshed))
            self.post("Eroded", eroded)
            self.post("Eroded/Dilated", dilated.copy())

        _, contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if contours is None:
            print("None returned from findContours")
            return

        if self.options['debugging']:
            allContoursDrawing = np.copy(mat)
            cv2.drawContours(allContoursDrawing, [c for c in contours if cv2.contourArea(c)], -1, (255, 255, 0), 2)
            self.post("All contours", allContoursDrawing)

        contour_info = namedtuple("contour_info",
                      ["contour", "rectangle_contour", "rect", "angle", "area", "center", "rectangularity", "heuristic_score"])
        
        contour_data = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.options['min_pipe_area']:
                continue

            rotated_rect = cv2.minAreaRect(c)
            contour = np.array(cv2.boxPoints(rotated_rect)).astype(int)
            rectangularity = area / (rotated_rect[1][0] * rotated_rect[1][1])
            center = rotated_rect[0]
            heuristic_score = rectangularity ** self.options["heuristic_power"] * cv2.contourArea(contour)
            x = contour_info(c, contour, rotated_rect, rotated_rect[2], area, center, rectangularity, heuristic_score)

            contour_data.append(x)
        if self.options["debugging"]:
            contours_to_draw = [x.rectangle_contour for x in contour_data]
            good_contours_drawing = np.copy(mat)
            cv2.drawContours(good_contours_drawing, contours_to_draw, -1, (255, 0, 0), 4)
            self.post("Rectangular contours", good_contours_drawing)
        
        if len(contour_data) == 0:
            shm.pipe_results.heuristic_score.set(0)
            return

        best = max(contour_data, key=lambda x: x.heuristic_score)
        
        if self.options['debugging']:
            print("rect:{}".format(best.rect))
            print("width:{}".format(best.rect[1][0]))
            print("height:{}".format(best.rect[1][1]))

        # True if taller than wide
        if best.rect[1][0] < best.rect[1][1]:
            shm.pipe_results.angle.set(best.angle)
            if self.options['debugging']:
                print("angle:{}".format(best.angle))
        else:
            shm.pipe_results.angle.set(best.angle + 90)
            if self.options['debugging']:
                print("angle:{}".format(best.angle + 90))
        shm.pipe_results.center_x.set(int(best.center[0]))
        shm.pipe_results.center_y.set(int(best.center[1]))
        shm.pipe_results.rectangularity.set(best.rectangularity)
        shm.pipe_results.heuristic_score.set(best.heuristic_score)
