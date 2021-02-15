# -*- coding: utf-8 -*-
"""Pythia - a minimal framework for deepstream and kivy.

.. versionadded:: 0.3.0
   * *perf* module, which allows to extract ds detections easily.

.. versionadded:: 0.4.0
   * *major refactor*: split metadata producer/consumers into separate
      modules.
"""

import os

import gi

gi.require_version("Gst", "1.0")
from gi.repository import GLib  # isort:skip
from gi.repository import GObject  # isort:skip
from gi.repository import Gst  # isort:skip

# HACK: until https://github.com/kivy/kivy/pull/7326 lands
# Although here we revert it by default to shush kivy
# <pwoolvett 2021-01-12T16:31>
TRUTHY = {"true", "1", "yes"}
os.environ.setdefault("KIVY_NO_ARGS", "true")
if os.environ["KIVY_NO_ARGS"] not in TRUTHY:
    del os.environ["KIVY_NO_ARGS"]
# END HACK

from kivy.logger import Logger as logger  # noqa: N813

logger.fixme = logger.debug

from pythia.consumer import Consumer
from pythia.producer import Producer

try:
    import pyds

    # fmt: off
    from pythia.deepstream.iterators import frames_per_batch   # isort:skip
    from pythia.deepstream.iterators import objects_per_frame   # isort:skip
    from pythia.deepstream.metadata_producers import ClassifierMetadataExtractor   # isort:skip
    from pythia.deepstream.metadata_producers import DetectorMetadataExtractor   # isort:skip
    from pythia.deepstream.metadata_producers import TrackerShadowMetadataExtractor   # isort:skip
    from pythia.deepstream.parsers import detector_bbox   # isort:skip
    from pythia.deepstream.parsers import last_bbox   # isort:skip
    from pythia.deepstream.parsers import past_bbox   # isort:skip
    from pythia.deepstream.parsers import tracker_bbox   # isort:skip
    # fmt: on

    PYDS_INSTALLED = True
except ImportError:
    PYDS_INSTALLED = False
    logger.warning(
        "Pythia+DS:"
        " Unable to import pyds modules."
        " Make sure to install pythia with the 'ds' extra."
    )

    frames_per_batch = None
    objects_per_frame = None
    ClassifierMetadataExtractor = None
    DetectorMetadataExtractor = None
    TrackerShadowMetadataExtractor = None
    detector_bbox = None
    last_bbox = None
    past_bbox = None
    tracker_bbox = None
