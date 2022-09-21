"""Test external cli funcionality."""
from pathlib import Path

import pytest

from pythia.utils.message_handlers import GOT_EOS_FROM

from tests.paths import FIXTURE_PIPELINES
from tests.utils import _run_pipeline
from tests.utils import IS_JETSON


def _natural_sort_path(path: Path) -> int:
    return int(path.stem.split("_")[0])


ALL_PIPELINES = sorted(
    (
        p
        for p in FIXTURE_PIPELINES.rglob("[0-9]*_*")
        if p.stem[:3]
        in (
            "10_",
            "11_",
            "12_",
        )
    ),
    key=_natural_sort_path,  # type: ignore[arg-type]
)

KNOWN_ISSUES = {
    "10_ds_single_stream_nvinfer_b2b_tracker_tiler.jetson": "tracker not working in jetson",  # noqa: C0301
    "11_ds_multi_stream_nvinfer_b2b_tracker_tiler.jetson": "tracker not working in jetson",  # noqa: C0301
}


@pytest.mark.parametrize(
    "pipeline_file", ALL_PIPELINES, ids=[p.name for p in ALL_PIPELINES]
)
@pytest.mark.usefixtures("_nvidia_cooldown")
def test_run_pipeline_test(monkeypatch, pipeline_file: Path):
    """Test all fixture pipelines.

    Args:
        monkeypatch: monkeypatching Pytest fixture. Used by pipeline
            runner to temporarily patch eg env vars
        pipeline_file: File containing a gstreamer pipeline to run.

    """

    skip_known_description = KNOWN_ISSUES.get(pipeline_file.name, False)
    if skip_known_description:
        pytest.skip(
            "Known pipeline with issues. " f"Reason: {skip_known_description}"
        )
    if not IS_JETSON and (pipeline_file.suffix == ".jetson"):
        pytest.skip(
            "Test targets jetson. " f"Detected at {pipeline_file.name}"
        )

    if IS_JETSON and (pipeline_file.suffix == ".gpu"):
        pytest.skip("Test targets GPU. " f"Detected at {pipeline_file.name}")
    res = _run_pipeline(monkeypatch, pipeline_file)
    assert GOT_EOS_FROM in res, _no_eos(res)


def _no_eos(res):
    print(res)
    return "No EOS message - did the pipeline even run!?"
