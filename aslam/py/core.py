import shm
import time
import math
import numpy as n
import conf.vehicle as vehicle
import conf.locale  as locale

_get_shm_in   = lambda n: getattr(shm, 'aslam_' + n + '_in')
_get_shm_out  = lambda n: getattr(shm, 'aslam_' + n + '_out')

class Wrapper:
  pass

def to_hpd(vec):
  return n.array([math.atan2(vec[1], vec[0]), math.atan2(vec[2], (vec[1] ** 2. + vec[0] ** 2.) ** 0.5), n.linalg.norm(vec)])

def gaussian(x, mu, variance):
  return math.exp( - ((x - mu) ** 2.) / (2 * variance))

class Object:
  __slots__ = ['name', 'group_in', 'group_out', 'components', 'offset']

  def __init__(self, name, components = {}):
    self.name = name
    self.components = Wrapper()
    for name, offset in components.items():
      setattr(self.components, name, Component(name, offset, self))
    self.group_in  = _get_shm_in(self.name)
    self.group_out = _get_shm_out(self.name)
    self.offset = n.array([0., 0., 0.])

  def position(self):
    north, east, depth = self.group_out.north.get(), self.group_out.east.get(), self.group_out.depth.get()
    return n.array([north, east, depth])

  def gin(self):
    return self.group_in

  def gout(self):
    return self.group_out

  def position_uncertainty(self):
    pass

  def mark_visible(self):
    self.group_in.visible.set(True)

  def mark_invisible(self):
    self.group_in.visible.set(False)

class Component(Object):
  __slots__ = ['name', 'offset', 'parent', 'group_in', 'group_out']

  def __init__(self, name, offset, parent):
    self.name, self.offset, self.parent = name, offset, parent

  def gin(self):
    return self.parent.group_in

  def gout(self):
    return self.parent.group_out

  def position(self):
    return self.parent.position() + self.offset

class Submarine(Object):
  __slots__ = ['group', 'offset', 'components']

  def __init__(self, components):
    self.group = shm.aslam_sub
    self.components = Wrapper()
    for name, offset in components.items():
      setattr(self.components, name, Component(name, offset, self))
    self.offset = n.array([0., 0., 0.])

  def position(self):  
    north, east, depth = self.group.north.get(), self.group.east.get(), self.group.depth.get()
    return n.array([north, east, depth])

  def orientation(self):
    heading, pitch, roll = self.group.heading.get(), self.group.pitch.get(), self.group.roll.get()
    return n.array([heading, pitch, roll])

  def move_to(self, position):
    shm.navigation_desires.north.set(position[0])
    shm.navigation_desires.east.set(position[1])
    shm.navigation_desires.depth.set(position[2])

class Observation:
  __slots__ = ['source', 'to', 'value', 'uncertainty', 'timestamp']

  def __init__(self, source, to, value, uncertainty, timestamp = None):
    self.source, self.to, self.value, self.uncertainty = source, to, value, uncertainty
    self.timestamp = time.time() if timestamp is None else timestamp
  
  def prior(self):
    group = self.to.gout().get()
    obj_pos = n.array([group.north, group.east, group.depth])
    obj_err = n.array([group.north_uncertainty, group.east_uncertainty, group.depth_uncertainty])
    src_pos = self.source.position()  
    delta   = obj_pos - src_pos
    hpd_mu  = to_hpd(delta)
    hpd_del = to_hpd(delta + obj_err)
    hpd_sig = abs(hpd_del - hpd_mu)
    return gaussian(self.value[0], hpd_mu[0], hpd_sig[0]) * gaussian(self.value[1], hpd_mu[1], hpd_sig[1]) * gaussian(self.value[2], hpd_mu[2], hpd_sig[2])

  def apply(self):
    group = self.to.gin().get()
    group.heading, group.pitch, group.distance = self.value
    group.heading_uncertainty, group.pitch_uncertainty, group.distance_uncertainty = self.uncertainty
    group.north_offset, group.east_offset, group.depth_offset = self.to.offset - self.source.offset
    group.timestamp = self.timestamp
    self.to.gin().set(group)

sub = Submarine(vehicle.components)
world = Wrapper()

for obj in locale.objects:
  setattr(world, obj['name'], Object(obj['name'], obj.get('components', {})))
