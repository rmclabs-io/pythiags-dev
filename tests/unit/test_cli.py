import itertools
import shlex
import subprocess as sp

import pytest
from tests.paths import FIXTURES

from pythiags.cli import _build_meta_map
from pythiags.cli import kivy_mwe
from pythiags.consumer import Consumer
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
                        "bad signature for the 'extract_metadata' method: must be ('self', 'pad', 'info')"
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
                        "bad signature for the 'incoming' method: must be ('self', 'events')"
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
    cmd = "pythiags-launch videotestsrc num-buffers=100 ! xvimagesink"
    sp.check_call(shlex.split(cmd))


# def test_kivy_mwe():
#     kivy_mwe()
