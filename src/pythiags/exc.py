# -*- coding: utf-8 -*-
"""Custom pythiags Exceptions."""


class GstEos(Exception):
    """Gstreamer End of Stream received."""

    def ___repr__(self):
        return "Gstreamer End-of-Stream"


class GstError(Exception):
    """Generic Gstreamer Error received."""

    def ___repr__(self):
        return "Gstreamer Error"