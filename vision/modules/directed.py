import time
import os
import sys
import socket
import struct

import cv2

from vision.modules import ModuleBase
from vision import options
from vision import vsp_client
import logger

fps_weight_ratio = 0.1

class DirectedModule(ModuleBase.ModuleBase):
    def __init__(self, direction, auvlog, save_video_log=True):
        super().__init__()
        self.time_per_frame = 0
        self.last_time = time.time()
        self.auvlog = auvlog
        self.save_video_log = save_video_log
        if save_video_log:
            self.video_writer = logger.VideoWriter(direction)
        self.direction = direction
        self.image_quality = 50
        self.address = '224.0.1.1'
        self.port = vsp_client.direction_port_map[direction]
        try:
            self.socket = s = socket.socket(type=socket.SOCK_DGRAM)
            s.bind(('', 0))
            s.setsockopt(socket.IPPROTO_IP, socket.SO_REUSEADDR, True)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                         socket.inet_aton('192.168.0.93'))
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            self.has_socket = True
        except:
            self.has_socket = False
            self.auvlog.warn('Could not initialize multicast in {}'.format(direction))

    def process(self, mat):
        _, jpeg = cv2.imencode('.jpg', mat, (cv2.IMWRITE_JPEG_QUALITY,
                                             self.image_quality))
        if self.has_socket:
            mbytes = jpeg.tobytes()
            if len(mbytes) > 65535:
                self.image_quality -= 1
            else:
                self.socket.sendto(struct.pack('L', self.acq_time), 0, (self.address, self.port))
                self.socket.sendto(mbytes, 0, (self.address, self.port))

        self.post(self.direction, mat)
        self.time_per_frame = self.time_per_frame * (1 - fps_weight_ratio) + (time.time() - self.last_time) * fps_weight_ratio

        self.auvlog('{} fps: {:.1f}'.format(self.direction, 1 / self.time_per_frame), True)
        if self.save_video_log:
            self.video_writer.log_image(mat)
        self.last_time = time.time()
