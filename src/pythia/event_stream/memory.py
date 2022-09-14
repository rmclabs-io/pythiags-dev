"""Memory-backed event stream storage."""

from __future__ import annotations

from collections import deque
from typing import Callable

from pythia.event_stream.base import Backend as Base

STORAGE: dict[str, deque] = {}


class Backend(Base):
    """Simple event stream client to store incoming data into a deque.

    By default, the deque does not have a limit so the dev mus pay
    special attention to avoid the deque from growing indefinitely.
    Alternatively, a bounded deque could be used, or a watcher to pop
    old-enough elements in a background worker.

    """

    _deque: deque | None = None
    _deque_constructor: Callable = deque
    """Allow to customize the storage (eg to set maxlen)."""

    @property
    def deque(self) -> deque:
        """Internal container lazy-loader.

        Returns:
            Initialized deque.

        """
        if self._deque is None:
            self.connect()
        return self._deque  # type: ignore

    def connect(self) -> None:
        """Fetch stream-specific deque from global container."""
        try:
            self._deque = STORAGE[self.stream]
        except KeyError:
            self._deque = STORAGE[self.stream] = self._deque_constructor()

    def post(self, data) -> None:
        """Append an element into the deque.

        Args:
            data: the data to append. Can be any python object.

        """
        self.deque.append(data)
