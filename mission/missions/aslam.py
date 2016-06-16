from mission.framework.task import Task
from mission.framework.timing import Timer
from mission.framework.combinators import *
from auv_python_helpers.cameras import *

import shm, aslam, time, math, random
import numpy as n

class Ram(Task):
  def on_run(self, buoy, results, real_pos):

    buoy_pos = buoy.position()
    aslam.sub.move_to(buoy_pos)

    vision = results.get()
    
    sub  = aslam.sub.position()
    delt = (real_pos[0] - sub[0], real_pos[1] - sub[1], real_pos[2] - sub[2])
    distance = (delt[0] ** 2.0 + delt[1] ** 2.0 + delt[2] ** 2.0) ** 0.5

    if vision.probability > 0.5:
  
      obj_x, obj_y = vision.center_x, vision.center_y
      ctr_x, ctr_y = 512., 512.
    
      # Sonar / camera simulation: calculate actual positional delta.
      rad = vision.radius
      calc_angle_subtended = calc_angle(rad + ctr_x, ctr_x, sim_pixel_size, sim_focal_length)
      real_radius = 0.1
      calc_distance = real_radius / math.sin(calc_angle_subtended)
      # ^ why is this wrong

      # Ground truth heading / pitch / distance.

      # Relative heading from sub to object, Kalman is ground truth.
      sub_h = math.radians(shm.kalman.heading.get())
      heading = math.atan2(delt[1], delt[0]) - sub_h
      heading = heading % (2 * math.pi)
      if heading > math.pi: heading -= 2 * math.pi

      # Relative pitch from sub to object. Currently, sub is presumed at neutral pitch while observing, although this could be changed.
      pitch = math.atan2(-delt[2], (delt[0] ** 2.0 + delt[1] ** 2.0) ** 0.5)

      # Camera-based heading / pitch / distance.
      calc_heading = calc_angle(obj_x, ctr_x, sim_pixel_size, sim_focal_length)
      calc_pitch = -calc_angle(obj_y, ctr_y, sim_pixel_size, sim_focal_length)

      #self.logv('Real heading, pitch, distance: {}. Calc heading, pitch, distance: {}'.format(
      #  (heading, pitch, distance),
      #  (calc_heading, calc_pitch, calc_distance)
      #  ), copy_to_stdout = True)

      if distance > 0.1:
        obs = aslam.Observation(aslam.sub, buoy, n.array([calc_heading, calc_pitch, distance]), n.array([0.1, 0.1, 0.5]))
        obs.apply()
        buoy.mark_visible()
        self.logv('Prior: {}'.format(obs.prior()), copy_to_stdout = True)
      else:
        buoy.mark_invisible()

    else:
      buoy.mark_invisible()

    if distance < 0.2:
      self.logv('Presumably we rammed the buoy!', copy_to_stdout = True)
      self.finish() 

Demo = lambda: Sequential(
  Ram(buoy = aslam.world.buoy_a, results = shm.a_buoy_results, real_pos = (5., 5., 1.5)),
  Ram(buoy = aslam.world.buoy_b, results = shm.b_buoy_results, real_pos = (-4., -3., 1.5)),
  Ram(buoy = aslam.world.buoy_c, results = shm.c_buoy_results, real_pos = (5., -5., 0.5)),
  Ram(buoy = aslam.world.buoy_d, results = shm.d_buoy_results, real_pos = (-2., 2., 1.))
  )
