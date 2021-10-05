#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Headless Example.

This example demonstrates a simple use of the pythiags API.

"""

import abc
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional
from typing import Tuple

from pythiags import GLib
from pythiags import GObject
from pythiags import Gst
from pythiags import logger
from pythiags.api import PythiaGsRunner
from pythiags.background import PostponedBackgroundThread
from pythiags.background import run_later
from pythiags.consumer import Consumer
from pythiags.producer import Producer
from pythiags.types import MetadataExtractionMap
from pythiags.utils import SENTINEL
from pythiags.utils import parse_launch
from pythiags.utils import set_state
from pythiags.utils import traced

DEFAULT_RUN_AS_BACKGROUND = True


class RunDeprecatedMeta(type):
    def __new__(cls, name, bases, dct):
        obj = super().__new__(cls, name, bases, dct)
        if "run" in dct:
            raise DeprecationWarning(
                f"`{name}` should not define a `run` method, as `pythiags.headless.Standalone` does not rely on it anymore."
                " You can either (a) directly overload is `__call__` definition, or (b) use the `background` kwarg in `__call__` (or `__init__`)."
            )
        obj.attr = 100
        return obj


class StandaloneMeta(abc.ABCMeta, RunDeprecatedMeta):
    pass


class Standalone(
    PythiaGsRunner,
    abc.ABC,
    metaclass=StandaloneMeta,
):
    def __init__(
        self,
        pipeline_string: str,
        metadata_extraction_map: Optional[MetadataExtractionMap] = None,
        background: bool = DEFAULT_RUN_AS_BACKGROUND,
        on_background_failure: Optional[Callable[[Exception], Any]] = None,
    ):
        super().__init__(
            pipeline_string,
            metadata_extraction_map=metadata_extraction_map,
        )
        self.loop: Optional[GObject.MainLoop] = None
        self._pipeline: Optional[Gst.Pipeline] = None

        self.background = background
        self.on_background_failure = on_background_failure
        self.background_running_thread: Optional[
            PostponedBackgroundThread
        ] = None

    @property
    def background_state(self) -> Optional[PostponedBackgroundThread.States]:
        if not self.background_running_thread:
            return None
        return self.background_running_thread.state

    @classmethod
    def build_and_run(
        cls,
        pipeline,
        *args,
        metadata_extraction_map: Optional[MetadataExtractionMap] = None,
        background: bool = DEFAULT_RUN_AS_BACKGROUND,
        **kwargs,
    ):
        self = cls(
            pipeline_string=pipeline,
            metadata_extraction_map=metadata_extraction_map,
            background=background,
        )
        self.__call__(*args, **kwargs)
        return self

    cli_run = build_and_run

    def __call__(self, control_logs=True, background=SENTINEL):
        """Configure with super before calling run."""
        state = self.background_state
        if state:
            raise RuntimeError(f"already running! state={state}")
        super().__call__(control_logs)

        self.loop = GLib.MainLoop()
        logger.trace(f"setting {self}'s pipeline to PLAYING...")
        set_state(self.pipeline, Gst.State.PLAYING)

        if background == SENTINEL:
            background = self.background

        if not background:
            return self._run_foreground()

        return self._run_background()

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

    def _run_background(self):
        self.background_running_thread = th = run_later(
            cb=self._run_foreground,
            delay=0,
            on_success=None,
            on_failure=self.on_background_failure,
        )
        return th

    def _run_foreground(self):
        logger.trace(f"running {self}'s loop")
        try:
            self.loop.run()
        except Exception as exc:
            logger.exception(exc)
            raise
        except BaseException as exc:
            logger.exception(exc)
            raise
        finally:
            self.stop()

    @traced(logger.info)
    def stop(self):
        set_state(self.pipeline, Gst.State.NULL)
        self.join()
        self.loop.quit()
