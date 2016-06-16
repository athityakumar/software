from mission.framework.task import Task
from mission.framework.helpers import call_if_function


class Timer(Task):
    """ A task that finishes after a set amount of time.

        Args:
            seconds: The amount of seconds to be waited before finishing.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seconds = 0

    def on_run(self, seconds, *args, **kwargs):
        """
        Args:
            seconds: The amount of seconds to be waited before finishing.
        """
        self.seconds = call_if_function(seconds)
        if (self.this_run_time - self.first_run_time) >= self.seconds:
            self.finish()
