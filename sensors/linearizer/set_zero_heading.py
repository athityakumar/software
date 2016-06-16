#!/usr/bin/env python2
''' Utility to set current heading to be zero after linearization '''

import shm
import pickle

hdg = shm.kalman.heading.get()
FILE = "data/linearizer.data"

data = list(pickle.load(open(FILE)))
data[2] = (data[2] - hdg) % 360    # take into account previous offset
pickle.dump(data, open(FILE, "w"))

print "Changed heading by angle %s" % (-hdg)

