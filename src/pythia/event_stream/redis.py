"""Redis-backed event stream storage."""

from __future__ import annotations

import json

from redis import Redis

from pythia.event_stream.base import Backend as Base


class Backend(Base):
    """Simple backend to post messages using :meth:`Redis.xadd`."""

    _client: Redis | None = None

    @property
    def client(self) -> Redis:
        """Redis producer lazy-loader.

        Returns:
            Initialized producer, guaranteed to be both ping-connected.

        """
        if not self._client:
            self.connect()
        return self._client  # type: ignore

    def connect(self) -> None:
        """Instantiate a Redis client.

        This method is in charge of creating the client and  making sure
        it is properly connected via ping.

        """
        self._client = Redis.from_url(self.uri)
        self._client.ping()

    def post(self, data) -> None:
        """Make the redis client send data via :meth:`Redis.xadd`.

        Args:
            data: the data to append. Can be any python object.

        """

        self.client.xadd(self.stream, fields={"data": json.dumps(data)})
