#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Camera Example.

This example demonstrates a simple use of the camera. It shows a window
with a buttoned labelled 'play' to turn the camera on and off. Note that
not finding a camera, perhaps because gstreamer is not installed, will
throw an exception during the kv language processing.

Taken from kivy camera example https://kivy.org/doc/stable/examples/gen__camera__main__py.html.

Modified by RMCLabs @ Q4 2020 for demonstration purposes.

"""

import abc
from typing import Dict
from typing import Optional
from typing import Tuple

from kivy.app import App
from kivy.uix.widget import Widget

from pythia.api import PythiaRunner
from pythia.consumer import Consumer
from pythia.producer import Producer


class PythiaApp(PythiaRunner, App, abc.ABC):
    def __init__(
        self,
        pipeline_string: str,
        metadata_extraction_map: Optional[
            Dict[str, Tuple[Producer, Consumer]]
        ] = None,
        **kwargs
    ):
        self.control_logs = kwargs.pop("control_logs", True)
        PythiaRunner.__init__(
            self,
            pipeline_string,
            metadata_extraction_map=metadata_extraction_map,
        )
        App.__init__(self, **kwargs)
        # TODO: use supers here <pwoolvett 2021-01-06T16:03:55>
        self._root: Optional[Widget] = None

    @abc.abstractmethod
    def build(self) -> Widget:
        """Return the root App widget."""

    def __call__(self, *a, **kw):
        """Reverse __call__ order."""
        self.control_logs = kw.pop("control_logs", self.control_logs)
        self.run()

    def on_start(self):
        PythiaRunner.__call__(self, self.control_logs)

    def on_eos(self, bus, message):
        super().on_eos(bus, message)
        self.stop()

    def on_error(self, bus, message):
        super().on_error(bus, message)
        self.stop()