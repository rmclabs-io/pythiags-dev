# -*- coding: utf-8 -*-
"""Background processing."""

import abc
import enum
import os
import queue
import signal
import sys
import threading
from functools import partial
from time import sleep
from typing import Any
from typing import Callable
from typing import Optional

from pythiags import logger
from pythiags.models import Events
from pythiags.utils import SENTINEL


class StoppableThread(threading.Thread, abc.ABC):
    """A `Thread` enabled for external stopping by attribute settings.

    .. seealso:: For example implementation, see `EventsWorker`

    """

    def __repr__(self):
        return f"<{type(self).__name__}({self.name})>"

    def __init__(
        self,
        queue: queue.Queue,
        name: Optional[str] = "BackgroundThread",
        daemon: Optional[bool] = True,
        pop_timeout: Optional[int] = 1,
    ) -> None:
        """Initialize a stoppable thread.

        Args:
            queue: Location to retreive data on every iteration.
            name: Set name (Thread kwarg).
            daemon: Set thread to daemon mode (Thread kwarg).
            pop_timeout: Use as `queue.Queue.get` timeout. Set to `None`
                disables timeout.

        """
        super().__init__(group=None, target=None, name=name, daemon=daemon)
        self.queue = queue
        self.external_stop = False
        self.pop_timeout = pop_timeout

    def run(self):
        """Run skeleton - fetch data and check external stop, forever."""
        while not self.external_stop:
            try:
                self.work_once(
                    self.queue.get(block=True, timeout=self.pop_timeout)
                )
                logger.debug(
                    "PyhiaBackground: %s popped element from queue", str(self)
                )
                self.queue.task_done()
            except queue.Empty:
                logger.debug(
                    "PyhiaBackground: %s empty queue after %s [s]",
                    str(self),
                    self.pop_timeout,
                )
            except Exception as exc:  # noqa: W0703
                logger.error(exc)
        logger.info(
            # No lazy formatting here to avoid thread+pickling issues
            f"PyhiaBackground: Stopping {self}. Reason: `external_stop` set."  # noqa: W1203
        )

    @abc.abstractmethod
    def work_once(self, events: Any):
        """Process a single element from the queue.

        This is the only method which must be implemented, the def t of
        the skeleton should work as it is.

        Args:
            events: An element obtained using `Queue.get`.

        """


class CancelNotInWaiting(ValueError):
    pass


class PostponedBackgroundThread(threading.Thread, abc.ABC):
    """A `Thread` enabled for external stopping by attribute settings."""

    class States(enum.IntFlag):
        IDLE = 0
        WAITING = 1
        RUNNING = 2
        CANCELLED = 4
        SUCCEEDED = 8
        FAILED = 16

    def __repr__(self):
        out = (
            f", return={self._output}"
            if self.States.SUCCEEDED in self.state
            else ""
        )
        return f"<{type(self).__name__}({self.name}, delay={self.delay}, state={str(self.state)}{out})>"

    def __init__(
        self,
        callback: callable,
        delay: int = 0,
        name: Optional[str] = "PostponedBackgroundThread",
        daemon: Optional[bool] = True,
        on_success: Optional[Callable[[Any], Any]] = None,
        on_failure: Optional[Callable[[Exception], Any]] = None,
    ) -> None:
        """Initialize a cancellable delayed thread.

        Args:
            callback: Callable to execute after delay.
            delay: Delay before running.
            name: Thread `name` kwarg.
            daemon: Thread  `daemon` kwarg.

        """

        super().__init__(group=None, target=None, name=name, daemon=daemon)

        self.callback = callback
        self.delay = delay

        self.on_failure = on_failure
        self.on_success = on_success

        self.state = self.States.IDLE
        self._cancelled = False
        self._output = SENTINEL

    def cancel(self):
        if self.States.WAITING not in self.state:
            raise CancelNotInWaiting(
                f"Unable to cancel: {self} not in waiting state"
            )

        self._cancelled = True
        self.state |= self.States.CANCELLED

    def run(self):
        """Run skeleton - delay data and check external stop."""
        self.state |= self.States.WAITING
        sleep(self.delay)
        if self._cancelled:
            logger.debug(f"{self.name}: Cancelled {self}")
            return

        self.state &= ~self.States.WAITING
        try:
            self.state |= self.States.RUNNING
            self._output = self.callback()
        except Exception as exc:
            self.state &= ~self.States.RUNNING
            self.state |= self.States.FAILED
            if self.on_failure:
                self.on_failure(exc)
            else:
                logger.exception(f"{self.name}: Failed {self.name}")
                raise
        except KeyboardInterrupt:
            print("How rude!")
        else:
            self.state &= ~self.States.RUNNING
            self.state |= self.States.SUCCEEDED
            if self.on_success:
                self.on_success(self._output)
            else:
                logger.debug(f"{self.name}: Completed {self}: {self._output}")

        return self._output

    def join(self, timeout=None, raise_on_timeout=False):
        ret = super().join(timeout=timeout)
        if raise_on_timeout and self.is_alive():
            raise TimeoutError(f"{self} did not complete in {timeout} [s]")
        return ret


def run_later(
    cb,
    delay,
    *a,
    daemon=True,
    on_success: Optional[Callable[[Any], Any]] = None,
    on_failure: Optional[Callable[[Exception], Any]] = None,
    **kw,
) -> PostponedBackgroundThread:
    runner = PostponedBackgroundThread(
        partial(cb, *a, **kw),
        delay,
        daemon=daemon,
        name=cb.__name__,
        on_success=on_success,
        on_failure=on_failure,
    )
    runner.start()
    return runner


class EventsWorker(StoppableThread):
    """Use an initialization-defined callback in `work_once` calls."""

    def __init__(self, callback: Callable[[Events], None], *a, **kw):
        """Initialize thread passing it a callback to use in `work_once`.

        Args:
            callback ([type]): [description]
            a: Positional arguments, forwarded to parent cls instantiation.
            kw: Keyword arguments, forwarded to parent cls instantiation.

        """
        super().__init__(*a, **kw)
        self.callback = callback

    def work_once(self, events: Events) -> None:
        """Call the bound callback on every loop iteration.

        Args:
            events: Data obtained from the queue on every iteration.

        """
        self.callback(events)


class PythiaThreadedExit(Exception):
    def __init__(self, signal, frame):
        super().__init__()
        self.signal, self.frame = signal, frame

    def __str__(self):
        return f"PythiaThreadedExit(signal={self.signal}, frame={self.frame})"


def signal_handler(signal, frame):
    logger.exception(
        PythiaThreadedExit(
            signal=signal,
            frame=frame,
        )
    )
    sys.exit(44)


signal.signal(signal.SIGUSR1, signal_handler)


def exit_from_thread():
    return os.kill(os.getpid(), signal.SIGUSR1)
