"""I want to quickly play an uri."""

import pytest

from tests.paths import DS_STREAMS


@pytest.mark.usefixtures("_nvidia_cooldown")
def test_demo():
    """Play a playbin pipeline.

    >>> from pythia import Demo
    >>> Demo.play(uri=..., background=False)

    ? Does background=True even make sense for cli appliacaitions?

    """

    from pythia import Demo
    from pythia.utils.gst import gst_init

    gst_init()
    Demo.play(
        f"file://{DS_STREAMS}/sample_720p.jpg",
        background=False,
    )
