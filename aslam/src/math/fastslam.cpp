#include "fastslam.h"

template<typename T>
s::vector<T> scan_sum(s::vector<T> vec) {
  T sum = 0;
  s::vector<T> ret;
  s::for_each(
    vec.begin(),
    vec.end(),
    [&](T& x) {
      sum += x;
      ret.push_back(sum);
    }
  );
  return ret;
};

inline double heading_diff(double x, double y) {
  double diff = fmod(x - y, 2 * M_PI);
  return diff > M_PI ? diff - (2 * M_PI) : diff;
};

template<typename X, typename Y>
X multivariate_gauss(const X& mean, const Y& covariance) {
  X rnd = X::Zero();
  
  double min = -1.0;
  double max = 1.0;

  for (int i = 0; i < mean.size(); i++) {
    rnd[i] = min + ((double) (rand() / (double) RAND_MAX) * (max - min));
  };

  return (covariance * rnd) + mean;
};

template<typename X, typename Y>
Particle<X, Y>::Particle(const X& initial_pose, double initial_weight) {
  this->pose   = initial_pose;
  this->weight = initial_weight;
};

template<typename X, typename Y>
Particle<X, Y>::Particle(const Particle& other) {
  this->pose    = other.pose;
  this->objects = s::vector<Y> (other.objects);
  this->weight  = other.weight;
};

template<typename X, typename Y>
Particle<X, Y>::~Particle () {
};

Map::Map(const Vec6& initial_pose, const Mat6& control_covariance, int num_particles) {
  this->control_covariance = control_covariance;
  this->object_index = 0;

  for (int i = 0; i < num_particles; i++) {
    this->particles.push_back(StdParticle(initial_pose, 1.0));
  };
};

void Map::add_object(s::string name, const Vec3& initial_position, const Mat3& initial_covariance) {
  this->object_indices[name] = this->object_index;
  this->object_index++;
  s::for_each(
    this->particles.begin(),
    this->particles.end(),
    [&](StdParticle& p) {
      p.objects.push_back(EKF3(initial_position, initial_covariance));
    }
  );
};

void Map::step_controls(const Vec6& rate, double dt) {
  Vec6 delta      = dt * rate;
  Mat6 covariance = dt * this->control_covariance;
  s::for_each(
    this->particles.begin(),
    this->particles.end(),
    [&](StdParticle& p) {
      Vec6 prev = p.pose;
      Vec6 real_delta = multivariate_gauss(delta, covariance);
      double heading = prev[3] + real_delta[3];
      double pitch   = prev[4] + real_delta[4];
      double roll    = prev[5] + real_delta[5];
      p.pose <<  prev[0] + real_delta[0] * cos(heading),
                 prev[1] + real_delta[1] * sin(heading),
                 prev[2] + real_delta[2],
                 heading,
                 pitch,
                 roll;
    }
  );
};

void Map::step_resample() {
  double sum = s::accumulate(
    this->particles.begin(),
    this->particles.end(),
    0.0,
    [](auto x, auto y) { return x + y.weight; }
  );
  s::vector<double> weights;
  s::for_each(
    this->particles.begin(),
    this->particles.end(),
    [&](StdParticle& p) {
      p.weight /= sum;
      weights.push_back(p.weight);
    }
  );
  s::vector<double> cumulative = scan_sum(weights); 
  s::vector<int> selected;
  for (unsigned int ind = 0; ind < weights.size(); ind++) {
    double threshold = static_cast<double>(ind) / static_cast<double>(weights.size());
    for (unsigned int wind = 0; wind < cumulative.size(); wind ++) {
      if (cumulative[wind] > threshold) {
        selected.push_back(wind);
        break;
      };
    };
  };
  s::vector<StdParticle> old = this->particles;
  this->particles.clear();
  s::for_each(
    selected.begin(),
    selected.end(),
    [&](int index) {
      this->particles.push_back(StdParticle(old[index]));
    }
  );
  assert(old.size() == this->particles.size());
};

