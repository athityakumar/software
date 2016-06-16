/*
    The CUAUV Visualizer uses OpenGL 3.x to render models in a 3D
    environment. The models are used to convey important information about
    the vehicle's state.

    TODO:
        show things other than orientation (e.g. velocity, desires, thrusters)
        more shaders
        normal mapping / bump mapping
        water
        fonts
        make a menu (press ESC)
        add sounds
        HUD
        etc.

      Technical:
        Shaders should be shared among renderers.
        Use Uniform Buffer Objects.
        Memory de allocation in the GPU.

    Resources:
        http://ogldev.atspace.co.uk/www/tutorial23/tutorial23.html
        http://fabiensanglard.net/shadowmapping/index.php
        http://en.wikibooks.org/wiki/OpenGL_Programming/Glescraft_4
        the cs 4620 course repo
        and many more...

    Authors:
      Alex Spitzer
      Daryl Sew
*/

#define VERSION "2.1"

#include <cmath>
#include <csignal>
#include <cstdio>
#include <ctime>
#include <dlfcn.h>
#include <functional>
#include <memory>
#include <unordered_map>
#include <vector>

#include <GLFW/glfw3.h>
#if (GLFW_VERSION_MAJOR == 3 && GLFW_VERSION_MINOR < 2)
// Warning?
#else
#define ENABLE_FULLSCREEN_TOGGLE
#endif

#define GLM_FORCE_RADIANS
#include <glm/vec3.hpp>
#include <glm/gtc/quaternion.hpp>
#include <glm/gtx/rotate_vector.hpp>

#if (GLM_VERSION_MINOR == 9 && GLM_VERSION_PATCH <= 5)
#error "Visualizer requires GLM 0.9.6 or newer. https://github.com/g-truc/glm/releases"
#endif

#include <libconfig.h++>
#if (LIBCONFIGXX_VER_MAJOR == 1 && LIBCONFIGXX_VER_MINOR <= 4)
#error "Visualizer requires libconfig++ 1.5.0 or newer. https://github.com/hyperrealm/libconfig/releases"
#endif

#include <libshm/c/dynamic.h>
#include <libshm/c/shm.h>
#include <misc/utils.h>

#include "fishbowl_comm.h"
#include "keyboard.h"
#include "vision_link.h"

#include "graphics_engine/gl_utils.h"
#include "graphics_engine/graphics_engine.h"

#define BIN2DATA "../models/"     // Relative path from binary to model of sub
#define BIN2TEXTURES "../textures/"
#define BIN2CONFIG "../"
#define VISION_LINK_LIB "libvision_link.so"

#define DEFAULT_CONFIG "world.cfg"
#define DEFAULT_SKYBOX "city"
#define DEFAULT_WIDTH 512
#define DEFAULT_HEIGHT 512

#define TARGET_FPS 60

#define radians(deg) ((M_PI * (deg)) / 180)

// Heading, pitch, and roll are in degrees.
auto quat_from_hpr(float heading, float pitch, float roll) {
  heading = radians(heading) / 2.0;
  pitch = radians(pitch) / 2.0;
  roll = radians(roll) / 2.0;

  glm::fquat q;
  q.w = cos(roll)*cos(pitch)*cos(heading) + sin(roll)*sin(pitch)*sin(heading);
  q.x = sin(roll)*cos(pitch)*cos(heading) - cos(roll)*sin(pitch)*sin(heading);
  q.y = cos(roll)*sin(pitch)*cos(heading) + sin(roll)*cos(pitch)*sin(heading);
  q.z = cos(roll)*cos(pitch)*sin(heading) - sin(roll)*sin(pitch)*cos(heading);
  return q;
}

auto NORTH = glm::vec3(1, 0, 0);
auto UP = glm::vec3(0, 0, -1);

std::unordered_map<std::string, std::unique_ptr<cuauv::dshm::Group>> shm_groups;
bool add_shm_group(const std::string &group_name,
                   std::vector<std::string> var_reqs={}) {
  if (shm_groups.find(group_name) == shm_groups.end()) {
    std::unique_ptr<cuauv::dshm::Group> shm_group_new;
    try {
      shm_group_new = cuauv::dshm::newGroup(group_name);
    }
    catch (std::invalid_argument e) {
      fprintf(stderr, "ERROR: SHM group \"%s\" doesn't exist.\n",
              group_name.c_str());
      return false;
    }

    shm_groups[group_name] = std::move(shm_group_new);
  }

  auto shm_group = shm_groups[group_name].get();
  for (const auto &var_str : var_reqs) {
    try {
      shm_group->var(var_str);
    }
    catch (std::invalid_argument e) {
      fprintf(stderr, "ERROR: SHM group \"%s\" doesn't have required "
                      "variable \"%s\".\n",
              group_name.c_str(), var_str.c_str());
      return false;
    }
  }

  return true;
}

