import sys
import signal
from threading import Thread, Event

import shm

#http://code.activestate.com/recipes/578231-probably-the-fastest-memoization-decorator-in-the-/
def memoize(f):
    """ Memoization decorator for functions taking one or more arguments. """
    class memodict(dict):
        def __init__(self, f):
            self.f = f
        def __call__(self, *args):
            return self[args]
        def __missing__(self, key):
            ret = self[key] = self.f(*key)
            return ret
    return memodict(f)

def watch_thread_wrapper(f):
    """
        Calls a function f that can be properly shut down on process
        termination. This function will exit the program on SIGINT or SIGTERM.
        f should take in a watcher and an event and should exit when
        the event is set.

        EXAMPLE:
            def f(watcher, quit_event):
                watcher.watch(group_of_interest)

                while not quit_event.is_set():
                    # do things
                    watcher.wait()

            watch_thread_wrapper(f) # Begins the loop above.
    """
    watcher = shm.watchers.watcher()
    quit_event = Event()

    thread = Thread(target=f, args=(watcher, quit_event))

    def interrupt_handler(_signal, _frame):
        quit_event.set()
        watcher.disable()
        thread.join()
        sys.exit(0)

    signal.signal(signal.SIGINT, interrupt_handler)
    signal.signal(signal.SIGTERM, interrupt_handler)

    thread.start()
    # XXX: Python HACK, join calls without a timeout do not respond to signals
    while thread.is_alive():
        thread.join(60)
