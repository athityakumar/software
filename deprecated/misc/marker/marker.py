#!/usr/bin/env python2

"""
A simple utility to grab points while driving around.

Input mark names to add the current sub position as a mark.
Control+C to kill the process and write files out to "marks_output".
Marks can be read by un-pickle-ing them (see the pickle library reference).
"""

import shm

north = shm.kalman.north
east = shm.kalman.east
heading = shm.kalman.heading
depth = shm.kalman.depth

marks = []

try:
    while(True):
        tag = raw_input(">")

        if tag == "quit":
            break
        
        marks.append( (tag, north.get(), east.get(), heading.get(), depth.get()) )
except KeyboardInterrupt:
    pass

import pickle
pickle.dump( marks, file("marks_output", "w") )
print "Marker log written"

import pylab
xs = [x[1] for x in marks]
ys = [x[2] for x in marks]
sizes = range(1,len(xs)+1)
pylab.scatter(xs, ys, s=sizes)
pylab.show()
