#pragma once

#define _USE_MATH_DEFINES

#include <thread>
#include <tuple>
#include <algorithm>
#include <vector>
#include <map>
#include <string>
#include <numeric>
#include <iostream>
#include <cassert>
#include <cmath>

#include <Eigen/Dense>
#include <Eigen/StdVector>

// C++ templates, sheesh - http://stackoverflow.com/questions/495021/why-can-templates-only-be-implemented-in-the-header-file

#include "ekf.cpp" // TODO TRY CHANGING

typedef e::Matrix<double, 6, 1> Vec6;
typedef e::Matrix<double, 6, 6> Mat6;
typedef e::Matrix<double, 3, 1> Vec3;
typedef e::Matrix<double, 3, 3> Mat3;
typedef e::Matrix<double, 2, 1> Vec2;
typedef e::Matrix<double, 2, 2> Mat2;

typedef EKF<Vec3, Mat3, bool, bool, Vec3, Mat3> EKF3;

namespace e = Eigen;
namespace s = std;

template<typename X, typename Y>
X multivariate_gauss(const X& mean, const Y& covariance);

template<typename X, typename Y>
class Particle {
  public:
    Particle(const X& initial_pose, double initial_weight);
    Particle(const Particle& other);
    ~Particle();

    X pose;

    s::vector<Y> objects;

    /* Particle Weight */
    double weight;

    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
};

typedef Particle<Vec6, EKF3> StdParticle;

class Map {
  public:
    Map(const Vec6& initial_pose, const Mat6& control_covariance, int num_particles);

    void add_object(s::string name, const Vec3& initial_position, const Mat3& initial_covariance);

    void observe_hpd(int index, const Vec3& obs, const Vec3& offset, const Mat3& cov);

    template<typename X, typename Y, typename A, typename B>
    void observe(int index, A observation_func, B observation_jacobian, X observation, Y covariance);

    /* 
      Iterate over particles, apply current motion prediction (velocity * dt). 
    */
    void step_controls(const Vec6& rate, double dt); // Ref 1. [6]
 
    /* 
      Integrate over possible object positions, multiply previous prior by probability given observation.
       Apparently this is closed-form for a Gaussian.
    */
    void step_resample(); // Ref 1. [7]

    s::tuple<Vec6, s::map<s::string, Vec6>> predict();
 
    s::vector<Particle<Vec6, EKF3>> particles; 
    s::map<s::string, int> object_indices;
    int object_index;

    Mat6 control_covariance;

    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
};
