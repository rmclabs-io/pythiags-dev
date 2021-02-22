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
from pythiags.api import PythiaGsRunner
from pythiags.consumer import Consumer
from pythiags.producer import Producer
from pythiags.types import MetadataExtractionMap
from pythiags.video import parse_launch


class Standalone(PythiaGsRunner, abc.ABC):
    def __init__(
        self,
        pipeline_string: str,
        metadata_extraction_map: Optional[MetadataExtractionMap] = None,
    ):
        super().__init__(
            pipeline_string,
            metadata_extraction_map=metadata_extraction_map,
        )
        self.loop: Optional[GObject.MainLoop] = None
        self._pipeline: Optional[Gst.Pipeline] = None

    @classmethod
    def cli_run(
        cls,
        pipeline,
        *args,
        metadata_extraction_map: Optional[MetadataExtractionMap] = None,
        **kwargs,
    ):
        self = cls(
            pipeline_string=pipeline,
            metadata_extraction_map=metadata_extraction_map,
        )
        self.__call__(*args, **kwargs)

    def __call__(self, control_logs=True):
        """Configure with super before calling run."""
        super().__call__(control_logs)
        self.run()

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
            logger.warning("Exc")
            logger.error(exc)
            raise
        finally:
            self.stop()

    def stop(self):
        logger.warning("PythiaGsHeadless: Stopping")
        self.pipeline.set_state(Gst.State.NULL)
        logger.warning("PythiaGsHeadless: calling self.join")
        self.join()
        self.loop.quit()