auto get_shm_group_hpr(cuauv::dshm::Group *shm_group) {
  float heading = shm_group->var("heading")->shmDouble();
  float pitch = shm_group->var("pitch")->shmDouble();
  float roll = shm_group->var("roll")->shmDouble();
  return quat_from_hpr(heading, pitch, roll);
}

auto get_shm_group_quat(cuauv::dshm::Group *shm_group) {
  glm::fquat q;
  q.w = shm_group->var("q0")->shmDouble();
  q.x = shm_group->var("q1")->shmDouble();
  q.y = shm_group->var("q2")->shmDouble();
  q.z = shm_group->var("q3")->shmDouble();
  return q;
}

auto get_shm_group_position(cuauv::dshm::Group *shm_group) {
  return glm::vec3(shm_group->var("north")->shmDouble(),
                   shm_group->var("east")->shmDouble(),
                   shm_group->var("depth")->shmDouble());
}

/*glm::fquat get_force_quat() {
  glm::vec3 force = glm::vec3(shm_get_control_internal_wrench_f_y(),
                             -shm_get_control_internal_wrench_f_z(),
                              shm_get_control_internal_wrench_f_x());
  return glm::rotation(glm::normalize(force), glm::vec3(0, 0, 1));
}*/

/*glm::vec3 get_force_scale() {
  glm::vec3 force = glm::vec3(shm_get_control_internal_wrench_f_x(),
                             -shm_get_control_internal_wrench_f_z(),
                              shm_get_control_internal_wrench_f_y());
  return glm::vec3(glm::length(force), 1, 1);
}*/

std::vector<std::unique_ptr<SceneObject>> scene_objects;
SceneObject *sub = nullptr;

Camera cam;
Light light1;
Light light2;

struct SubCamera {
  std::unique_ptr<Camera> cam;
  glm::vec3 offset_p;
  glm::fquat offset_q;
  VisionLink *vision_link;
};

std::vector<struct SubCamera> sub_cameras;

enum State {
  MOUSE,
  FIXED,
  STATES
};

std::function<void (GLFWwindow *, double, double)> mouse_handlers[STATES];
State mouse_state;

bool first_person = false;
bool sub_follow = false;
// Used only during sub follow mode.
float cam_angle = 0.0;

bool heading_lock = false;

std::function<VisionLink *(void)> create_link;
std::function<void *(VisionLink *)> destroy_link;
int load_vision_link_lib() {
  void *handle = dlopen((getBinDir() + VISION_LINK_LIB).c_str(), RTLD_LAZY);
  if (!handle) {
    fprintf(stderr, "ERROR: Could not load vision link lib: %s\n", dlerror());
    return -1;
  }

  create_link = reinterpret_cast<VisionLink *(*)()>(dlsym(handle, "create_link"));
  if (!create_link) {
    fprintf(stderr, "ERROR: Could not find create_link symbol in vision link lib.\n");
    return -1;
  }

  destroy_link = reinterpret_cast<void *(*)(VisionLink *)>(dlsym(handle, "destroy_link"));
  if (!destroy_link) {
    fprintf(stderr, "ERROR: Could not find destroy_link symbol in vision link lib.\n");
    return -1;
  }

  return 0;
}

void add_sub_camera(const std::string& cam_name,
                    unsigned int width, unsigned int height, float fov,
                    glm::vec3 offset_p, glm::fquat offset_q) {
  SubCamera target;
  target.cam = std::make_unique<Camera>();
  if (!target.cam) {
    fprintf(stderr, "ERROR: Could not allocate memory for Camera!\n");
    return;
  }

  target.cam->width = width;
  target.cam->height = height;
  target.cam->fov = fov;

  target.vision_link = create_link();
  if (!target.vision_link) {
    fprintf(stderr, "ERROR: Failed to create vision link\n");
    return;
  }

  if (target.vision_link->init(cam_name, width, height)) {
    fprintf(stderr, "WARNING: Failed to initialize vision link for camera \"%s"
                    "\"; vision output will fail.\n", cam_name.c_str());
    destroy_link(target.vision_link);
    return;
  }

  target.offset_p = offset_p;
  target.offset_q = offset_q;

  VisionLink *vlp = target.vision_link;
  add_render_target(target.cam.get(),
                    [vlp] (unsigned char *data, timespec *acq_time) {
                      vlp->post(data, acq_time);
  });

  sub_cameras.push_back(std::move(target));
}

