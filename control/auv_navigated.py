#!/usr/bin/env python3
import time
import math
import shm.navigation_settings as settings
import shm.navigation_desires as nd
import shm.desires as desires
from shm.kalman import north, east, heading
from auv_python_helpers.math_utils import inverse_clamp
from pid import PID

def main(freq=30, xPID=[2, 0, 0], yPID=[2, 0, 0],
         min_x_speed=0.2, min_y_speed=0.1, deadband=0.01):
    
    # Init position -> velocity controllers
    vel_x_out = PID(xPID[0], xPID[1], xPID[2])
    vel_y_out = PID(yPID[0], yPID[1], yPID[2])

    rate = 1/freq   
    start = time.time()
    while True:
        if (time.time() - start > rate):
            if not settings.enabled.get():
                # Make sure that the sub doesn't go crazy on enable
                nd.north.set(north.get())
                nd.east.set(east.get())
                desires.heading.set(nd.heading.get())
                desires.pitch.set(nd.pitch.get())
                desires.roll.set(nd.roll.get())
                desires.depth.set(nd.depth.get())
                desires.speed.set(nd.speed.get())
                desires.sway_speed.set(nd.sway_speed.get())
                time.sleep(rate)
                start = time.time()
                continue

            desires.heading.set(nd.heading.get())
            desires.pitch.set(nd.pitch.get())
            desires.roll.set(nd.roll.get())
            desires.depth.set(nd.depth.get())

            # Postition specific trajectories, navigation
            if settings.position_controls.get():
                delta_n = north.get() - nd.north.get()
                delta_e = east.get() - nd.east.get()

                delta_x = math.cos(math.radians(heading.get()))*delta_n + \
                          math.sin(math.radians(heading.get()))*delta_e
                delta_y = -math.sin(math.radians(heading.get()))*delta_n + \
                          math.cos(math.radians(heading.get()))*delta_e

                x_out = vel_x_out.tick(delta_x, 0)
                y_out = vel_y_out.tick(delta_y, 0)

                def condition(error, value, liveband):
                    if abs(error) > deadband:
                        return inverse_clamp(value, liveband)
                    return 0

                x_out = condition(delta_x, x_out, min_x_speed)
                y_out = condition(delta_y, y_out, min_y_speed)

                desires.speed.set(x_out)
                desires.sway_speed.set(y_out)

                if settings.optimize.get():
                    mag = math.sqrt(delta_n**2 + delta_e**2)
                    if mag > 2:
                        direction = math.atan2(-delta_e, -delta_n)
                        direction = math.degrees(direction)
                        nd.heading.set(direction)

            # Otherwise, "naively" let velocity desires fall through
            else:
                desires.speed.set(nd.speed.get())
                desires.sway_speed.set(nd.sway_speed.get())


            start = time.time()
        else:
            time.sleep(rate/2)

if __name__ == "__main__":
    main()
