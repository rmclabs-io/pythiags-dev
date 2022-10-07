"""Common paths used throught tests."""

from pathlib import Path

from pythia.paths import DS_MODELS
from pythia.paths import DS_PATH
from pythia.paths import DS_SAMPLES
from pythia.paths import DS_STREAMS
from pythia.paths import PEOPLESEGNET

TESTS = Path(__file__).parent
FIXTURE_DATA = TESTS / "fixture_data"
FIXTURE_PIPELINES = FIXTURE_DATA / "pipelines"
FIXTURE_CONFIGS = FIXTURE_DATA / "configs"
PROJECT_ROOT = TESTS.parent
README = PROJECT_ROOT / "README.md"
DOCKER = PROJECT_ROOT / "docker"

DPA = DS_PATH / "sources/deepstream_python_apps"

ANALYTICS = FIXTURE_CONFIGS / "analytics.conf"
TRACKER = FIXTURE_CONFIGS / "tracker_NvDCF_perf.yml"

__all__ = [
    "TESTS",
    "FIXTURE_DATA",
    "FIXTURE_PIPELINES",
    "DS_PATH",
    "DS_MODELS",
    "DS_SAMPLES",
    "DS_STREAMS",
    "PEOPLESEGNET",
    "PROJECT_ROOT",
    "README",
    "DOCKER",
    "DPA",
    "TRACKER",
    "ANALYTICS",
]
