"""Test external cli funcionality."""
from pathlib import Path

import pytest

from pythia.utils.message_handlers import GOT_EOS_FROM

from tests.paths import FIXTURE_PIPELINES
from tests.utils import _run_pipeline
from tests.utils import IS_JETSON


def _natural_sort_path(path: Path) -> int:
    return int(path.stem.split("_")[0])


@pytest.mark.parametrize(
    "pipeline_file",
    sorted(
        (
            p
            for p in FIXTURE_PIPELINES.rglob("[0-9]*_*")
            if "skip" not in p.suffix
        ),
        key=_natural_sort_path,  # type: ignore[arg-type]
    ),
)
def test_run_pipeline_test(monkeypatch, pipeline_file: Path):
    """Test all fixture pipelines.

    Args:
        monkeypatch: monkeypatching Pytest fixture. Used by pipeline
            runner to temporarily patch eg env vars
        pipeline_file: File containing a gstreamer pipeline to run.

    """

    sp_kw = {}  # type: ignore[var-annotated]
    pipeline_string = pipeline_file.read_text()

    if (not IS_JETSON) and ("nvegltransform" in pipeline_string):
        pytest.skip("nvegltransform only availabe in jetson devices")

    res = _run_pipeline(monkeypatch, pipeline_file, **sp_kw)
    assert GOT_EOS_FROM in res, "No EOS message - did the pipeline even run!?"
