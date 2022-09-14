"""Test Application API."""
import pytest

from pythia.applications.base import Application
from pythia.pipelines.base import Pipeline

from tests.utils import NO_NVIDIA


@pytest.mark.xfail(NO_NVIDIA, reason="Deepstream and or hardware crippled")
def test_no_model_application():
    """Check wether a minimal application can run."""
    pipeline = Pipeline(
        "test://?muxer_width=320&muxer_height=240&num_buffers=100",
        sink="fakesink",
    )
    app = Application(pipeline)
    # with timer(10, app.stop):
    app()
