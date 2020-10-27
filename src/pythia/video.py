# -*- coding: utf-8 -*-
""""""


from kivy.app import App
from kivy.properties import StringProperty
from kivy.core.camera.camera_gi import CameraGi
from kivy.uix.camera import Camera
from kivy.uix.image import Image

from pythia import logger
from pythia import Gst


def parse_launch(pipeline: str) -> str:
    pipeline = Gst.parse_launch(pipeline)
    if not pipeline:
        raise RuntimeError
    return pipeline


def on_eos(_, __, app):
    logger.info("Gstreamer: End-of-stream\n")
    app.stop()
    return True


def on_error(_, message, app):
    err, debug = message.parse_error()
    logger.error("Gstreamer: %s: %s\n" % (err, debug))
    app.stop()
    return True


class DeepstreamCamera(CameraGi):
    """Allow arbitrary gst-launch pipeline to be displayed from kivy.

    The following requirements must be met:

    1 The last pipeline element must be the following:

      `appsink name=camerasink emit-signals=True caps=video/x-raw,format=RGB`

    2 The pipeline must contain an element named "decoder". This is used
      internally by `kivy.core.camera.camera_gi.CameraGi` to extract the
      texturesize once a successful appsink `pull-sample` is emitter,
      with the following callback:

      ```python
      for pad in decoder.srcpads:
          s = pad.get_current_caps().get_structure(0)
          return (s.get_value('width'), s.get_value('height'))
      ```

    Additionally, if the pipeline contains an element named "observer".
    It will be used to ectract deepstream metadata
    """

    def __init__(self, *largs, **kwargs):
        self.app = App.get_running_app()
        self.pipeline_string = kwargs.pop("pipeline_string")
        super().__init__(*largs, **kwargs)
        if any(
            required not in self.pipeline_string
            for required in {"name=decoder", "name=camerasink", "appsink"}
        ):
            raise ValueError(
                """DeepstreamCamera `pipeline_string` kwarg must:
                1. Contain a gst element named decoder
                2. End in an appsink named `camerasink`
            """
            )

    def init_camera(self):
        # TODO: This doesn't work when camera resolution is resized at runtime.
        # There must be some other way to release the camera?
        if self._pipeline:
            self._pipeline = None
        self._pipeline = parse_launch(self.pipeline_string)
        self._camerasink = self._pipeline.get_by_name("camerasink")
        self._camerasink.connect("new-sample", self._gst_new_sample)
        self._decodebin = self._pipeline.get_by_name("decoder")

        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", on_eos, self.app)
        bus.connect("message::error", on_error, self.app)

        self._observer = self._pipeline.get_by_name("observer")
        if self._observer:
            self.app.monitor_detections(self._observer)

        if self._camerasink and not self.stopped:
            self.start()


class GSCameraWidget(Camera):
    """CameraWidget which receives arbitrary Gstreamer pipelines as
    parameter.

    TODO: sync resolution param with the output of the pipeline_string
    """

    pipeline_string = StringProperty()
    """Pipeline_string to build Gstreamer Pipeline."""

    def __init__(self, **kwargs):
        """Override to `fbind` `pipeline_string` as well."""
        self._camera = None
        super(Image, self).__init__(
            **kwargs
        )  # Image's init to avoid Camera to avoid Camera form calling `on_index` at the end of its constructor
        if self.index == -1:
            self.index = 0
        on_index = self._on_index
        fbind = self.fbind
        fbind("index", on_index)
        # fbind("resolution", on_index)
        fbind("pipeline_string", on_index)
        on_index()

    def _on_index(self, *largs):
        """Override super to enforce `DeepstreamCamera`"""
        self._camera = None
        if not self.pipeline_string:
            return
        self._camera = DeepstreamCamera(
            index=self.index,
            # resolution=self.resolution,
            pipeline_string=self.pipeline_string,
            stopped=True,
        )
        self._camera.bind(on_load=self._camera_loaded)
        if self.play:
            self._camera.start()
            self._camera.bind(on_texture=self.on_tex)
