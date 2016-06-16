#ifndef _RENDERABLE_H_
#define _RENDERABLE_H_

#include <memory>
#include <vector>

#include <GL/gl.h>

class Material;
class Mesh;
class Renderer;

class AttributeMeta {
  public:
    GLfloat *source;
    const char *name;
    int n;
    int width;
};

class RenderableMaterial {
  public:
    int init(const Material *material);
    void update_renderer(Renderer *renderer, bool override_texture, bool override_alpha) const;

  private:
    bool texture_enabled;
    GLuint texture_ind;
    const Material *material = nullptr;
};

class Renderable {
  public:
    int init_gl(Renderer *renderer_, std::vector<AttributeMeta> metas,
                int n_indices_, GLuint *index_buffer, GLenum draw_type_);
    void draw() const;

    Renderer *renderer;
    RenderableMaterial material;

  private:
    GLenum draw_type;
    int n_indices;
    GLuint vao;
};

Renderable get_renderable(Renderer *renderer);
Renderable get_renderable(Mesh *mesh, Renderer *renderer);
#endif
