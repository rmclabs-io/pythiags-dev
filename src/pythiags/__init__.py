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
gi.require_version("GstApp", "1.0")
from gi.repository import GLib  # isort:skip
from gi.repository import GObject  # isort:skip
from gi.repository import Gst  # isort:skip
from gi.repository import GstApp  # isort:skip

from pythiags._setup import logger
from pythiags._setup import version as __version__
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
    logger.debug("PythiaGs: Module pyds succesfully loaded")
except ImportError:
    PYDS_INSTALLED = False
    logger.warning(
        "PythiaGs: Unable to import pyds module. Make sure to install pythiags with the 'ds' extra."
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

try:
    import kivy

    KIVY_INSTALLED = True
    del kivy
except ImportError:
    KIVY_INSTALLED = False
    logger.warning(
        "Unable to import kivy module. Make sure to install pythiags with the 'kivy' extra."
    )

if "DISPLAY" not in os.environ:
    logger.warning("DISPLAY env var not set! This will cause errors")

Gst.init(None)

PYTHIAGS_APPSINK_NAME = os.environ.get("PYTHIAGS_APPSINK_NAME", "pythiags")
