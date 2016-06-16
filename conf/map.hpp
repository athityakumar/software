#pragma once

#include <string>
#include <vector>

#include <Eigen/Dense>

namespace cuauv {
namespace conf {

namespace e = Eigen;
namespace s = std;

struct object {
  s::string name;
  e::Vector3d initial_position;
  e::Matrix3d initial_covariance;
};

struct sub {
  e::Matrix<double, 6, 1> initial_pose;
  e::Matrix<double, 6, 6> control_covariance;
};

struct map {
  sub submarine;
  s::vector<object> objects;
  int num_particles;
};

/** Loads map from CUAUV_LOCALE environment variable. 
 * @throws s::runtime_error if file cannot be read.
 **/
map load_map(void);

}
}
