import abc
import json
import logging
from pathlib import Path

from pythiags.models import Events


class Consumer(abc.ABC):
    @abc.abstractmethod
    def incoming(self, events: Events) -> None:
        """Callback to report extracted metadata in python native objects.

        This callback is called in a sencondary thread, after a worker
        detects a non-empty queue.

        """


class LogFileWriter(Consumer):
    """Logging implementation of a pythiags Consumer."""

    def __init__(self, dump_path: Path, serializer=json.dumps):
        self.logger = self.build_logger(dump_path)
        self.serialize = serializer

    @staticmethod
    def build_logger(filepath):
        path = Path(filepath).resolve()
        logger = logging.getLogger(path.stem)
        logger.setLevel(logging.INFO)
        ch = logging.FileHandler(str(path))
        ch.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(ch)
        return logger

    def incoming(self, events: Events) -> None:
        for event in events:
            serialized = self.serialize(event)
            self.logger.info(serialized)
