# -*- coding: utf-8 -*-
"""Pythia - a minimal framework for deepstream and kivy

.. versionadded:: 0.3.0
   * *perf* module, which allows to extract ds detections easily.
"""

from kivy.logger import Logger as logger

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst

__version__ = "0.3.2"
__all__ = ["logger", "__version__", "Gst", "GObject"]
