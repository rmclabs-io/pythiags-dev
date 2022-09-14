"""Common paths used throught tests."""

from os import getenv
from pathlib import Path

DS_PATH = Path(getenv("DS_PATH", "/opt/nvidia/deepstream/deepstream"))
DS_SAMPLES = DS_PATH / "samples"
DS_STREAMS = DS_SAMPLES / "streams"
DS_MODELS = DS_SAMPLES / "models"
PEOPLESEGNET = DS_MODELS / "peoplesegnet"
