"""Register probes using the :meth:`Application.probe` decorator."""

from __future__ import annotations

from typing import Iterator
from typing import Protocol

import pyds
import pytest

from pythia import Application
from pythia.event_stream.base import Backend
from pythia.iterators import objects_per_batch
from pythia.types import EventStreamUri
from pythia.types import Serializable
from pythia.utils.gst import gst_init

from tests.paths import FIXTURE_PIPELINES

BACKEND_TIMEOUT = [
    ("redis://redis:6379?stream=raw_detections", 5),
    ("kafka://kafka:9092?stream=raw_detections", 20),
    ("memory://?stream=raw_detections", 0),
]


class BackendChecker(Protocol):  # noqa: R0903, C0115
    uri: EventStreamUri

    @staticmethod
    def listen(backend) -> list:  # noqa: C0116
        ...


@pytest.mark.parametrize("setup_backend", BACKEND_TIMEOUT, indirect=True)
def test_producer_working(setup_backend: BackendChecker) -> None:
    """Use generator probe to forward messages to event stream backend.

    Args:
        setup_backend: pytest fixture forwarding the uri and probiding
            a 'listen' attribute to be used to read back from the
            backend service.

    """

    pipeline = (FIXTURE_PIPELINES / "4_minimal_nvinfer_jpeg").read_text()
    gst_init()
    app = Application.from_pipeline_string(pipeline)

    detections = []

    @app.probe("pgie", pad_direction="src", backend_uri=setup_backend.uri)
    def report(batch_meta: pyds.NvDsBatchMeta) -> Iterator[Serializable]:
        for frame, detection in objects_per_batch(batch_meta):
            frame_num = frame.frame_num
            box = detection.rect_params
            data = {
                "frame_num": frame_num,
                "label": detection.obj_label,
                "left": box.left,
                "top": box.top,
                "width": box.width,
                "height": box.height,
                "confidence": detection.confidence,
            }
            detections.append(data)
            yield data

    backend: Backend = app._registered_probes["pgie"]["src"][0][  # noqa: W0212
        "backend"
    ]
    klass = type(backend)
    post_impl = klass.post

    def post(self, data):
        if not hasattr(self, "called_with__"):
            self.called_with__ = []
        self.called_with__.append(data)
        return post_impl(self, data)

    klass.post = post  # type: ignore[assignment]

    app()
    for detection in detections:
        backend.called_with__.remove(detection)  # type: ignore[attr-defined]

    assert not backend.called_with__  # type: ignore[attr-defined]
    received = setup_backend.listen(backend)
    assert received == detections
