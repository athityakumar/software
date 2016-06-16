import pickle
import sys
import math

marks = pickle.load( file(sys.argv[1]) )
d = dict( [(name, (n, e, h, d)) for (name, n, e, h, d) in marks])

def distance(n1, n2):
    return math.sqrt( (d[n1][0] - d[n2][0])**2 + (d[n1][1] - d[n2][1])**2 )
