# -*- coding: utf-8 -*-
"""Background processing."""

import abc
import queue
import threading
from typing import Any
from typing import Callable
from typing import Optional

from pythiags import logger
from pythiags.models import Events


class StoppableThread(threading.Thread, abc.ABC):
    """A `Thread` wnabled for external stopping by attribute settings.

    .. seealso:: For example implementation, see `EventsWorker`

    """

    def __init__(
        self,
        queue: queue.Queue,
        name: Optional[str] = None,
        daemon: Optional[bool] = True,
    ) -> None:
        """Initialize a stoppable thread.

        Args:
            queue: Location to retreive data on every iteration.
            name: Set name (Thread kwarg).
            daemon: Set thread to daemon mode (Thread kwarg).

        """
        super().__init__(group=None, target=None, name=name, daemon=daemon)
        self.queue = queue
        self.external_stop = False

    def run(self):
        """Run skeleton - fetch data and check external stop, forever."""
        while not self.external_stop:
            try:
                logger.debug(f"PyhiaBackground: {self} working")
                self.work_once(self.queue.get(block=True, timeout=1))
                logger.debug(f"PyhiaBackground: {self} queue got element")
                self.queue.task_done()
            except queue.Empty as exc:
                logger.debug(f"PyhiaBackground: {self} queue timeout ({exc})")
            except Exception as exc:
                logger.warning(exc)
        logger.info(
            f"PyhiaBackground: Stopping {self}. Reason: `external_stop` set."
        )

    @abc.abstractmethod
    def work_once(self, data: Any):
        """Process a single element from the queue.

        This is the only method which must be implemented, the rest of
        the skeleton should work as it is.

        Args:
            data: An element obtained using `Queue.get`.

        """


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
