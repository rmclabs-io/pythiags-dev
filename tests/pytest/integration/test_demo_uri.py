"""I want to quickly play an uri."""

from tests.paths import DS_STREAMS


def test_temo():
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


if __name__ == "__main__":
    test_temo()
