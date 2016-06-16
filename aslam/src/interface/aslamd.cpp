#include <chrono>
#include <iostream>

#include <libshm/c/shm.h>
#include <auvlog/client.h>
#include <conf/map.hpp>

#include "../math/fastslam.cpp"

struct aslam_sub shm_aslam_sub;
struct kalman    shm_kalman;

#define AUVLOG(m) auvlog_log_stdout("aslam", m);

#define read(name) \
  name shm_aslam_##name;\
  shm_getg(name, shm_aslam_##name);\
  if(shm_aslam_##name.visible) {\
    Vec3 obs;\
    Vec3 offset;\
    Mat3 cov;\
    obs << shm_aslam_##name.heading, shm_aslam_##name.pitch, shm_aslam_##name.distance;\
    offset << shm_aslam_##name.north_offset, shm_aslam_##name.east_offset, shm_aslam_##name.depth_offset;\
    cov << shm_aslam_##name.heading_uncertainty, 0.0, 0.0,\
           0.0, shm_aslam_##name.pitch_uncertainty, 0.0,\
           0.0, 0.0, shm_aslam_##name.distance_uncertainty;\
    map.observe_hpd(map.object_indices[#name], obs, offset, cov);\
  }

#define write(name) \
  name shm_aslam_##name;\
  Vec6 pos_cov_##name = objects[#name];\
  shm_aslam_##name.north = pos_cov_##name[0];\
  shm_aslam_##name.north_uncertainty = pos_cov_##name[1];\
  shm_aslam_##name.east = pos_cov_##name[2];\
  shm_aslam_##name.east_uncertainty = pos_cov_##name[3];\
  shm_aslam_##name.depth = pos_cov_##name[4];\
  shm_aslam_##name.depth_uncertainty = pos_cov_##name[5];\
  shm_setg(name, shm_aslam_##name);

#define repeat_in(macro) \
  macro(aslam_buoy_a_in);\
  macro(aslam_buoy_b_in);\
  macro(aslam_buoy_c_in);\
  macro(aslam_buoy_d_in);

#define repeat_out(macro) \
  macro(aslam_buoy_a_out);\
  macro(aslam_buoy_b_out);\
  macro(aslam_buoy_c_out);\
  macro(aslam_buoy_d_out);

#define DEG_TO_RAD(val) val * M_PI / 180
  
using namespace cuauv;

int main(int argc, char* argv[]) {
  shm_init();
  auvlog_init();

  conf::map m = conf::load_map();

  AUVLOG("Loaded configuration file.");

  Map map (m.submarine.initial_pose, m.submarine.control_covariance, m.num_particles);

  AUVLOG("Initialized map.");

  s::for_each(
    m.objects.begin(),
    m.objects.end(),
    [&](const conf::object& o) {
      map.add_object("aslam_" + o.name + "_out", o.initial_position, o.initial_covariance);
      map.object_indices["aslam_" + o.name + "_in"] = map.object_indices["aslam_" + o.name + "_out"];
      AUVLOG("Successfully initialized object: " + o.name + ".");
    }
  );

  s::chrono::time_point<std::chrono::high_resolution_clock> prev, curr;
  s::chrono::duration<double> dur;
  double dt;
  
  Vec6 pose;
  s::map<s::string, Vec6> objects;

  prev = s::chrono::high_resolution_clock::now();

  Vec6 prev_state = Vec6::Zero();
 
  for (;;) {
    curr = s::chrono::high_resolution_clock::now();
    dur  = curr - prev;
    dt   = (double) dur.count();
    prev = curr;
    shm_getg(kalman, shm_kalman);
  
    Vec6 state;
    state <<
      shm_kalman.north,
      shm_kalman.east,
      shm_kalman.depth,
      DEG_TO_RAD(shm_kalman.heading),
      DEG_TO_RAD(shm_kalman.pitch),
      DEG_TO_RAD(shm_kalman.roll)
    ;
      
    Vec6 delta = state - prev_state;
    prev_state = state;
    
    /*
    e::Vector4d delta (
      shm_kalman.velx,
      shm_kalman.vely,
      0, // shm_kalman.depth_rate,
      0  // shm_kalman.heading_rate * M_PI / 180.0
    );

    map.step_controls(delta / dt, dt);
    */
    
    /* Temporary workaround. */
    s::for_each(
      map.particles.begin(),
      map.particles.end(),
      [&](StdParticle& p) {
        Vec6 del = p.pose + delta;
        Mat6 cov = map.control_covariance * dt;
        p.pose = multivariate_gauss(del, cov);
     }
    );
  
    repeat_in(read);

    map.step_resample();
      
    s::tie(pose, objects) = map.predict();

    repeat_out(write);

    shm_aslam_sub.north   = pose[0];
    shm_aslam_sub.east    = pose[1];
    shm_aslam_sub.depth   = pose[2];
    shm_aslam_sub.heading = pose[3];
    shm_aslam_sub.pitch   = pose[4];
    shm_aslam_sub.roll    = pose[5];

    shm_setg(aslam_sub, shm_aslam_sub);

    s::this_thread::sleep_for(s::chrono::duration<double>(0.01));

  };
};
