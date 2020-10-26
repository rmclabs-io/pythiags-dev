# -*- coding: utf-8 -*-
""""""
import os
from sys import argv
from sys import exit
from pathlib import Path
from typing import List

from kivy.logger import Logger

from pythia.app import PythiaApp
from pythia.pipeline import build_pipeline

DEMO_PIPELINE = """\
    videotestsrc
    ! decodebin name=decoder
    ! videoconvert
    ! appsink name=camerasink emit-signals=True caps=video/x-raw,format=RGB
"""

PROD_PIPELINE = build_pipeline(
    640,
    480,
    960,
    544,
    1280,
    720,
    30,
    "/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_infer_primary.txt",
    [2, 5, 8],
)


def build_pipeline_string(mode:List[str]):
    if not mode:
        Logger.error(
            "A Gst pipeline with gstlaunch syntax is required. Alternatively, pass `demo` or `prod`"
        )
        exit(1)
    if mode[0] == "demo":
        return DEMO_PIPELINE

    if mode[0] == "prod":
        return PROD_PIPELINE

    if mode[0] == "json":
        from json import load
        with open(Path.cwd() / "pythia.json", "r") as cfg:
            data = load(cfg)
        return build_pipeline(**data)
    return " ".join(mode)


def main(arg=None):
    os.environ["DBUS_FATAL_WARNINGS"] = "0"
    os.environ["DISPLAY"] = ":0"

    pipeline = build_pipeline_string(arg or argv[1:])
    PythiaApp(pipeline).run()


if __name__ == "__main__":
    main()
