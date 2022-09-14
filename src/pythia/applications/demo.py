"""Playbin."""

from pythia.applications.command_line import CliApplication
from pythia.utils.gst import gst_init


class _Demo(CliApplication):
    @classmethod
    def _play(cls, uri: str, *, background: bool = False) -> None:
        gst_init()
        app = cls.from_pipeline_string(f"playbin uri={uri}")
        if background:
            raise NotImplementedError("background mode not yet supported")
        app()

    play = _play


Demo = _Demo
