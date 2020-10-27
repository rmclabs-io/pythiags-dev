# -*- coding: utf-8 -*-
"""Pythia - a minimal framework for deepstream and kivy"""

from kivy.logger import Logger as logger

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst

__version__ = "0.2.0"
__all__ = ["logger", "__version__", "Gst"]
