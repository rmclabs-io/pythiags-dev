#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Headless Example.

This example demonstrates a simple use of the pythiags API.

"""

import abc
from typing import Dict
from typing import Optional
from typing import Tuple

from pythiags import GObject
from pythiags import Gst
from pythiags import logger
from pythiags.api import pythiagsRunner
from pythiags.consumer import Consumer
from pythiags.producer import Producer
from pythiags.video import parse_launch


class Standalone(pythiagsRunner, abc.ABC):
    def __init__(
        self,
        pipeline_string: str,
        metadata_extraction_map: Optional[
            Dict[str, Tuple[Producer, Consumer]]
        ] = None,
    ):
        super().__init__(
            pipeline_string,
            metadata_extraction_map=metadata_extraction_map,
        )
        self.loop: Optional[GObject.MainLoop] = None
        self._pipeline: Optional[Gst.Pipeline] = None

    def __call__(self, control_logs=True, *a, **kw):
        """Reverse __call__ order."""
        self.run()
        super().__call__(control_logs)

    def on_eos(self, bus, message):
        super().on_eos(bus, message)
        self.stop()

    def on_error(self, bus, message):
        super().on_error(bus, message)
        self.stop()

    @property
    def pipeline(self) -> Gst.Pipeline:
        """The low-level Gst.Pipeline Element."""
        if not self._pipeline:
            self._pipeline = parse_launch(self.pipeline_string)
        return self._pipeline

    def run(self):
        self.loop = GObject.MainLoop()
        self.pipeline.set_state(Gst.State.PLAYING)
        try:
            self.loop.run()
        except Exception as exc:
            logger.error(exc)
            raise
        finally:
            self.stop()

    def stop(self):
        self.pipeline.set_state(Gst.State.NULL)
        self.join()
