# Tests that didn't neatly fit in another file. Should be deprecated eventually.

#@ sensors.him.updating = shm.him.heading.get() != delayed(0.5, 'shm.him.heading.get()')
#@ sensors.depth.updating = shm.depth.depth.get() != delayed(0.5, 'shm.depth.depth.get()')
#@ sensors.depth.not_crazy = abs(shm.depth.depth.get() - delayed(0.2, 'shm.depth.depth.get()')) < 0.2
#@ thor.sensors.pressure.valid = .7 < shm.pressure.hull.get() < .8
#@ loki.sensors.pressure.valid = .7 < shm.pressure.hull.get() < .8
#@ sensors.pressure.updating = shm.pressure.hull.get() != delayed(0.5, 'shm.pressure.hull.get()')

#@ thor.merge.total_voltage.ok = 26.0 > shm.merge_status.total_voltage.get() > 21.0
#@ thor.merge.total_current.ok = 30.0 > shm.merge_status.total_current.get() > 2.0
#@ thor.merge.voltage_port.ok = 26.0 > shm.merge_status.voltage_port.get() > 21.0
#@ thor.merge.voltage_starboard.ok = 26.0 > shm.merge_status.voltage_starboard.get() > 21.0

#@ thor.serial.actuator.connected = shm.connected_devices.actuator.get()
#@ thor.serial.gpio.connected = shm.connected_devices.gpio.get()
#@ thor.serial.him.connected = shm.connected_devices.him.get()
#@ thor.serial.merge.connected = shm.connected_devices.merge.get()
#@ thor.serial.thruster.connected = shm.connected_devices.thruster.get()

#@ loki.serial.minipower.connected = shm.connected_devices.minipower.get()
#@ loki.serial.minithruster.connected = shm.connected_devices.minithruster.get()
#@ loki.serial.powerDistribution.connected = shm.connected_devices.powerDistribution.get()
#@ loki.serial.sensuator.connected = shm.connected_devices.sensuator.get()
