"""This is the example shown in the readme.

Feature: Deepstream detections available
  As an external developer
  I want to capture detections with a simple python module
  so I can quickly develop my application based on pythia

@deepstream
Scenario: Show detections in console
  Given a bunch of images with people and cars
  And a parsing module which logs detections to console
  When I run a pipeline with pygst-launch
  Then I see the detections in the console

"""


import json
import shutil
import subprocess as sp
from pathlib import Path
from shlex import split

from tests.fixture_data.probes import json_probe
from tests.paths import DS_SAMPLES
from tests.paths import FIXTURE_PIPELINES
from tests.utils import IS_JETSON
from tests.utils import roundup

PIPELINE = f"""
uridecodebin3 uri=file://{DS_SAMPLES}/streams/sample_720p.jpg
! m.sink_0
nvstreammux
  name=m width=1280 height=720 batch-size=1
! nvinfer
  config-file-path={DS_SAMPLES}/models/peoplesegnet/pgie.conf
  name=pgie
! fakesink
"""

COMMAND = "gst-pylaunch -p {pipe} -x {probesfile}:{probe}@pgie.src"

PROBES = {"pgie": {"pgie_source_probe"}}

EXPECTED_GPU = [
    {
        "frame_num": 0,
        "label": "person",
        "left": 64.81732177734375,
        "top": 301.4888916015625,
        "width": 73.27799224853516,
        "height": 220.6262969970703,
        "confidence": 0.9044251441955566,
    },
    {
        "frame_num": 0,
        "label": "person",
        "left": 288.8456726074219,
        "top": 318.9028625488281,
        "width": 18.09908103942871,
        "height": 45.25007247924805,
        "confidence": 0.9598023891448975,
    },
    {
        "frame_num": 0,
        "label": "person",
        "left": 1.6681976318359375,
        "top": 270.2680358886719,
        "width": 130.84967041015625,
        "height": 398.81494140625,
        "confidence": 0.9893208742141724,
    },
    {
        "frame_num": 0,
        "label": "person",
        "left": 198.725830078125,
        "top": 307.57794189453125,
        "width": 117.63912200927734,
        "height": 265.9861755371094,
        "confidence": 0.9998897314071655,
    },
]  # noqa: C0301
EXPECTED_JETSON = [
    {
        "frame_num": 0,
        "label": "person",
        "left": 306.3999938964844,
        "top": 324.1902160644531,
        "width": 18.40576171875,
        "height": 46.07585906982422,
        "confidence": 0.8086320161819458,
    },
    {
        "frame_num": 0,
        "label": "person",
        "left": 0.1695607453584671,
        "top": 267.9074401855469,
        "width": 137.39837646484375,
        "height": 406.4962463378906,
        "confidence": 0.9789136648178101,
    },
    {
        "frame_num": 0,
        "label": "person",
        "left": 288.3331604003906,
        "top": 319.6286926269531,
        "width": 17.49056053161621,
        "height": 43.15187454223633,
        "confidence": 0.983992338180542,
    },
    {
        "frame_num": 0,
        "label": "person",
        "left": 198.9019012451172,
        "top": 307.902099609375,
        "width": 117.9039077758789,
        "height": 260.23541259765625,
        "confidence": 0.9998049736022949,
    },
]  # noqa: C0301


def test_probe_print_console(tmpdir: Path) -> None:
    """Check pipeline with nvinfer probe outputs to json.

    Args:
        tmpdir: pytest fixture - temporary directory. Used to write
            pipeline file and python file with probes.

    """
    pipe = tmpdir / "pipeline.gstp"
    probesfile = tmpdir / "probes.py"
    shutil.copy(str(FIXTURE_PIPELINES / "4_minimal_nvinfer_jpeg"), str(pipe))

    probesfile.write_text(
        Path(json_probe.__file__).read_text(encoding="utf8"), encoding="utf8"
    )

    cmd = COMMAND.format(
        pipe=pipe,
        probesfile=probesfile,
        probe=json_probe._probe.__name__,  # noqa: W0212
    )

    logfile = Path(json_probe.JSONLINES_LOC)
    logfile.unlink(missing_ok=True)
    sp.check_call(split(cmd), text=True)  # noqa: S603

    expected = EXPECTED_JETSON if IS_JETSON else EXPECTED_GPU

    received = []
    for line_ in logfile.read_text(encoding="utf-8").splitlines():
        line = line_.strip()
        if not line:
            continue
        received.append(json.loads(line))
    assert roundup(received) == roundup(expected)
