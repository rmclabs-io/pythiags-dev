"""Event stream interface and common definitions."""
from __future__ import annotations

import abc
import importlib
import re
from typing import Any
from typing import Dict
from typing import Tuple
from typing import Type
from urllib.parse import parse_qs
from urllib.parse import urlparse

from pythia.types import EventStreamUri


def _parse_netloc(netloc: str):
    pat = (
        "^"
        r"(?:"
        r"(?P<username>.*?"
        r"(:(?P<password>.*?))?"
        r")?"
        r"@"
        r")?"
        r"(?P<host>.*?)"
        r"(?:"
        r":(?P<port>\d+)"
        r")?"
        r"$"
    )
    match = re.match(pat, netloc)
    if not match:
        raise ValueError(f"Invalid netloc '{netloc}' for uri")
    return match.groupdict()


def parse_uri(uri: EventStreamUri) -> Tuple[dict[str, Any], Dict[Any, list]]:
    """Get information from the uri.

    Args:
        uri: uri to parse.

    Returns:
        A tuple containing (a) dictionary containing the following keys:
        scheme, netloc, path, params, query, fragment - as contained in
        the uri, and (b) query parameters form the uri.

    """
    data = urlparse(uri)._asdict()
    query = parse_qs(data["query"], strict_parsing=False)
    return data, query


class Backend(abc.ABC):
    """Even stream backend.

    This class has three pruposes:
        * Interface for custom backends
        * Skeleton for their internal workings.
        * Factory to choose implementation.

    """

    def __init__(self, uri: EventStreamUri) -> None:
        """Initialize a backend from its uri.

        Args:
            uri: connection string.

        """
        self.raw_uri = uri
        data, query = parse_uri(uri)
        self.netloc = _parse_netloc(data["netloc"])
        self.query = query
        self.stream = stream = self.query["stream"][0]
        self.uri = uri.replace(f"stream={stream}", "").rstrip("?")
        self.connect()

    @classmethod
    def from_uri(cls: Type[Backend], uri: EventStreamUri) -> Backend:
        """Factory to select Backend from its schema.

        Args:
            uri: connection string.

        Returns:
            The instantiated backend for the requested schema.

        """
        data, _ = parse_uri(uri)
        scheme = data["scheme"]
        module = importlib.import_module(f"{__package__}.{scheme}")
        klass = module.Backend

        return klass(uri=uri)

    @abc.abstractmethod
    def connect(self):
        """Ensure internal connection to the remote service is ok."""

    @abc.abstractmethod
    def post(self, data):
        """Send single packet of data.

        Args:
            data: the data to send.

        This method gets called once for each element yielded from the
        buffer probe.

        Any kind of batching should be implemented here and coordinated
        with the respective buffer probe.

        """