void handle_input(GLFWwindow *window) {
  static constexpr float move_speed = 0.05;

  bool shift = glfwGetKey(window, GLFW_KEY_LEFT_SHIFT) == GLFW_PRESS ||
               glfwGetKey(window, GLFW_KEY_RIGHT_SHIFT) == GLFW_PRESS;

  auto get_speed = [shift, window] (auto c) -> float {
    bool pressed = glfwGetKey(window, c);
    if (pressed && shift)
      return 0.14;
    if (pressed)
      return 1;
    return 0;
  };

  if (first_person) {
    static float off_x, off_y, off_z = 0.0;
    off_x += move_speed * get_speed(GLFW_KEY_W);
    off_x -= move_speed * get_speed(GLFW_KEY_S);
    off_y += move_speed * get_speed(GLFW_KEY_D);
    off_y -= move_speed * get_speed(GLFW_KEY_A);
    off_z += move_speed * get_speed(GLFW_KEY_E);
    off_z -= move_speed * get_speed(GLFW_KEY_Q);

    cam.direction = sub->get_orientation() * NORTH;
    cam.up = sub->get_orientation() * UP;
    auto third = glm::cross(cam.direction, cam.up);
    cam.position = sub->get_position() + cam.direction * off_x +
                   cam.up * off_z + third * off_y;
  }

  // Keep the sub centered in the view
  else if (sub_follow) {
    static float distance = -1.5;
    static float height = 0.0;

    if (distance < -0.5) {
      distance += move_speed * get_speed(GLFW_KEY_W);
    }
    distance -= move_speed * get_speed(GLFW_KEY_S);
    height += move_speed * get_speed(GLFW_KEY_Q);
    height -= move_speed * get_speed(GLFW_KEY_E);

    float starting_angle = 0.0;
    if (heading_lock) {
      // GLM Euler angles are pitch x, heading y, and roll z. Our "heading" is
      // rotation about the z axis, so we get the roll.
      // TODO This is susceptible to gimbal lock. Could use hysteresis to fix.
      starting_angle = -glm::roll(sub->get_orientation());
    }

    cam_angle -= 0.03 * get_speed(GLFW_KEY_A);
    cam_angle += 0.03 * get_speed(GLFW_KEY_D);

    cam.direction = glm::rotate(NORTH, starting_angle + cam_angle, cam.up);
    cam.position = sub->get_position() +
                   cam.direction * distance + cam.up * height;
  }

  // Free look mode
  else {
    glm::vec3 to_add = glm::vec3(0, 0, 0);
    to_add += cam.direction * get_speed(GLFW_KEY_W);
    to_add -= cam.direction * get_speed(GLFW_KEY_S);
    to_add += glm::cross(cam.up, cam.direction) * get_speed(GLFW_KEY_A);
    to_add -= glm::cross(cam.up, cam.direction) * get_speed(GLFW_KEY_D);
    to_add += cam.up * get_speed(GLFW_KEY_Q);
    to_add -= cam.up * get_speed(GLFW_KEY_E);

    cam.position += to_add * move_speed;
  }
}

double last_x;
double last_y;
void mouse_move_mode_on(GLFWwindow *window) {
  mouse_state = MOUSE;
  // Disabled mode automatically keeps the cursor centered; neat!
  glfwSetInputMode(window, GLFW_CURSOR, GLFW_CURSOR_DISABLED);
  glfwGetCursorPos(window, &last_x, &last_y);
}

void mouse_move_mode_off(GLFWwindow *window) {
  mouse_state = FIXED;
  glfwSetInputMode(window, GLFW_CURSOR, GLFW_CURSOR_NORMAL);
}

