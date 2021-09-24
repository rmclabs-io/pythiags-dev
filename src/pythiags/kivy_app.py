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
import time
from threading import Thread
from typing import Dict
from typing import Optional
from typing import Tuple

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.widget import Widget

from pythiags import Gst
from pythiags import logger
from pythiags.api import PythiaGsRunner
from pythiags.consumer import Consumer
from pythiags.exc import NoValidWindowProvider
from pythiags.producer import Producer
from pythiags.types import MetadataExtractionMap
from pythiags.utils import traced
from pythiags.video import GSCameraWidget
from pythiags.video import PythiaGsCamera


def set_resolution(w, h):
    from kivy.core.window import Window

    if not Window:
        raise NoValidWindowProvider

    Window.size = (w, h)


class PythiaGsApp(PythiaGsRunner, App, abc.ABC):
    def __init__(
        self,
        pipeline_string: str,
        metadata_extraction_map: Optional[
            Dict[str, Tuple[Producer, Consumer]]
        ] = None,
        resolution=None,
        **kwargs,
    ):
        self.resolution = resolution
        self.control_logs = kwargs.pop("control_logs", True)
        PythiaGsRunner.__init__(
            self,
            pipeline_string,
            metadata_extraction_map=metadata_extraction_map,
        )
        App.__init__(self, **kwargs)
        # TODO: use supers here <pwoolvett 2021-01-06T16:03:55>
        self._root: Optional[Widget] = None

    @abc.abstractmethod
    def on_first_frame_out(self):
        logger.debug("PythiaGsApp: Gstreamer pipeline ready")

    @abc.abstractmethod
    def get_camera(self) -> PythiaGsCamera:
        """Return `pythiags.video:GSCameraWidget` instance reference."""

    @property
    def pipeline(self):
        return self.get_camera()._camera._pipeline

    @abc.abstractmethod
    def build(self) -> Widget:
        """Return the root App widget."""

    def __call__(self, *a, **kw):
        """Reverse __call__ order."""
        logger.debug(f"PythiaGsApp: __call__")
        if self.resolution:
            set_resolution(*self.resolution)
        self.control_logs = kw.pop("control_logs", self.control_logs)
        self.run()

    def on_start_background(self):
        try:
            logger.debug(f"PythiaGsApp: on_start")

            camera = self.get_camera()._camera
            camera.set_state(Gst.State.PAUSED, on_err="warn")
            logger.debug(
                f"PythiaGsApp: on_start, pipeline status set to PAUSED"
            )
            PythiaGsRunner.__call__(self, self.control_logs)

            self.override_camera_first_frame_out_cb()
            camera.set_state(Gst.State.PLAYING)

            logger.debug(
                f"PythiaGsApp: on_start, pipeline status set to PLAYING"
            )
        except Exception as exc:
            logger.error(str(exc))
            Clock.schedule_once(lambda dt: self.stop())

    def on_start(self):
        Thread(target=self.on_start_background).start()

    def override_camera_first_frame_out_cb(self):
        cam_impl = self.get_camera()._camera
        original_cb = cam_impl.on_first_frame_out_ or (lambda: None)
        logger.debug(
            "PythiaGsApp: Camera `on_first_frame_out` %s", str(original_cb)
        )

        def on_first_frame_out_():
            original_cb()
            self.on_first_frame_out()

        cam_impl.on_first_frame_out_ = on_first_frame_out_
        logger.debug(
            "PythiaGsApp: Camera `on_first_frame_out` also calls %s",
            str(self.on_first_frame_out),
        )

    def on_eos(self, bus, message):
        super().on_eos(bus, message)
        self.stop()

    def on_error(self, bus, message):
        super().on_error(bus, message)
        self.stop()


class PythiaGsCli(PythiaGsApp):

    root: GSCameraWidget

    @property
    def pipeline(self) -> Gst.Pipeline:
        return self.root._camera._pipeline

    def build(self) -> GSCameraWidget:
        try:
            self.camera = GSCameraWidget(pipeline_string=self.pipeline_string)
        except ValueError as err:
            msg = (
                f"PythiaGsApp: Unable to intialize pipeline. Reason: {repr(err)}"
                ". Make sure the last element contains this: `appsink name=pythiags emit-signals=true caps=video/x-raw,format=RGB`"
            )
            logger.error(msg)
            raise
        return self.camera

    def get_camera(self):
        return self.camera

    def on_first_frame_out(self):
        super().on_first_frame_out()

    @classmethod
    def cli_run(
        cls,
        pipeline,
        *args,
        metadata_extraction_map: Optional[MetadataExtractionMap] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ):
        self = cls(pipeline, metadata_extraction_map)
        if timeout:
            pass
            # from kivy.app import App
            from kivy.clock import Clock

            # Clock.schedule_once(lambda dt: self.stop(), timeout)
            Clock.schedule_once(self.timeout_worker, timeout)
            # thread = Thread(target=self.timeout_worker, args=(timeout,))
            # thread.start()
        self.__call__()

    def timeout_worker(self, timeout: int):
        # running_time = 0
        # while running_time < timeout:
        #     time.sleep(1)
        #     running_time += 1
        self.pipeline.send_event(Gst.Event.new_eos())

    @traced(logger.info)
    def on_eos(self, *a, **kw):
        r = super().on_eos(*a, **kw)
        return r
