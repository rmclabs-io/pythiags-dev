"""Memory-backed event stream storage."""

from __future__ import annotations

from pythia.applications.annotation import _DumpLogger
from pythia.applications.annotation import _make_logger
from pythia.event_stream.base import Backend as Base


class Backend(Base):
    """Simple event stream client to dump incoming data using logs."""

    _logger: _DumpLogger | None = None

    @property
    def logger(self) -> _DumpLogger:
        """Internal logger lazy-loader.

        Returns:
            Initialized logger.

        """
        if self._logger is None:
            self.connect()
        return self._logger  # type: ignore

    def connect(self) -> None:
        """Fetch stream-specific deque from global container."""
        self._logger = _make_logger(type(self).__qualname__, self.stream)

    def post(self, data) -> None:
        """Append an element into the deque.

        Args:
            data: the data to append. Can be any python object.

        """
        self.logger.json(data)