void handle_mouse_move(GLFWwindow *window, double x, double y) {
  static constexpr float move_speed = 0.003;

  float x_pix = last_x - x;
  float y_pix = last_y - y;
  last_x = x;
  last_y = y;

  float x_diff = x_pix * move_speed;
  float y_diff = y_pix * move_speed;

  if (sub_follow) {
    cam_angle -= x_diff;
  }

  // Free look mode
  else {
    glm::vec3 third = glm::cross(cam.direction, cam.up);

    // Rotate based on vertical mouse motion: pitch
    cam.direction = glm::rotate(cam.direction, y_diff, third);
    cam.up = glm::rotate(cam.up, y_diff, third);

    // Rotate based on horizontal mouse motion: heading
    cam.direction = glm::rotate(cam.direction, x_diff, UP);
    cam.up = glm::rotate(cam.up, x_diff, UP);
  }
}

void update_transformations() {
  for (const auto &object : scene_objects) {
    object->update_transformation();
  }

  glm::vec3 sub_pos = glm::vec3(0, 0, 0);
  if (sub) {
    sub_pos = sub->get_position();
  }

  glm::fquat sub_q = glm::fquat(1, 0, 0, 0);
  if (sub) {
    sub_q = sub->get_orientation();
  }

  // Update cameras on the submarine.
  for (auto &target : sub_cameras) {
    target.cam->position = sub_pos + (sub_q * target.offset_p);
    auto cam_q = sub_q * target.offset_q;
    target.cam->direction = cam_q * NORTH;
    target.cam->up = cam_q * UP;
  }

  // The lights follow the submarine around.
  sub_pos.z = 0;
  light1.position = glm::vec3(-1, 1, -11) + sub_pos;
  light2.position = glm::vec3(1, -1, -11) + sub_pos;
}

bool done = false;
void signal_handler(int param) {
  done = true;
}

//timespec last_time;

void draw_loop(GLFWwindow *window) {
  while (!glfwWindowShouldClose(window) && !done) {
    // Timing needs to be maintained if using single buffered context.
    /*timespec curr_time;
    clock_gettime(CLOCK_REALTIME, &curr_time);

    auto get_time_us = [] (const timespec &curr_time) {
      return 1000000 * curr_time.tv_sec + curr_time.tv_nsec / 1000;
    };

    long elapsed = get_time_us(curr_time) - get_time_us(last_time);
    float fps = 1000000. / elapsed;

    last_time = curr_time;*/

    for (const auto &pair : shm_groups) {
      pair.second->pull();
    }

    update_transformations();
    handle_input(window);
    render_all(cam);

    glfwSwapBuffers(window);
    glfwPollEvents();

    /*clock_gettime(CLOCK_REALTIME, &curr_time);
    elapsed = get_time_us(curr_time) - get_time_us(last_time);

    float sleep_time_ms = (1000 / TARGET_FPS) - elapsed / 1000.;
    printf("%f FPS, time taken is %lu us\n", fps, elapsed);
    if (sleep_time_ms < 0) {
      sleep_time_ms = 0;
    }*/
  }
}

void reshape_callback(GLFWwindow *window, int w, int h) {
  cam.width = w;
  cam.height = h;
}

void error_callback(int error, const char *description) {
  fprintf(stderr, "GLFW ERROR (%d): %s\n", error, description);
}

void get_fishbowl_data() {
  // TODO Do this repeatedly.
  if (!fishbowl_comm::connect()) {
    std::vector<uint32_t> entities = fishbowl_comm::get_all_entities();
    for (auto &e_id : entities) {
      std::string obj_name;
      int res;
      if ((res = fishbowl_comm::get_xattr(e_id, "render", obj_name))) {
        continue;
      }

      double x, y, z;
      bool pos_good = true;
      if ((res = fishbowl_comm::get_position(e_id, x, y, z))) {
        fprintf(stderr, "WARNING: Failed to get position from fishbowl "
                        "for render tag %s\n", obj_name.c_str());
        pos_good = false;
      }

      double q0, q1, q2, q3;
      bool q_good = true;
      if ((res = fishbowl_comm::get_orientation(e_id, q0, q1, q2, q3))) {
        fprintf(stderr, "WARNING: Failed to get position from fishbowl "
                        "for render tag %s\n", obj_name.c_str());
        q_good = false;
      }

      if (!pos_good && !q_good) {
        continue;
      }

      // TODO Build a map for this.
      for (const auto &scene_object : scene_objects) {
        if (scene_object->render_tag == obj_name) {
          if (pos_good) {
            printf("Updating position for object with render tag %s to "
                   "(%f, %f, %f)\n", obj_name.c_str(), x, y, z);
            scene_object->get_position = [x, y, z] () {
              return glm::vec3(x, y, z);
            };
          }

          if (q_good) {
            printf("Updating orientation for object with render tag %s to "
                   "(%f, %f, %f, %f)\n", obj_name.c_str(), q0, q1, q2, q3);
            scene_object->get_orientation = [q0, q1, q2, q3] () {
              return glm::fquat(q0, q1, q2, q3);
            };
          }
        }
      }
    }

    fishbowl_comm::disconnect();
  }
}

