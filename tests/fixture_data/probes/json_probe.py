"""Sample buffer probe for pythia testing."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from typing import Iterator

import pyds

from pythia.iterators import frames_per_batch
from pythia.iterators import objects_per_frame
from pythia.utils.gst import Gst

with tempfile.NamedTemporaryFile(  # noqa: R1732
    delete=False, suffix=".log", prefix="pythiatest-"
) as tmp:
    FORGETME = tmp.name
JSONLINES_LOC = Path(tmp.name).with_name("pythiastest-log").with_suffix(".log")


def _batch_meta_gen(
    batch_meta: pyds.NvDsBatchMeta,
) -> Iterator[dict[str, Any]]:
    for frame in frames_per_batch(batch_meta):
        frame_num = frame.frame_num
        for detection in objects_per_frame(frame):
            box = detection.rect_params
            yield {
                "frame_num": frame_num,
                "label": detection.obj_label,
                "left": box.left,
                "top": box.top,
                "width": box.width,
                "height": box.height,
                "confidence": detection.confidence,
            }


def _probe(
    pad,  # noqa: W0613
    info,  # noqa: W0613
    batch_meta: pyds.NvDsBatchMeta,
) -> Gst.PadProbeReturn:
    with open(JSONLINES_LOC, "a+", encoding="utf-8") as log:
        for data in _batch_meta_gen(batch_meta):
            print(json.dumps(data), file=log)
    return Gst.PadProbeReturn.OK
