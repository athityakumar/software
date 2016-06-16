#!/usr/bin/env python2
import argparse
import pickle

'''
Generates a layout file from a marker file
'''

ap = argparse.ArgumentParser(description='')
ap.add_argument('marker', type=str, help='filename of the marker generated output')
args = vars(ap.parse_args())

m = open(args["marker"], "r")

mar = pickle.load(m)

isx = "Marker output from file %s" % args["marker"]
print isx + "\r\n" + ("-" * len(isx)) 

ear = []

for (name,north,east,heading,depth) in mar:
    e = "===%s===\r\n" % name 
    e += "Coords:  %.2fN, %.2fE\r\n" % (north, east)
    e += "Depth:   %.2fM\r\n" % depth
    e += "Heading: %.2f%s\r\n" % (heading, (u"\N{DEGREE SIGN}"))
    ear.append(e)

print ("---\r\n".join(ear))