int main(int argc, char **argv) {
  // Read configuraiton file.
  std::string model_filename;
  if (argc < 2) {
    model_filename = getBinDir() + BIN2CONFIG + DEFAULT_CONFIG;
  }
  else {
    model_filename = argv[1];
  }

  libconfig::Config config;
  config.setOptions(libconfig::Setting::OptionAutoConvert);

  try {
    config.readFile(model_filename.c_str());
  }
  catch (libconfig::ParseException &pe) {
    fprintf(stderr, "ERROR: Failed to parse config file %s:%d %s\n",
            pe.getFile(), pe.getLine(), pe.getError());
    return -1;
  }
  catch (libconfig::FileIOException &fe) {
    fprintf(stderr, "ERROR: Failed to open config file %s\n",
            model_filename.c_str());
    return -1;
  }

  std::string skybox(DEFAULT_SKYBOX);
  config.lookupValue("skybox", skybox);

  int starting_width = DEFAULT_WIDTH;
  int starting_height = DEFAULT_HEIGHT;
  config.lookupValue("width", starting_width);
  config.lookupValue("height", starting_height);

  if (starting_width < 1 || starting_width > 10000) {
    fprintf(stderr, "ERROR: Invalid screen width: %d. Must be in [1, 10000]\n",
            starting_width);
    return -1;
  }

  if (starting_height < 1 || starting_height > 10000) {
    fprintf(stderr, "ERROR: Invalid screen height: %d. Must be in [1, 10000]\n",
            starting_height);
    return -1;
  }

  // Create window.
  glfwSetErrorCallback(error_callback);
  if (!glfwInit()) {
    return -1;
  }

  glfwWindowHint(GLFW_SAMPLES, 4); // TODO how many samples?
  glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
  glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
  glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 2);
  GLFWwindow *window = glfwCreateWindow(starting_width, starting_height,
                                      "CUAUV Visualizer " VERSION, NULL, NULL);
  if (!window) {
    fprintf(stderr, "ERROR: Failed to create window.\n");
    return -1;
  }

  glfwMakeContextCurrent(window);

  cam.direction = NORTH;
  cam.up = UP;
  cam.width = starting_width;
  cam.height = starting_height;
  cam.fov = 1.0;

  if (init_engine(skybox, true)) {
    fprintf(stderr, "ERROR: Failed to initalize graphics engine.\n");
    return -1;
  }

  shm_init();

  // Parse configuration file.
  std::unordered_map<std::string, GLuint> texture_map;

  auto &objects = config.lookup("objects");
  for (const auto &object : objects) {
    std::string name("Poor nameless object");
    object.lookupValue("name", name);

    std::unique_ptr<SceneObject> scene_object;

    bool is_sub = (object.exists("sub") && ((bool)object.lookup("sub")) == true)
                  || objects.getLength() == 1;
    if (!object.exists("model")) {
      scene_object = std::make_unique<SceneObject>();
      if (!scene_object) {
        fprintf(stderr, "ERROR: Could not allocate memory for SceneObject!\n");
        continue;
      }

      load_axes(scene_object.get());
    }

    else {
      auto mesh_object = std::make_unique<MeshObject>();
      if (!mesh_object) {
        fprintf(stderr, "ERROR: Could not allocate memory for MeshObject!\n");
        continue;
      }
      std::string mesh_name = object.lookup("model");

      auto get_file_name = [] (const std::string &filename, const char *folder) {
        if (filename[0] == '/') {
          return filename;
        }
        return getBinDir() + folder + filename;
      };

      if (load_model(get_file_name(mesh_name, BIN2DATA), mesh_object.get())) {
        fprintf(stderr, "ERROR: failed to make model \"%s\".\n", mesh_name.c_str());
      }

      if (object.exists("texture")) {
        std::string texture = object.lookup("texture");
        if (texture_map.find(texture) == texture_map.end()) {
          GLuint texture_ind;
          if (load_texture(get_file_name(texture, BIN2TEXTURES), texture_ind)) {
            fprintf(stderr, "WARNING: texture \"%s\" failed to load.\n", texture.c_str());
          }

          texture_map[texture] = texture_ind;
        }

        mesh_object->set_texture(texture_map[texture]);
      }

      if (object.exists("alpha")) {
        mesh_object->set_alpha(object.lookup("alpha"));
      }

      scene_object = std::move(mesh_object);
    }

    auto grab_vec = [&object, &name] (const std::string &att_name, glm::vec3 id_v) -> std::function<glm::vec3()> {
      auto id = [id_v] { return id_v; };
      if (object.exists(att_name)) {
        auto &att = object.lookup(att_name);
        if (att.getLength() == 3) {
          glm::vec3 vec(att[0], att[1], att[2]);
          return [vec] { return vec; };
        }

        std::string att_s = att;
        if (add_shm_group(att_s, {"north", "east", "depth"})) {
          return std::bind(get_shm_group_position, shm_groups[att_s].get());
        }
        else {
          fprintf(stderr, "WARNING: Invalid attribute %s for object %s.\n",
                  att_name.c_str(), name.c_str());
        }
      }
      else {
        return id;
      }
      return id;
    };

    auto grab_orientation = [&object, &name] (const std::string &att_prefix) -> std::function<glm::fquat()> {
      auto id = [] { return quat_from_hpr(0, 0, 0); };
      if (object.exists(att_prefix + "_hpr")) {
        auto &att = object.lookup(att_prefix + "_hpr");
        if (att.getLength() == 3) {
          glm::fquat q = quat_from_hpr(att[0], att[1], att[2]);
          return [q] { return q; };
        }
        std::string att_s = att;
        if (add_shm_group(att_s, {"heading", "pitch", "roll"})) {
          return std::bind(get_shm_group_hpr, shm_groups[att_s].get());
        }
        else {
          fprintf(stderr, "ERROR: Invalid orientation_hpr for object \"%s\".\n", name.c_str());
        }
      }
      else if (object.exists(att_prefix + "_q")) {
        std::string att_s = object.lookup(att_prefix + "_q");
        if (add_shm_group(att_s, {"q0", "q1", "q2", "q3"})) {
          return std::bind(get_shm_group_quat, shm_groups[att_s].get());
        }
        else {
          fprintf(stderr, "ERROR: Invalid orientation_q for object \"%s\".\n", name.c_str());
        }
      }

      return id;
    };

    scene_object->get_position = grab_vec("position", glm::vec3(0, 0, 0));
    scene_object->get_orientation = grab_orientation("orientation");
    scene_object->mesh_offset = grab_orientation("mesh_offset")();
    scene_object->get_scale = grab_vec("scale", glm::vec3(1, 1, 1));

    if (object.exists("exclude_renders")) {
      auto &excludes = object.lookup("exclude_renders");
      for (const auto &render : excludes) {
        std::unordered_map<std::string, char> value_map = {
          {"main", RENDER_MAIN},
          {"offscreen", RENDER_OFFSCREEN},
          {"shadow", RENDER_SHADOW}
        };

        if (value_map.find(render) == value_map.end()) {
          std::string s;
          for (const auto &pair : value_map) {
            s += pair.first + " ";
          }

          fprintf(stderr, "WARNING: Invalid exclude_renders for object \"%s\". "
                          "Possible values are: %s\n", name.c_str(), s.c_str());
        }
        else {
          scene_object->exclude |= value_map[render];
        }
      }
    }

    if (object.exists("camera_attachments")) {
      if (!load_vision_link_lib()) {
        auto &cams = object.lookup("camera_attachments");
        for (const auto &cam : cams) {
          auto &pos = cam.lookup("pos");
          auto &orient = cam.lookup("orientation");

          unsigned int width = DEFAULT_WIDTH;
          unsigned int height = DEFAULT_HEIGHT;
          float fov = 1.0;
          cam.lookupValue("width", width);
          cam.lookupValue("height", height);
          cam.lookupValue("fov", fov);

          add_sub_camera(cam.lookup("name"), width, height, fov,
                         glm::vec3(pos[0], pos[1], pos[2]),
                         quat_from_hpr(orient[0], orient[1], orient[2]));
        }
      }
      else {
        fprintf(stderr, "WARNING: Loading vision link library failed; "
                        "vision output unavailable.\n");
      }
    }

    if (object.exists("render_tag")) {
      scene_object->render_tag = object.lookup("render_tag").c_str();
    }

    if (is_sub) {
      sub = scene_object.get();
    }

    scene_objects.push_back(std::move(scene_object));
  }

  // Update objects based on fishbowl data!
  get_fishbowl_data();

  if (!sub) {
    fprintf(stderr, "WARNING: no sub designated; sub follow mode will not work.\n");
  }

  add_light(&light1);
  add_light(&light2);

  glfwSetFramebufferSizeCallback(window, reshape_callback);
  glfwSetKeyCallback(window, key_callback);
  glfwSetCursorPosCallback(window, [] (GLFWwindow *w, double x, double y) {
    mouse_handlers[mouse_state](w, x, y);
  });

  glClearColor(0.0, 0.0, 0.0, 1.0);
  glClearDepth(1.0);
  glEnable(GL_DEPTH_TEST);
  glDepthFunc(GL_LEQUAL);
  glEnable(GL_TEXTURE_2D);
  glEnable(GL_BLEND);
  glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);

  mouse_move_mode_off(window);

  mouse_handlers[MOUSE] = handle_mouse_move;
  mouse_handlers[FIXED] = [] (GLFWwindow *w, int x, int y) {};
  register_action(GLFW_KEY_M, [window] {
    if (mouse_state == MOUSE) {
      mouse_move_mode_off(window);
    }
    else {
      mouse_move_mode_on(window);
    }
  });

  register_action(GLFW_KEY_F, [] {
    if (sub) {
      sub_follow = !sub_follow;
      if (sub_follow) {
        cam.up = UP;
      }
    }
  });
  register_action(GLFW_KEY_H, [] {
    heading_lock = !heading_lock;
    if (heading_lock) {
      cam_angle = 0.0;
    }
  });

  register_action(GLFW_KEY_X, toggle_skybox);
  register_action(GLFW_KEY_Z, toggle_shadows);
  register_action(GLFW_KEY_V, toggle_offscreen_rendering);
  register_action(GLFW_KEY_B, get_fishbowl_data);
  register_action(GLFW_KEY_ESCAPE, [window] () { mouse_move_mode_off(window); });

  register_action(GLFW_KEY_1, [] {
    sub_follow = false;
    cam.position = glm::vec3(0, 0, 0);
    cam.direction = NORTH;
    cam.up = UP;
  });

  register_action(GLFW_KEY_2, [] {
    sub_follow = false;
    cam.position = glm::vec3(0, 0, -25);
    cam.direction = glm::vec3(0, 0, 1);
    cam.up = glm::vec3(1, 0, 0);
  });

  register_action(GLFW_KEY_3, [] {
    sub_follow = false;
    cam.position = glm::vec3(0, 14, -9);
    cam.direction = glm::vec3(0, -0.707, 0.707);
    cam.up = glm::vec3(0, -0.707, -0.707);
  });

  register_action(GLFW_KEY_9, [] {
    first_person = !first_person;
  });

