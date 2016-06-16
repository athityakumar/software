import math


def ypr_to_quat(ypr):
    [y, p, r] = ypr
    q0 = math.cos(r/2)*math.cos(p/2)*math.cos(y/2) + math.sin(r/2)*math.sin(p/2)*math.sin(y/2)
    q1 = math.sin(r/2)*math.cos(p/2)*math.cos(y/2) - math.cos(r/2)*math.sin(p/2)*math.sin(y/2)
    q2 = math.cos(r/2)*math.sin(p/2)*math.cos(y/2) + math.sin(r/2)*math.cos(p/2)*math.sin(y/2)
    q3 = math.cos(r/2)*math.cos(p/2)*math.sin(y/2) - math.sin(r/2)*math.sin(p/2)*math.cos(y/2)
    return [q0, q1, q2, q3]


def xyz_to_quat(xyz):
    [p, r, y] = xyz
    return ypr_to_quat([y, p, r])


def quat_to_ypr(quat):
    [q0, q1, q2, q3] = quat
    y = math.atan2(2*(q0*q3 + q1*q2), 1-2*(q2*q2 + q3*q3))
    r = math.atan2(2*(q0*q1 + q2*q3), 1-2*(q1*q1 + q2*q2))
    test = q0*q2 - q3*q1
    if test > .5:
        test = .5
    if test < -.5:
        test = -.5
    p = math.asin(2*test)
    return [y, p, r]

def quat_to_xyz(quat):
    [z, x, y] = quat_to_ypr(quat)
    return [x, y, z]


def ypr_degrees(ypr):
    return [i*180/math.pi for i in ypr]


def add_quat(q, d):
    q0 = q[0]*d[0] - q[1]*d[1] - q[2]*d[2] - q[3]*d[3]
    q1 = q[1]*d[0] + q[0]*d[1] - q[3]*d[2] + q[2]*d[3]
    q2 = q[2]*d[0] + q[3]*d[1] + q[0]*d[2] - q[1]*d[3]
    q3 = q[3]*d[0] - q[2]*d[1] + q[1]*d[2] + q[0]*d[3]
    return [q0, q1, q2, q3]


def print_deg(r):
    print([x*180/math.pi for x in r])


def normalize_quat(quat):
    magnitude = math.sqrt(sum(i**2 for i in quat))
    try:
        return [i/magnitude for i in quat]
    except:
        return [1, 0, 0, 0]

def hamilton(x, y):
    a1 = x[0]
    b1 = x[1]
    c1 = x[2]
    d1 = x[3]
    a2 = y[0]
    b2 = y[1]
    c2 = y[2]
    d2 = y[3]
    ao = a1*a2 - b1*b2 - c1*c2 - d1*d2
    bo = a1*b2 + b1*a2 + c1*d2 - d1*c2
    co = a1*c2 - b1*d2 + c1*a2 + d1*b2
    do = a1*d2 + b1*c2 - c1*b2 + d1*a2
    return [ao, bo, co, do]

def conj(q):
    return [q[0], -q[1], -q[2], -q[3]]


