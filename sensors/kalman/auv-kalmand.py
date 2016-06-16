#!/usr/bin/env python3
''' The daemon that runs the Python Kalman filters for velocity and heading. '''

from numpy import array, cos, sin, radians
import numpy as np
import quat

from settings import dt

import sys
import shm
import time

from auv_python_helpers.angles import abs_heading_sub_degrees
from shm.watchers import watcher
from threading import Thread
from conf.vehicle import sensors, VEHICLE
from functools import reduce

rec_get_attr = lambda s: reduce(lambda acc, e: getattr(acc, e), s.split('.'), shm)

# thruster_array allows access to thruster values
thrusters = ['port', 'starboard', 'sway_fore', 'sway_aft']

#### Heading Shared Variables
hdg_input_var = rec_get_attr(sensors["heading"])
hdg_out_var = shm.kalman.heading
hdg_cumulative_out_var = shm.kalman.heading_cumulative
rate_var = rec_get_attr(sensors["ratez"])
rate_var_imu = rec_get_attr(sensors["heading_rate"])
rate_out_var = shm.kalman.heading_rate

heading_sensor = shm.kalman.sensor

pitch_var = rec_get_attr(sensors["pitch"])
# HIM pitch velocity is negative!
pitch_rate_var = rec_get_attr(sensors["pitch_rate"])
pitch_out_var = shm.kalman.pitch
pitch_rate_out_var = shm.kalman.pitch_rate

roll_var = rec_get_attr(sensors["roll"])
roll_rate_var = rec_get_attr(sensors["roll_rate"])
roll_out_var = shm.kalman.roll
roll_rate_out_var = shm.kalman.roll_rate

gx4_q0 = rec_get_attr(sensors["quaternion"]).q0
gx4_q1 = rec_get_attr(sensors["quaternion"]).q1
gx4_q2 = rec_get_attr(sensors["quaternion"]).q2
gx4_q3 = rec_get_attr(sensors["quaternion"]).q3

#### Velocity Shared Variables
x_vel_in = rec_get_attr(sensors["velx"])
y_vel_in = rec_get_attr(sensors["vely"])
# XXX Fragile.
dvl_velocity = "dvl" in sensors["vely"]

# NB: swapped for testing, correct?
x_acc_in = rec_get_attr(sensors["accelx"])
y_acc_in = rec_get_attr(sensors["accely"])
depth_in = rec_get_attr(sensors["depth"])
depth_offset = rec_get_attr(sensors["depth_offset"])


x_vel_out = shm.kalman.velx
y_vel_out = shm.kalman.vely

x_acc_out = shm.kalman.accelx
y_acc_out = shm.kalman.accely
depth_out = shm.kalman.depth
depth_rate_out = shm.kalman.depth_rate
forward_out = shm.kalman.forward
sway_out = shm.kalman.sway
north_out = shm.kalman.north
east_out = shm.kalman.east

# DVL Beam vars
beam_vars = [shm.dvl.low_amp_1,
        shm.dvl.low_amp_2,
        shm.dvl.low_amp_3,
        shm.dvl.low_amp_4,
        shm.dvl.low_correlation_1,
        shm.dvl.low_correlation_2,
        shm.dvl.low_correlation_3,
        shm.dvl.low_correlation_4]

wrench = shm.control_internal_wrench

def CalibrateHeadingRate(var):
    vals = []
    for i in range(10):
        vals.append(var.get())
        time.sleep(0.02)
    return sum(vals)/len(vals)
rate_offset = CalibrateHeadingRate(rate_var)
rate_offset_imu = CalibrateHeadingRate(rate_var_imu)

from kalman_unscented import UnscentedKalmanFilter

def fx(x, dt):
    q_initial = x[:4]
    disp_quat = quat.ypr_to_quat([vel*dt for vel in x[4:]])
    q_final = quat.add_quat(q_initial, disp_quat)
    x[0] = q_final[0]
    x[1] = q_final[1]
    x[2] = q_final[2]
    x[3] = q_final[3]
    return x

def hx(x):
    return x

orientation_filter = UnscentedKalmanFilter(7, fx, 7, hx, dt, .1)
orientation_filter.x_hat = np.array([gx4_q0.get(), gx4_q1.get(), gx4_q2.get(), gx4_q3.get(), 0, 0, 0])
orientation_filter.P *= .5
orientation_filter.R = np.array([[10, 0, 0, 0, 0, 0, 0],
                                 [0, 90, 0, 0, 0, 0, 0],
                                 [0, 0, 10, 0, 0, 0, 0],
                                 [0, 0, 0, 40, 0, 0, 0],
                                 [0, 0, 0, 0, .5, 0, 0],
                                 [0, 0, 0, 0, 0, .7, 0],
                                 [0, 0, 0, 0, 0, 0, .05]])

from kalman_position import PositionFilter
kalman_xHat = array([[ -1*x_vel_in.get(),
    # x_acc_in.get(),
    y_vel_in.get(),
    0,
    # y_acc_in.get(),
    0,
    0,
    0,
    depth_in.get() - depth_offset.get(),
    #depth_in.get() - 8.64,
    0]]).reshape(8,1)
# Pass in ftarray, shared memory handle to controller
kalman_position = PositionFilter(kalman_xHat)


watchers = dict()
for var in [hdg_input_var, rate_var, rate_var_imu, pitch_var, pitch_rate_var, roll_var, roll_rate_var, gx4_q0, gx4_q1, gx4_q2, gx4_q3]:
    watchers[var] = watcher()
    group = eval(var.__module__)
    watchers[var].watch(group)
