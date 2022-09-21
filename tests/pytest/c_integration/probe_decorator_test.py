"""Register probes using the :meth:`Application.probe` decorator."""

from __future__ import annotations

from typing import TypedDict

import pyds
import pytest

from pythia import Application
from pythia.iterators import frames_per_batch
from pythia.iterators import objects_per_frame
from pythia.utils.gst import Gst
from pythia.utils.gst import gst_init

from tests.paths import FIXTURE_PIPELINES


class _Detection(TypedDict):
    frame_num: int
    label: str
    left: float
    top: float
    width: float
    height: float
    confidence: float


class _MockClient:  # noqa: R0903
    def __init__(self) -> None:
        self.sent: list[_Detection] = []

    def post(self, data) -> None:  # noqa: C0116
        self.sent.append(data)


class _App(Application):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.client = _MockClient()


@pytest.mark.usefixtures("_nvidia_cooldown")
def test_decorator_working() -> None:
    """Define a probe using a single."""
    pipeline = (FIXTURE_PIPELINES / "4_minimal_nvinfer_jpeg").read_text()
    gst_init()
    app = _App.from_pipeline_string(pipeline)

    @app.probe("pgie", pad_direction="src")
    def probe_4(batch_meta: pyds.NvDsBatchMeta):
        for frame in frames_per_batch(batch_meta):
            frame_num = frame.frame_num
            for detection in objects_per_frame(frame):
                box = detection.rect_params
                app.client.post(
                    {
                        "frame_num": frame_num,
                        "label": detection.obj_label,
                        "left": box.left,
                        "top": box.top,
                        "width": box.width,
                        "height": box.height,
                        "confidence": detection.confidence,
                    }
                )
        return Gst.PadProbeReturn.OK

    app()

    assert app.client.sent, "No detections were sent to the client"
    assert (
        max(m["confidence"] for m in app.client.sent) > 0.9
    ), "Expected at least a confidente detection."
