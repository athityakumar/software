import time
from collections import namedtuple
import math

import cv2
import shm
import numpy as np

from vision.modules import ModuleBase
from vision import options

import random


capture_source = 'downward'

CONTOUR_HEURISTIC_LIMIT = 5
CONTOUR_SCALED_HEURISTIC_LIMIT = 2


options = [options.IntOption('hls_h_min', 105, 0, 255), #need to change value to white
		   options.IntOption('hls_h_max', 143, 0, 255), #need to change value to white
		   options.IntOption('lab_a_min', 127, 0, 255), #need to change value to white
		   options.IntOption('lab_a_max', 235, 0, 255), #need to change value to white
		   options.IntOption('lab_b_min', 3, 0, 255), #need to change value to white
		   options.IntOption('lab_b_max', 123, 0, 255), #need to change value to white
		   options.IntOption('min_area', 500, 0, 1000000),
		   options.IntOption('blur_size',  11, 1, 255, lambda x: x % 2 == 1),
		   options.DoubleOption('min_rectangularity', 0.5, 0, 1),
		   options.BoolOption('debugging', True)]

class Bins(ModuleBase.ModuleBase):
	def __init__(self, logger):
		super(Bins, self).__init__(options, True)

	def process(self, mat):

		"""Currently a stub, below are the shm variables to set
		shm.bin1.x
		shm.bin1.y
		shm.bin1.covered
		shm.bin1.p

		shm.bin2.x
		shm.bin2.y
		shm.bin2.covered
		shm.bin2.p

		shm.handle.x
		shm.handle.y
		shm.handle.p
		"""
		self.post('orig', mat)

		lab_image = cv2.cvtColor(mat, cv2.COLOR_RGB2LAB)
		lab_split = cv2.split(lab_image)
		lab_athreshed = cv2.inRange(lab_split[1], self.options['lab_a_min'],
												  self.options['lab_a_max'])
		print('a min: {}, a max: {}'.format( self.options['lab_a_min'],  self.options['lab_a_max']))
		if self.options['debugging']:
			self.post('asdf lab a Threshed', lab_athreshed)


		lab_bthreshed = cv2.inRange(lab_split[2], self.options['lab_b_min'],
												  self.options['lab_b_max'])
		if self.options['debugging']:
			self.post('lab b Threshed', lab_bthreshed)


		hls_image = cv2.cvtColor(mat, cv2.COLOR_RGB2HLS)
		hls_split = cv2.split(hls_image)
		hls_hthreshed = cv2.inRange(hls_split[0], self.options['hls_h_min'],
												  self.options['hls_h_max'])
		if self.options['debugging']:
			self.post('hls h Threshed', hls_hthreshed)
		
		finalThreshed = hls_hthreshed & lab_athreshed & lab_bthreshed
		if self.options['debugging']:
			self.post('finalThreshed', finalThreshed)

		blurred = cv2.medianBlur(finalThreshed, 1)
		self.post('blurred', blurred)

		_, contours, hierarchy = cv2.findContours(blurred.copy(), cv2.RETR_EXTERNAL,
													cv2.CHAIN_APPROX_SIMPLE)
		contoursMat = mat.copy()

		contourAreas = []
		for contour in contours:
			contourArea = cv2.contourArea(contour)
			if contourArea >= self.options['min_area']:
				contourAreas.append([contour, contourArea])
		contourAreas = sorted(contourAreas, key=lambda x: -x[1])[:CONTOUR_HEURISTIC_LIMIT]

		contourScores = []
		for c, a in contourAreas:
			x, y, w, h = cv2.boundingRect(c)
			center = (x + w/2, y + h/2)
			rectangularity = a / (w*h)
			if rectangularity >= self.options['min_rectangularity']:
				contourScores.append((c, a, rectangularity, rectangularity * a, center, x + w/2, y + h/2))
		contourScores = sorted(contourScores, key=lambda x: -x[3])[:CONTOUR_SCALED_HEURISTIC_LIMIT]

		if contourScores:
			binContour = max(contourScores, key=lambda x: x[4][1]) # Zero is top-left of image
			cv2.drawContours(contoursMat, [binContour[0]], -1, (255, 255, 0), 2)
			self.post("All contours", contoursMat)

			shm.bin1.p.set(1.0)
			shm.bin1.x.set(int(binContour[4][0]))
			shm.bin1.y.set(int(binContour[4][1]))
			shm.bin1.covered.set(1)

			shm.bin2.p.set(1.0)
			shm.bin2.x.set(int(binContour[4][0]))
			shm.bin2.y.set(int(binContour[4][1]))
			shm.bin2.covered.set(0)

		else:
			shm.bin1.p.set(0)
			shm.bin2.p.set(0)