void Map::observe_hpd(int index, const Vec3& obs, const Vec3& offset, const Mat3& cov) {
  this->observe(
    index,
    /* 
      Observation Function: 
      Heading = atan2(dy, dx) - h
      Pitch = atan2(dz, dxy)
      Distance = dxyz 
      
    */
    [&](const Vec6& pose, const Vec3& pos) {
      Vec3 del (pos[0] - pose[0], pos[1] - pose[1], pos[2] - pose[2]);
      Vec2 ray (del[0], del[1]);
      Vec3 rel (
        heading_diff(atan2(del[1], del[0]), pose[3]),
        atan2(-del[2], ray.norm()),
        del.norm()
      ); 
      return rel;
    },
    [&](const Vec6& pose, const Vec3& pos) {
      /*
         Jacobian: partial derivatives of obs func w.r.t. position
         ph/px ph/py ph/pz
         pp/px pp/py pp/pz
         pd/px pd/py pd/pz
         ...
      */
      Vec3 del (pos[0] - pose[0], pos[1] - pose[1], pos[2] - pose[2]);
      Mat3 jac;
      Vec2 ray (del[0], del[1]);
      double del_norm = del.norm();
      double ray_norm = ray.norm();
      double temp = s::pow(ray_norm, 2) + s::pow(del[2], 2);
      double denom = temp * ray_norm;
      jac << -del[1] / ray_norm, del[0] / ray_norm, 0,
             -(del[2] * del[0]) / denom, -(del[2] * del[1]) / denom, -ray_norm / temp,
             del[0] / del_norm, del[1] / del_norm, -del[2] / del_norm;
      return jac;
    },
    obs,
    cov
  );
};

template<typename X, typename Y, typename A, typename B>
void Map::observe(int index, A observation_func, B observation_jacobian, X observation, Y covariance) {
  s::for_each(
    this->particles.begin(),
    this->particles.end(),
    [&](StdParticle& p) {
      p.objects[index].update(
        [&](const Vec3& pos) { return observation_func(p.pose, pos); },
        [&](const Vec3& pos) { return observation_jacobian(p.pose, pos); },
        observation,
        covariance
      );
      double norm = p.objects[index].residual.norm();
      p.weight /= 1 + norm;
      // +1 to get rid of some nasty infinities when residuals are zero.
      // ^ This isn't official but it seems to me that it should work. Just has to be relative.
      // Other potential option: https://github.com/yglee/FastSLAM/blob/master/cpp/fastslam1/compute_weight.cpp
    }
  );
};

s::tuple<Vec6, s::map<s::string, Vec6>> Map::predict() {
  Vec6 est_pose = Vec6::Zero();
  s::vector<Vec6, e::aligned_allocator<Vec6>> temp;
  
  for (unsigned int i = 0; i < this->object_indices.size(); i++) {
    temp.push_back(Vec6::Zero());
  };

  double mul = 1.0 / (static_cast<double>(this->particles.size()));

  s::for_each(
    this->particles.begin(),
    this->particles.end(),
    [&](const StdParticle& p) {
      est_pose += p.pose * mul;
      for (unsigned int i = 0; i < temp.size(); i++) {
        temp[i][0] += p.objects[i].mean[0] * mul;
        temp[i][1] += p.objects[i].covariance(0, 0) * mul;
        temp[i][2] += p.objects[i].mean[1] * mul;
        temp[i][3] += p.objects[i].covariance(1, 1) * mul;
        temp[i][4] += p.objects[i].mean[2] * mul;
        temp[i][5] += p.objects[i].covariance(2, 2) * mul;
      };
      // TODO fix for headings
    }
  );  

  s::map<s::string, Vec6> objmap;
  for (const auto& kv : this->object_indices) {
    objmap[kv.first] = temp[kv.second];
  }
  return std::make_tuple(est_pose, objmap);
};
