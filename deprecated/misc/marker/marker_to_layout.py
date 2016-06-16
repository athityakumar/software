#!/usr/bin/env python2
import argparse
import pickle

'''
Generates a layout file from a marker file
'''

ap = argparse.ArgumentParser(description='')
ap.add_argument('marker', type=str, help='filename of the marker generated output')
ap.add_argument('layout', type=str, help='filename of the layout file to be written')
ap.add_argument('-n', dest='north', type=float, help='north coordinate for "start"', required=False, default=0)
ap.add_argument('-e', dest='east', type=float, help='east coordinate for "start"', required=False, default=0)
args = vars(ap.parse_args())

m = open(args["marker"], "r")
l = open(args["layout"], "w")

mar = pickle.load(m)

layout = {}
for (name,north,east,heading,depth) in mar:
    print "Element %s is at %.1fN, %.1fE" % (name, north, east)
    layout[name] = (north, east)

ns = args["north"]
es = args["east"]

if (ns != 0 or es != 0) and "start" in layout.keys():
    print "Remapping \"start\" to %.1fN, %.1fE" % (ns, es)
    (on, oe) = layout["start"]
    for (name, (n,e)) in zip(layout.keys(), layout.values()):
        layout[name] = (n-on+ns, e-oe+es)

pickle.dump(layout, l)

print "Layout file written"

