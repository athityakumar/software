import numpy
import pickle

data = pickle.load(open("data/linearizer.data",'r'))
actual = data[0]
readings = data[1]['3dmg']
offset = data[2]

#linearized = [data[key] for key in sorted(data.keys())]

scale = 360./len(readings)

readings = sorted(zip(readings, scale*numpy.arange(len(readings))),
                    key = lambda pair: -pair[1])

def cmp_headings(h1, h2):
    '''returns 1,0,-1 as comparison of the headings
    -1 is h1 < h2, 1 is h1 > h2'''
    if (h1-h2) % 360. == 0:
        return 0
    elif diff(h2, h1) > 0:
        return 1
    else:
        return -1

def Invert(reading, offset=0.0):
    '''Takes an actual heading and determines which reading
    corresponded to it by looking in the list of readings.
    readings is a list of pairs (reading, heading) from 0 to 360.'''

    #Find where the readings cross over the heading
    n = 0
    below = False
    for i,(r,h) in enumerate(readings):
        if cmp_headings(r, reading) <= 0:
            below = True
        elif below:
            break
        n = i
    belowR,belowH = readings[n]
    
    aboveR,aboveH = readings[(n+1)%len(readings)]

    coeff = diff(belowR, reading) / diff(belowR, aboveR)
    return (diff(belowH, aboveH)*coeff + belowH - offset)%360

def linearize(reading):
    #below = int(numpy.floor(reading/scale) % len(linearized))
    #above = int(numpy.ceil(reading/scale) % len(linearized))
    #m = linearized[below]
    #M = linearized[above]
    #d = diff(m, M)
    #t = reading/scale - below

    #inverted = m + d*t

    #return inverted

    return 360 - Invert(reading, offset)

def to180(d):
    if d > 180.:
        return d-360.
    else:
        return d
def diff(x, y):
    return to180( (y-x)%360. )
