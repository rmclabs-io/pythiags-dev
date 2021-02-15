import os
import subprocess as sp
from pathlib import Path
from shlex import split

import pytest
from tests.paths import DS_PIPELINES
from tests.paths import GST_PIPELINES

import pythia
from pythia.utils import module_from_file

DEEPSTREAM_ELEMENTS = {
    "nvinfer",
    "nvtracker",
    "nvvideoconvert",
    "nvjpeg",
    "nvmultistreamtiler",
}

GST_BASE_PLUGINS_NOT_IN_DS = {
    "xvimagesink",
}


def in_docker() -> bool:
    """Check if running inside docker.

    Returns:
        True if running in a Docker container, else False

    """
    try:
        with open("/proc/1/cgroup", "rt") as ifh:
            data = ifh.read()
        return any(pat in data for pat in {"docker", "kubepod"})
    except Exception:  # noqa: W0703
        return False


def gst_launch(pipeline_path):
    with open(pipeline_path) as fp:
        pipeline = fp.read()
    if not pythia.PYDS_INSTALLED:
        if any(ds_element in pipeline for ds_element in DEEPSTREAM_ELEMENTS):
            pytest.skip("pyds not installed")
    if in_docker():
        if any(
            gst_element in pipeline
            for gst_element in GST_BASE_PLUGINS_NOT_IN_DS
        ):
            pytest.skip("Running from docker")

    env = dict(os.environ)
    with pytest.raises(sp.TimeoutExpired):
        return sp.check_call(  # noqa: S603
            split(f"gst-launch-1.0 -e {pipeline}"),
            env=env,
            timeout=5,
        )


@pytest.mark.incremental
class TestGstreamer:
    @pytest.mark.skip(not pythia.PYDS_INSTALLED, "pyds not installed")
    def import_pyds(self):
        import pyds  # noqa: F401
        import pyds_bbox_meta  # noqa: F401
        import pyds_tracker_meta  # noqa: F401

    @pytest.mark.skip(not pythia.PYDS_INSTALLED, "pyds not installed")
    def check_plugins(self):
        gst_inspect = sp.check_output(  # noqa: S603
            split("gst-inspect-1.0")
        ).decode("utf8")
        for required in DEEPSTREAM_ELEMENTS:
            assert required in gst_inspect

    @pytest.mark.parametrize("pipeline_path", [*GST_PIPELINES.glob("*")])
    def test_gst_launch(self, pipeline_path):
        return gst_launch(pipeline_path)


@pytest.mark.parametrize("pipeline_path", [*DS_PIPELINES.glob("*")])
def test_deepstream(pipeline_path):
    if not pythia.PYDS_INSTALLED:
        pytest.skip("pyds not installed")
    return gst_launch(pipeline_path)


def test_kivy():
    import kivy
    from kivy.clock import Clock

    renderer = module_from_file(
        str(Path(kivy.examples_dir) / "canvas/rounded_rectangle.py")
    )

    class Demo(renderer.DrawRoundedRectanglesApp):  # noqa: R0903
        def on_start(self):
            Clock.schedule_once(lambda dt: self.stop(), 2)

    return Demo().run()
