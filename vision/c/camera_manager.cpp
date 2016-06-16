#include <iostream>
#include <signal.h>
#include <string>
#include <vector>

#include "CaptureSource.hpp"

#ifdef UEYE
#include "UeyeCamera.hpp"
#endif

#ifdef XIMEA
#include "XimeaCamera.hpp"
#endif

// this is global to allow for signal handling, otherwise we would have to
//  capture it within main() somehow, which from what I can tell is impossible
CaptureSource *cap;

int main(int argc, char* argv[]) {
  std::vector<std::string> valid_names = {
#ifdef XIMEA
    "ximea",
#endif
#ifdef UEYE
    "ueyeleft", "ueyeright", "ueyedown",
#endif
    "guppy"
  };

  std::string all_cams;
  for (const auto& cam : valid_names) {
    all_cams += cam + " ";
  }

  if (argc < 2) {
    std::cout << "Please specify a camera to start. One of: "
              << all_cams << std::endl;
    return 1;
  }

  std::string camera_name = argv[1];


  if (camera_name == "guppy") {
    std::cout << "Guppy not implemented" << std::endl;
    return 1;
  }

#ifdef XIMEA
  else if (camera_name == "ximea") {
    cap = new XimeaCamera("forward");
  }
#endif

#ifdef UEYE
  else if (camera_name == "ueyeleft") {
    cap = new UeyeCamera("forward", 3, "ueye_forward");
  }

  else if (camera_name == "ueyeright") {
    cap = new UeyeCamera("forwardright", 2, "ueye_forward");
  }

  else if (camera_name == "ueyedown") {
    cap = new UeyeCamera("downward", 1, "ueye_downward");
  }
#endif

  else {
    std::cout << "\"" << camera_name << "\" is not a valid camera name. "
              << "Choose one of: " << all_cams << std::endl;
    return 1;
  }

  auto signal_handler = [] (int sig) {
    std::cout << "Received sigterm. Terminating capture source" << std::endl;
    cap->terminate();
  };
  signal(SIGINT, signal_handler);
  signal(SIGTERM, signal_handler);

  cap->run();

  return 0;
}
