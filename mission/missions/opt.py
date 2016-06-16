'''

Optimal Mission Runner

Introduction:

Usage:

Tasks must expose the following interface:

  current_points :: double
  possible_modes :: () -> [mode]
  
  --> Should take into account state, whether we think we're succeeding.
  
Tasks are passed the following parameters on run:

  mode :: string (the name of the mode)
  flex :: bool

Caveats / To Know:

Task instances may be re-run after periods of inactivity (not being run).
This can cause issues with quasi-time-dependent state, e.g. PID loops calculating dts.
Suggested fix: check self.last_run in on_run and reset such state if too much time has passed.

'''

from functools import *

from auv_python_helpers.auvec import *

from mission.framework.task import *
from mission.framework.combinators import *
from mission.framework.movement import *
from mission.framework.primitive import *

import pyximport
pyximport.install()

from mission.opt.core import *

import shm
import time

def execute(task, taskPlan):
  # TODO Deal with bounding box.
  task.instance(
    mode = taskPlan.mode,
    flex = 0
    )

def prettify(taskPlan):
  return ' => '.join(task.taskName + ' @ ' + task.mode.name for task in taskPlan)

class Opt(Task):
  def __init__(self, tasks, restrictions, criterion, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.tasks = tasks
    self.restrictions = restrictions
    self.criterion = criterion
    self.taskMap = {task.name: task for task in self.tasks}
    
  def on_first_run(self, *args, **kwargs):
    pass

  def on_run(self):
    capabilities = shm.capabilities.get()
    start = time.time()
    distances = {task.name: {other.name: (task.startPosition() - other.startPosition()).norm() for other in self.tasks} for task in self.tasks}
    options = []
    for plan in generate([], self.tasks, self.restrictions):
      plan_stat  = stat(distances, plan, capabilities)
      plan_score = self.criterion.score(plan_stat)
      options.append((plan, plan_stat, plan_score))
    options = sorted(options, key = lambda x:x[1], reverse = True)
    end = time.time()
    self.logv('Generated, validated, scored and sorted {} possible execution plans in {} seconds.'.format(len(options), end - start))
    if len(options) > 0:
      selected = options[0]
      self.logv('Execution plan: {}. Expected points: {}. Expected time: {}. Score: {}.'.format(prettify(selected[0]), selected[1].expectedPoints, selected[1].expectedTime, selected[2]))
      taskPlan = selected[0][0]
      self.logv('Executing task {} with mode {}.'.format(taskPlan.taskName, taskPlan.mode.name))
      execute(self.taskMap[taskPlan.taskName], taskPlan)
    else:
      self.finish()

  def on_finish(self):
    self.logv('Optimal mission complete!')
