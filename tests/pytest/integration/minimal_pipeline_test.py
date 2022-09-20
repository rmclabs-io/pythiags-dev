"""Test pipeline functionality."""

from pathlib import Path

from pythia.pipelines.base import Pipeline

from tests.utils import cleanup
from tests.utils import diff

VIDEOTESTSRC = "test://?muxer_width=320&muxer_height=240"


def test_minimal_pipeline_no_model() -> None:
    """Check wether a pipeline with no model can run."""
    pipeline = Pipeline(VIDEOTESTSRC, models=[], sink="fakesink")
    expected_pipeline = """
        videotestsrc
        ! queue
        ! nvvideoconvert
        ! video/x-raw(memory:NVMM)
        ! m.sink_0
        nvstreammux
          name=m
          batch-size=1
          width=320
          height=240
        ! fakesink
    """
    real_pipeline = pipeline.gst()
    assert not diff(real_pipeline, real_pipeline), (
        f"Incorrect pipeline.\n"
        f"Expected:\n```gst\n{expected_pipeline}\n```\n"
        f"Received:\n```gst\n{real_pipeline}```"
    )


def test_minimal_pipeline_with_model_as_path(peoplesegnet: Path) -> None:
    """Check wether a pipeline runs with a model, specified as path.

    Args:
        peoplesegnet: directory to load a `Model` from.

    """

    pipeline = Pipeline(VIDEOTESTSRC, models=peoplesegnet, sink="fakesink")
    expected_pipeline = f"""
        videotestsrc
          num-buffers=-1
        ! queue
        ! nvvideoconvert
        ! video/x-raw(memory:NVMM)
        ! m.sink_0
        nvstreammux
          name=m
          batch-size=1
          nvbuf-memory-type=0
          width=320
          height=240
        ! nvinfer
          config-file-path={peoplesegnet.resolve()/'pgie.conf'}
          name=model_0
          unique-id=1
        ! fakesink
    """
    real_pipeline = pipeline.gst()
    assert cleanup(real_pipeline) == cleanup(expected_pipeline), (
        f"Incorrect pipeline.\n"
        f"Diff:\n```diff\n{diff(real_pipeline, expected_pipeline)}```"
    )
