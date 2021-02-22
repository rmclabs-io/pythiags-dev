# -*- coding: utf-8 -*-
"""pythiags - a minimal framework for deepstream and kivy.

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

from pythiags.consumer import Consumer
from pythiags.producer import Producer

try:
    import pyds

    # fmt: off
    from pythiags.deepstream.iterators import frames_per_batch   # isort:skip
    from pythiags.deepstream.iterators import objects_per_frame   # isort:skip
    from pythiags.deepstream.metadata_producers import ClassifierMetadataExtractor   # isort:skip
    from pythiags.deepstream.metadata_producers import DetectorMetadataExtractor   # isort:skip
    from pythiags.deepstream.metadata_producers import TrackerShadowMetadataExtractor   # isort:skip
    from pythiags.deepstream.parsers import detector_bbox   # isort:skip
    from pythiags.deepstream.parsers import last_bbox   # isort:skip
    from pythiags.deepstream.parsers import past_bbox   # isort:skip
    from pythiags.deepstream.parsers import tracker_bbox   # isort:skip
    # fmt: on

    PYDS_INSTALLED = True
except ImportError:
    PYDS_INSTALLED = False
    logger.warning(
        "pythiags+DS:"
        " Unable to import pyds modules."
        " Make sure to install pythiags with the 'ds' extra."
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

PYTHIAGS_APPSINK_NAME = os.environ.get("PYTHIAGS_APPSINK_NAME", "pythiags")
