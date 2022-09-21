"""Playbin."""

from pythia.applications.command_line import CliApplication
from pythia.utils.ext import IS_JETSON
from pythia.utils.gst import gst_init


class _Demo(CliApplication):
    @classmethod
    def _play(cls, uri: str, *, background: bool = False) -> None:
        gst_init()
        egltransform = "nvegltransform ! " if IS_JETSON else ""
        app = cls.from_pipeline_string(
            f"uridecodebin uri={uri} ! {egltransform}nveglglessink"
        )
        if background:
            raise NotImplementedError("background mode not yet supported")
        app()

    play = _play


Demo = _Demo
