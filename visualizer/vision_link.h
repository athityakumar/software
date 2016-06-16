#ifndef _VISION_LINK_H_
#define _VISION_LINK_H_

#include <string>
#include <chrono>

class timespec;

class VisionLink {
  public:
    virtual ~VisionLink() {}
    virtual int init(const std::string &cam_name, unsigned int width,
                                                  unsigned int height) = 0;
    virtual void post(unsigned char *image, timespec *acq_time) = 0;
};

#endif
