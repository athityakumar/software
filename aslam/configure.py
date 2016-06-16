#!/usr/bin/python

from build import ninja_common
import os

build = ninja_common.Build('aslam')

build.install('auv-aslam-test', f = 'aslam/scripts/aslam-test.sh')

build.build_cmd('auv-aslamd', [
  'src/interface/aslamd.cpp'
  ],
  deps      = ['nanomsg'],
  auv_deps  = ['shm', 'conf', 'auvlog', 'aslam'],
  pkg_confs = ['eigen3'],
  lflags    = [],
  cflags    = ['-Wno-deprecated-declarations'])

build.build_shared('aslam', [
  'src/math/fastslam.cpp'
  ],
  auv_deps  = ['shm'],
  pkg_confs = ['eigen3'],
  lflags    = [],
  cflags    = ['-Wno-deprecated-declarations'])
