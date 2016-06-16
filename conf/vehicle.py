import json
import numpy as np
import os
import sys

DIR = os.environ.get("CUAUV_SOFTWARE")
if DIR is None:
    sys.stderr.write("vehicle.py: CUAUV_SOFTWARE must be set "
                     "to the root of the software repository.\n")
    sys.exit(1)

d = None
VEHICLE = os.getenv("CUAUV_VEHICLE", "thor")
with open(os.path.join(DIR, "conf", "%s.json" % VEHICLE)) as f:
    d = json.load(f)

center_of_buoyancy = np.array(d['center_of_buoyancy'])
buoyancy_force = d['buoyancy_force']
gravity_force = d['gravity_force']
sub_height = d['sub_height']
I = np.array(d['I'])
thrusters = d['thrusters']
sensors = d['sensors']

# note: the inherit from object is needed for Python 2 compatibility
# (it makes it a 'new-style' object, which is the default in Python 3)
class DragPlane(object):
    def __init__(self, pos, normal, cD, area):
        self.pos = pos
        self.n = normal
        self.cD = cD
        self.area = area

        self.torque_hat = np.cross(self.pos, self.n)

drag_planes = []
for dp in d['drag_planes']:
    drag_planes.append(DragPlane(np.array(dp['pos']), np.array(dp['normal']), dp['cD'], dp['area']))

components = d['components']