def get(var):
    #if watchers[var].has_changed():
    #    return var.get()
    #else:
    #    return None
    return var.get()

start = time.time()
iteration = 0
while True:
    while (iteration*dt < (time.time() - start)):

        yaw_rate = get(rate_var_imu)
        pitch_rate = get(pitch_rate_var)
        roll_rate = get(roll_rate_var)
        yaw_rate_kal = get(rate_var_imu)*np.pi/180
        pitch_rate_kal = get(pitch_rate_var)*np.pi/180
        roll_rate_kal = get(roll_rate_var)*np.pi/180

        # Bugs arise due to quaternion aliasing, so we choose the quaternion
        # closest to the actual state
        actual_quat = [get(gx4_q0), get(gx4_q1), get(gx4_q2), get(gx4_q3)]
        negated_quat = [-i for i in actual_quat]
        kalman_quat = orientation_filter.x_hat[:4]

        actual_delta = [kalman_quat[i] - actual_quat[i] for i in range(4)]
        negated_delta = [kalman_quat[i] - negated_quat[i] for i in range(4)]

        quat_in = actual_quat
        if np.linalg.norm(actual_delta) > np.linalg.norm(negated_delta):
            quat_in = negated_quat

        orientation_filter.predict()
        orientation_filter.update(quat_in + [yaw_rate_kal, pitch_rate_kal, roll_rate_kal])

        # [q0, q1, q2, q3, yawrate, pitchrate, rollrate]
        data = orientation_filter.x_hat
        ypr = quat.quat_to_ypr(data[:4])

        outputs = shm.kalman.get()
        keys = ['q0', 'q1', 'q2', 'q3', 'heading_rate', 'pitch_rate', 'roll_rate']
        output = dict(zip(keys, data))
        outputs.update(**output)
        outputs.heading_rate *= 180/np.pi
        outputs.pitch_rate *= 180/np.pi
        outputs.roll_rate *= 180/np.pi
        outputs.update(**{'heading': ypr[0]*180/np.pi%360, 'pitch': ypr[1]*180/np.pi, 'roll': ypr[2]*180/np.pi})

        outputs.heading_cumulative = outputs.heading
        shm.kalman.set(outputs)


        ## Read Inputs
        #Data relative to the sub
        x_vel = -1*x_vel_in.get()
        x_acc = 0 # x_acc_in.get()
        y_vel = -1*y_vel_in.get()
        y_acc = 0 # y_acc_in.get()

        # When the DVL is tracking the surface the y velocity is reversed.
        # This is not ideal... what happens when it is not exactly inverted?
        if dvl_velocity and \
           bool(abs_heading_sub_degrees(outputs.roll, 180) < 90) ^ \
           bool(abs_heading_sub_degrees(outputs.pitch, 180) < 90):
            y_vel = -y_vel

        #depth = depth_in.get() - depth_offset.get()
        depth = depth_in.get() - 8.64
        #depth = 2.5 - shm.dvl.savg_altitude.get() 
        # Compensate for gravitational acceleration
        grav_x = sin( radians(outputs.pitch) )*9.8 # XXX: CHRIS DOES NOT LIKE (small angle approx??)
        grav_y = -sin( radians(outputs.roll) )*9.8
        gx4_grav_y = np.tan(radians(outputs.pitch))*np.sqrt(shm.gx4.accelx.get()**2 + shm.gx4.accelz.get()**2)
        gx4_grav_x = -1*np.tan(radians(outputs.roll))*shm.gx4.accelz.get()
        him_grav_y = np.tan(radians(outputs.pitch))*np.sqrt(shm.him.x_accel.get()**2 + shm.him.z_accel.get()**2)
        him_grav_x = -1*np.tan(radians(outputs.roll))*shm.him.z_accel.get()
        x_acc = x_acc - grav_x
        y_acc = y_acc - grav_y
        x_acc, y_acc = [0, 0] # temporary


        #Check whether the DVL beams are good
        beams_good = sum( [not var.get() for var in beam_vars] ) >= 2

        #beams_good = all( [not var.get() for var in beam_vars] )
        #And if not, disable them
        if not beams_good:
            active_measurements = array([0,1,0,1,1]).reshape((5,1))
        else:
            active_measurements = None

        # XXX Experimental.
        #active_measurements = array([1,0,1,0,1]).reshape((5,1))

        soft_kill = shm.switches.soft_kill.get()

        curr_thrusters = dict((t,(1-soft_kill)*shm.motor_desires.__getattribute__(t).get()) for t in thrusters)
        u = array((wrench.f_x.get(), wrench.f_y.get(), \
                   wrench.f_z.get(), wrench.t_x.get(), \
                   wrench.t_y.get(), wrench.t_z.get()))



        ## Update
        
        outputs.update(**kalman_position.update(outputs.heading, x_vel, x_acc, y_vel, y_acc, depth, u, active_measurements, curr_thrusters, outputs.pitch, outputs.roll))
       
        # This really shouldn't be necessary when kalman has a u term (which it does)
        if not beams_good and VEHICLE is "thor":
            outputs.velx = 0
            outputs.vely = 0

        ## Write outputs as group, notify only once
        shm.kalman.set(outputs)

        iteration += 1

    time.sleep(dt/5.)

#@ kalman.heading.updating = shm.kalman.heading.get() != delayed(0.5, 'shm.kalman.heading.get()')
#@ kalman.heading.valid = 0 <= shm.kalman.heading.get() < 360
#@ kalman.velx.updating = shm.kalman.velx.get() != delayed(0.5, 'shm.kalman.velx.get()')
