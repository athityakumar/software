#!/usr/bin/env python2

import shm
from LUTlinearizer import linearize

group = shm.threedmg

heading_input = group.heading
heading_output = shm.linear_heading.heading

watcher = shm.watchers.watcher()
watcher.watch(group)

while 1:
    heading_output.set(linearize(heading_input.get()))
    watcher.wait()
