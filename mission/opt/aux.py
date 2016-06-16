'''

Optimal Mission Runner Types / Auxiliary

Separated out for ease-of-import.

'''

from collections import namedtuple
from enum import Enum

TaskPlan = namedtuple('TaskPlan', [
  'taskName',
  'mode'
  ])

ExecutionPlanStat = namedtuple('ExecutionPlanStat', [
  'expectedPoints',
  'expectedTime'
  ])

'''
Criterion: An optimization criterion (how to decide what to do).

Criteria must specify:
  validate :: ExecutionPlan -> Bool
  score :: ExecutionPlanStat -> Double
'''

Criterion = namedtuple('Criterion', [
  'validate',
  'score'
  ])

'''
Capabilites: The capabilities of the submarine!

'''

'''
Mode: A way in which a task can be run.

Examples:
  -> Various passage options for navigation.
  -> Firing one vs. two torpedoes for torpedoes.
  -> Dropping on one / two / specific bins for bins.

Modes must specify:
  name :: string (this is passed to the task)
  expectedPoints :: double
  expectedTime :: double (seconds)

expectedPoints should be equal to the point total given by the rules multiplied by the expected chance of success of the task.
'''

Mode = namedtuple('Mode', [
  'name',
  'expectedPoints',
  'expectedTime'
  ])

'''
OptimizableTask: A task that can be run by the optimal mission runner.

OptimizableTasks must specify:
  name :: string
  instance :: instance of Task (instance, `not` class)
  permissibleBoundingBox :: () -> auvec.PositionBoundingBox
'''

OptimizableTask = namedtuple('OptimizableTask', [
  'name',
  'instance',
  'startPosition',
  'permissibleBoundingBox'
  ])

'''
Topological Restriction: A required ordering of tasks.

TopologicalRestrictions must specify
  beforeTask :: string
  afterTask  :: string
'''

TopologicalRestriction = namedtuple('TopologicalRestriction', [
  'beforeTask',
  'afterTask'
  ])
