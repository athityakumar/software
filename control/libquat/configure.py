#!/usr/bin/python

from build import ninja_common

build = ninja_common.Build("control/libquat")
build.build_c_shared('quat', ['quat.c'])
