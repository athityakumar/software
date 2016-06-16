# Python modules
import mmap
import struct
import sys
import numpy

from misc.log import with_logging

#Maps CAVE representation of cameras to the strings
#used for Posix IPC (the camera names within cave_test).
#This may be useful if these vision names are ever changed.
camera_map = {"Forward": "Forward",
              "Downward": "Downward"
             }

#Default resolutions for cameras; necessary for initializing shared memory
#Improper resolutions may result in a bus error when vision is run
resolutions = {"Forward": (1024, 768),
               "Downward": (640, 480)}

# Third-party modules
POSIX_IPC_LOADED = True
try:
    import posix_ipc
except ImportError, ie:
    POSIX_IPC_LOADED = False
    sys.stderr.write('''\033[93m
        ERROR: The posix_ipc module could not be found. This module is required
        to use the vision tester. For installation directions, see: \033[94m
        https://cuauv.org/wiki/Software/Linux_Dependencies#Simulator_Dependencies
        \033[0m\n''')
    sys.exit(0)

@with_logging
class CameraLink:

    @classmethod
    def preinit(cls):
        #Create shared memory blocks for all cameras (so that vision
        #can be started before frames are exported)
        for c in camera_map.keys():
            #Frame details do not matter since all we need to do is
            #create a shared memory block
            res = resolutions[c]
            dummy = cls(c, height=res[1], width=res[0], nChannels=3)
        cls.log.info("Shared memory initialized for vision output")

    # Initialize a camera link with the given frame dimensions 
    def __init__(self, name, height=None, width=None, nChannels=None):
        self.name = camera_map[name]
        self.height = height
        self.width = width
        self.nChannels = nChannels
    
        self.dataSize = self.height * self.width * self.nChannels

        self.currentFrame = 0
   
        #Init shared memory
        self.initializeIpc()

    def initializeIpc(self):

        # This Struct gives the format for the 128-byte shared mem header.
        # The header contains the index of the current valid image (1 or 0),
        # the number of channels, width, height, and the offset in to the
        # shared memory file of each image.
        self.header = struct.Struct('HHHHII')

        # Create the shared memory and semaphore. The shared memory is large
        # enough to contain two RGBA images for double-buffering.
        memory = posix_ipc.SharedMemory('/'+self.name+'Shm', posix_ipc.O_CREAT,
                     size=(self.header.size + 2 * self.dataSize))

        # Create semaphores. SemQ is a producer-consumer style semaphore. The
        # camera will release it each time a new image is ready.
        self.semQ = posix_ipc.Semaphore('/'+self.name+'SemQ',
                        posix_ipc.O_CREAT, initial_value=0)

        self.mapfile = mmap.mmap(memory.fd, memory.size)
        memory.close_fd()
        self.mapfile.seek(0)

        self.mapfile.write(self.header.pack(
                0, self.nChannels, self.width, self.height,
                self.header.size, self.header.size + self.dataSize))


    # Sends a frame (of the same dimensions this camera link was initialized
    # with) to the vision daemon
    def send_image(self, frame):

        frame = frame.flatten() #make array 1-dimensional

        self.mapfile.seek(self.header.size + self.currentFrame * self.dataSize)
        if (len(frame) != self.dataSize):
            self.log.error("FRAME SIZE ASSERTION")
            return

        self.mapfile.write(frame.tostring())

        # If no one has consumed the last image yet, eat it since we're about
        # to write over it.
        try:
            self.semQ.acquire(0)
        except posix_ipc.BusyError, e:
            pass

        # Update the image pointer.
        self.mapfile.seek(0)
        self.mapfile.write(self.header.pack(
            self.currentFrame, self.nChannels, self.width, self.height,
            self.header.size, self.header.size + self.dataSize))
        self.semQ.release()
        if self.currentFrame == 0:
            self.currentFrame = 1
        else:
            self.currentFrame = 0
