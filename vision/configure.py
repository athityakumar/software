#!/usr/bin/python
from build import ninja_common
import os

build = ninja_common.Build('vision')

build.install('auv-visiond', f='vision/visiond.py')

build.install('auv-vision-gui', f='vision/gui/server.py')

build.build_shared('auv-camera-message-framework', ['c/camera_message_framework.cpp'], deps=['pthread'], auv_deps=['utils'])

build.build_shared('auv-camera-filters', ['c/camera_filters.cpp'], pkg_confs=['opencv'], auv_deps=['utils'])

build.build_cmd('auv-firewire-daemon', ['c/firewire_camera.cpp'], deps=['dc1394'], auv_deps=['auv-camera-message-framework'], pkg_confs=['opencv'])

build.build_cmd('auv-cams', ['gui/cams/cams.cpp'], pkg_confs=['opencv'], auv_deps=['auv-camera-message-framework'])

camera_apis = { "ueye.h" : ("UEYE", "UeyeCamera.cpp", "ueye_api"),
                "m3api/xiApi.h" : ("XIMEA", "XimeaCamera.cpp", "m3api")
              }
extra_sources = []
cflags = []
deps = []
for incl, (define, src, lib) in camera_apis.items():
  include_full_path = os.path.join("/usr/include", incl)
  if os.path.isfile(include_full_path):
    extra_sources.append("c/%s" % src)
    cflags.append("-D%s" % define)
    deps.append(lib)
  else:
    print("Could not build capture source for \"%s\" camera because you are missing \"%s\"." % (define, include_full_path))

build.build_cmd('auv-camera', ["c/camera_manager.cpp"] + extra_sources,
                cflags=cflags, deps=deps, pkg_confs=['opencv'],
                auv_deps=['utils', 'auv-camera-message-framework',
                          'auv-camera-filters', 'shm'])
