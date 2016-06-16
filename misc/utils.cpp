#include "utils.h"

#include <stdio.h>
#include <sys/wait.h>
#include <unistd.h>

//Returns directory of executable calling it (Linux magic)
//NOTE: includes ending slash
std::string getBinDir() {
  char buf[1024];
  int len = readlink("/proc/self/exe", buf, sizeof(buf)-1);
  buf[len] = '\0';
  std::string bin_filename(buf);
  size_t last_slash = bin_filename.find_last_of('/');
  return bin_filename.substr(0, last_slash+1);
}

//test whether a file is opened.
bool file_opened(char *filename) {
  pid_t child_pid = fork();
  if (!child_pid) {
    if (!freopen("/dev/null", "w", stdout)) {
      fprintf(stderr, "Could not redirect stdout to /dev/null\n");
    }
    if (!freopen("/dev/null", "w", stderr)) {
      fprintf(stderr, "Could not redirect stderr to /dev/null\n");
    }

    execlp("fuser", "fuser", "-s", filename, NULL);
    exit(-1);
  }
  int status;
  waitpid(child_pid, &status, 0);
  status = WEXITSTATUS(status);
  return status == 0;
}
