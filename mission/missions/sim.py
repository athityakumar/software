# Full Simulated Mission

from mission.opt.aux import *
from auv_python_helpers.auvec import *
from mission.missions.opt import Opt
from mission.missions.printer import Printer

criterion = Criterion(
  validate = lambda _: True,
  score = lambda plan: plan.expectedPoints + 1 / (1 + plan.expectedTime)
  )

class ModedPrinter(Printer):
  def possible_modes(self):
    return [
      Mode(name = 'Mode A', expectedPoints = 100, expectedTime = 10),
      Mode(name = 'Mode B', expectedPoints = 200, expectedTime = 15)
      ]

printer = lambda n: OptimizableTask(
  name = n,
  instance = ModedPrinter(),
  startPosition = lambda: Position.ZERO(),
  permissibleBoundingBox = lambda: None
  )

tasks = [
  printer('Printer 1'),
  printer('Printer 2'), 
  printer('Printer 3')
]

restrictions = [
  TopologicalRestriction(beforeTask = 'Printer 1', afterTask = 'Printer 2')
  ]

Sim = lambda: Opt(tasks, restrictions, criterion)