#ifdef ENABLE_FULLSCREEN_TOGGLE
  // 0 key toggles full screen mode.
  int old_x, old_y, old_w, old_h;
  register_action(GLFW_KEY_0, [window, &old_x, &old_y, &old_w, &old_h] {
    if (glfwGetWindowMonitor(window)) {
      glfwSetWindowMonitor(window, NULL, old_x, old_y, old_w, old_h, 0);
    }
    else {
      // Save the window's position and size.
      glfwGetWindowPos(window, &old_x, &old_y);
      glfwGetFramebufferSize(window, &old_w, &old_h);

      // Use the current monitor video mode.
      auto monitor = glfwGetPrimaryMonitor();
      auto vid_mode = glfwGetVideoMode(monitor);
      glfwSetWindowMonitor(window, monitor, 0, 0,
                           vid_mode->width, vid_mode->height, GLFW_DONT_CARE);
    }
  });
#endif

  int width, height;
  glfwGetFramebufferSize(window, &width, &height);
  reshape_callback(window, width, height);

  signal(SIGINT, signal_handler);
  signal(SIGTERM, signal_handler);

  draw_loop(window);

  // Clean up vision links.
  for (auto &target : sub_cameras) {
    destroy_link(target.vision_link);
  }

  glfwDestroyWindow(window);
  glfwTerminate();
  return 0;
}
