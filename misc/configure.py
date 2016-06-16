#!/usr/bin/python

from build import ninja_common
build = ninja_common.Build('misc')

build.install('auv-led', f='misc/led.py')

build.install('cams')

build.build_shared('utils', ['utils.cpp'])

build.build_cmd('auv-human-depth', ['human-depth.cpp'],
        auv_deps=['shm'])

build.install("auv-build-chicken", "misc/auv-build-chicken.sh")

build.install("auv-sim-defaults", "misc/sim_defaults.py")
build.install("auv-simulate", "misc/start_sim.sh")
build.install("auv-terminal", "misc/auv_terminal.sh")
build.install("auv-quicktest", "misc/quick-test.sh")
build.install("auv-pingalert", "misc/pingalert/pingalert.py")
