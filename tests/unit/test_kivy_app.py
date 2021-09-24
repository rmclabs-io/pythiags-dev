import itertools
import shlex
import subprocess as sp
import time
from threading import Thread
from typing import Optional

import pytest
from tests.paths import FIXTURES

from pythiags.cli import _build_meta_map
from pythiags.consumer import Consumer
from pythiags.kivy_app import PythiaGsCli
from pythiags.producer import Producer


class TestBuildMetaMap:

    EXTRACTORS = {
        "ExtractorOk",
        "ExtractorBadSignature",
        "ExtractorBadInheritance",
    }
    CONSUMERS = {
        "ConsumerOk",
        "ConsumerBadSignature",
        "ConsumerBadInheritance",
    }

    @pytest.mark.parametrize(
        ("extractor", "consumer"), itertools.product(EXTRACTORS, CONSUMERS)
    )
    def test_build_meta_map(self, extractor, consumer):
        extractor_importstr = (
            str(FIXTURES / "sample_parser.py") + f":{extractor}"
        )
        consumer_importstr = (
            str(FIXTURES / "sample_parser.py") + f":{consumer}"
        )

        extractor_ok = "ok" in extractor.lower()
        consumer_ok = "ok" in consumer.lower()

        if not extractor_ok or not consumer_ok:
            with pytest.raises(TypeError) as excinfo:
                _build_meta_map(
                    "element",
                    extractor_importstr,
                    consumer_importstr,
                )
            exc = str(excinfo.value)
            if not extractor_ok:
                if "badsignature" in extractor.lower():
                    assert (
                        "bad signature for the 'extract_metadata' method: must be ['self', 'pad', 'info']"
                        in exc
                    )
                else:
                    assert (
                        "must subclass <class 'pythiags.producer.Producer'>"
                        in exc
                    )
            elif not consumer_ok:
                if "badsignature" in consumer.lower():
                    assert (
                        "bad signature for the 'incoming' method: must be ['self', 'events']"
                        in exc
                    )
                else:
                    assert (
                        "must subclass <class 'pythiags.consumer.Consumer'>"
                        in exc
                    )
            return

        mem = _build_meta_map(
            "element",
            extractor_importstr,
            consumer_importstr,
        )
        assert {*mem.keys()} == {"element"}
        ext, cons = [*mem.values()][0]

        assert isinstance(ext, Producer)
        assert isinstance(cons, Consumer)

        assert ext.extract_metadata.__code__.co_varnames == (
            "self",
            "pad",
            "info",
        )
        assert cons.incoming.__code__.co_varnames == ("self", "events")


def test_pythiags_launch():
    cmd = "pygst-launch videotestsrc num-buffers=100 ! fakesink"
    sp.check_call(shlex.split(cmd))


class Timer(Thread):
    """A `Thread` enabled for external stopping by attribute settings."""

    def __repr__(self):
        return f"<{type(self).__name__}({self.name})>"

    def __init__(
        self,
        timeout: int,
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
        self.timeout = timeout
        self.external_stop = False
        self.running_time = 0

    def run(self):
        """Run skeleton - fetch data and check external stop, forever."""
        while not self.external_stop and self.running_time < self.timeout:
            time.sleep(1)
            self.running_time += 1
        if not self.external_stop:
            raise TimeoutError("Function timed out.")

    def stop(
        self,
    ):
        self.external_stop = True


SAMPLE_PIPE = "videotestsrc num-buffers={num_buffers} ! video/x-raw, framerate={fps}/1 ! timeoverlay ! appsink name=pythiags emit-signals=true caps=video/x-raw,format=RGB"


def test_cli_timeout():
    timer = Timer(timeout=10)
    timer.start()
    # pipeline = "videotestsrc num-buffers=1000000 ! appsink name=pythiags emit-signals=true caps=video/x-raw,format=RGB"
    pipeline = SAMPLE_PIPE.format(num_buffers=1000000, fps=30)
    PythiaGsCli.cli_run(pipeline=pipeline, timeout=5)
    timer.stop()


def test_cli_no_timeout():
    # pipeline = "videotestsrc num-buffers=60 ! timeoverlay ! appsink name=pythiags emit-signals=true caps=video/x-raw,format=RGB"
    pipeline = SAMPLE_PIPE.format(num_buffers=60, fps=30)
    PythiaGsCli.cli_run(pipeline=pipeline, timeout=2)
    time.sleep(2)
