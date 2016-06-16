import math

'''
Forward Cam FOV: 440
'''

# These need to be in the same units - here, meters.
ueye_pixel_size = 4.5e-6
theia_focal_length = 0.0013

sim_pixel_size = 0.01 / 1024
sim_focal_length = 0.005

def field_of_view(dimension, focal_length):
  return 2 * math.atan(dimension / (2 * focal_length))

def calc_angle(object_coord, camera_center_coord, pixel_size, focal_length):
  diff = pixel_size * (object_coord - camera_center_coord)
  # It is "as if" the sensor was smaller. See https://en.wikipedia.org/wiki/Angle_of_view for a nice picture.
  return field_of_view(2 * diff, focal_length) / 2
