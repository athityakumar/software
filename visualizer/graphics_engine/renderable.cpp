#include "renderable.h"

#include <glm/gtc/type_ptr.hpp>

#include "colors.h"
#include "gl_utils.h"
#include "graphics_engine.h"
#include "material.h"
#include "mesh.h"
#include "renderer.h"

int RenderableMaterial::init(const Material *material) {
  this->material = material;

  if (material) {
    texture_enabled = material->map_Kd.size();
    if (texture_enabled) {
      if (load_texture(material->map_Kd, texture_ind)) {
        fprintf(stderr, "ERROR: Texture \"%s\" could not be loaded, requested "
                        "by material \"%s\"\n",
                material->map_Kd.c_str(), material->name.c_str());
        return -1;
      }
    }
  }

  return 0;
}

void RenderableMaterial::update_renderer(Renderer *renderer, bool override_texture, bool override_alpha) const {
  if (material) {
    renderer->update_uniform("ambient_color", material->Ka);
    renderer->update_uniform("diffuse_color", material->Kd);
    renderer->update_uniform("specular_color", material->Ks);
    renderer->update_uniform("shininess", material->Ns);
    if (!override_alpha) {
      renderer->update_uniform("alpha", material->d);
    }

    if (!override_texture) {
      if (texture_enabled) {
        renderer->update_uniform("tex", texture_ind);
      }
    }
    renderer->update_uniform<GLuint>("texture_enabled", texture_enabled || override_texture);
  }
}

int Renderable::init_gl(Renderer *renderer_, std::vector<AttributeMeta> metas,
                        int n_indices_, GLuint *index_buffer, GLenum draw_type_) {
  renderer = renderer_;
  n_indices = n_indices_;
  draw_type = draw_type_;

  glGenVertexArrays(1, &vao);
  glBindVertexArray(vao);

  // Make all the vertex attribute buffers.
  for (const auto& att : metas) {
    GLuint buffer_ind;
    glGenBuffers(1, &buffer_ind);
    glBindBuffer(GL_ARRAY_BUFFER, buffer_ind);
    glBufferData(GL_ARRAY_BUFFER, att.n * att.width * sizeof(GLfloat),
                 att.source, GL_STATIC_DRAW);
    GLint att_loc = renderer->get_att_location(att.name);
    if (att_loc < 0) {
      fprintf(stderr, "Could not get attribute %s in shader.\n", att.name);
      return -1;
    }

    glEnableVertexAttribArray(att_loc);
    glVertexAttribPointer(att_loc, att.width, GL_FLOAT, GL_FALSE, 0, 0);
  }

  // Make the index buffer.
  GLuint i_buffer;
  glGenBuffers(1, &i_buffer);
  glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, i_buffer);
  glBufferData(GL_ELEMENT_ARRAY_BUFFER, n_indices * sizeof(GLuint),
               index_buffer, GL_STATIC_DRAW);

  glBindVertexArray(0);
  return glGetError() != GL_NO_ERROR;
}

void Renderable::draw() const {
  glBindVertexArray(vao);
  glDrawElements(draw_type, n_indices, GL_UNSIGNED_INT, 0);
  glBindVertexArray(0);
}

Renderable get_renderable(Renderer *renderer) {
  GLfloat verts[8][3] = { { 1., 0., 0. },{ 0., 1., 0. },{ 0., 0., 1.},
                          { -1., 0., 0.},{ 0., -1., 0.},{ 0., 0., -1.},
                          { 0., 0., 0. },{ 0., 0., 0. }};
  GLfloat colors[24] = { FADED_BLUE, FADED_BLUE, FADED_BLUE, FADED_RED, FADED_RED, FADED_RED, BLUE, RED };
  GLuint inds[12] = { 6, 0, 6, 1, 6, 2, 7, 3, 7, 4, 7, 5 };

  std::vector<AttributeMeta> atts;
  atts.push_back( { (float *)verts, "in_position", 8, 3 } );
  atts.push_back( { colors, "in_color", 8, 3 } );

  Renderable renderable;
  renderable.init_gl(renderer, atts, 12, inds, GL_LINES);
  return std::move(renderable);
}

Renderable get_renderable(Mesh *mesh, Renderer *renderer) {
  auto verts = std::unique_ptr<GLfloat[]>(new GLfloat[mesh->vertices.size() * 3]);
  auto normals = std::unique_ptr<GLfloat[]>(new GLfloat[mesh->vertices.size()*3]);
  auto uvs = std::unique_ptr<GLfloat[]>(new GLfloat[mesh->vertices.size()*2]);
  auto *inds = mesh->indices.data();
  for (unsigned int i = 0; i < mesh->vertices.size(); i++) {
    for (int j = 0; j < 3; j++) {
      verts[i*3 + j] = glm::value_ptr(mesh->vertices[i].pos)[j];
      normals[i*3 + j] = glm::value_ptr(mesh->vertices[i].normal)[j];
      if (j < 2)
        uvs[i*2 + j] = glm::value_ptr(mesh->vertices[i].uv)[j];
    }
  }

  std::vector<AttributeMeta> atts;
  atts.push_back( { verts.get(), "in_position", (int)mesh->vertices.size(), 3 } );
  if (mesh->has_normal) {
    atts.push_back( { normals.get(), "in_normal", (int)mesh->vertices.size(), 3 } );
  }
  if (mesh->has_uv) {
    atts.push_back( { uvs.get(), "in_uv", (int)mesh->vertices.size(), 2 } );
  }

  Renderable renderable;
  renderable.init_gl(renderer, atts, mesh->indices.size(), inds, GL_TRIANGLES);
  renderable.material.init(mesh->material);
  return std::move(renderable);
}
