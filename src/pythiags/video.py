# -*- coding: utf-8 -*-
""""""

import atexit
import sys
from ctypes import Structure
from ctypes import c_int
from ctypes import c_void_p
from ctypes import string_at
from typing import Callable
from typing import Optional
from typing import TypeVar
from weakref import ref

from kivy.clock import Clock
from kivy.core.camera import CameraBase
from kivy.graphics.texture import Texture
from kivy.properties import StringProperty
from kivy.support import install_gobject_iteration
from kivy.uix.camera import Camera
from kivy.uix.image import Image

from pythiags import PYTHIAGS_APPSINK_NAME
from pythiags import GLib
from pythiags import Gst
from pythiags import logger

Gst.init(None)
try:
    install_gobject_iteration()
except AttributeError as exc:
    if "sphinx-build" in sys.argv[0]:
        # NOTE: kivy.clock.Clock is not available <pwoolvett 2021-01-27T18:24:30>
        logger.warning(exc)
    else:
        raise


def parse_launch(gstlaunch_pipeline: str) -> str:
    try:
        pipeline = Gst.parse_launch(gstlaunch_pipeline)
    except GLib.GError as exc:
        msg = str(exc)
        if "{" in msg:
            msg += ". Maybe you forgot to add pipeline kwargs?"
        logger.error(msg)
        raise RuntimeError(msg) from exc

    if not pipeline:
        msg = f"Unable to initialize Gstreamer Pipeline"
        logger.error(msg)
        raise RuntimeError(msg)
    return pipeline


def get_by_name(pipeline: Gst.Pipeline, name: str) -> Gst.Element:
    element = pipeline.get_by_name(name)
    if element:
        return element
    raise ValueError(f"{pipeline}.get_by_name('{name}') returned None")


def get_static_pad(element: Gst.Element, padname: str) -> Gst.Pad:
    pad = element.get_static_pad(padname)
    if pad:
        return pad
    raise ValueError(f"{element}.get_static_pad('{padname}') returned None")


def on_eos(_, __, app):
    logger.info("Gstreamer: End-of-stream\n")
    app.stop()
    return True


def on_error(_, message, app):
    err, debug = message.parse_error()
    logger.error("Gstreamer: %s: %s\n", err, debug)
    app.stop()
    return True


def validate_appsink(pipeline):
    sink = get_by_name(pipeline, PYTHIAGS_APPSINK_NAME)
    klass = type(sink).__name__
    if klass != "GstAppSink":
        msg = f"The {PYTHIAGS_APPSINK_NAME} element must be an appsink, not {klass}!"
        logger.error(f"PythiaGsVideo: {msg}")
        raise ValueError(msg)

    return sink


C = TypeVar("C", bound="PythiaGsCamera")


class StateChangeFailed(RuntimeError):
    pass


class PythiaGsCamera(CameraBase):
    """Allow arbitrary gst-launch pipeline to be displayed from kivy.

    The following requirements must be met:

    1 The last pipeline element must be the following:

      `appsink name=pythiags emit-signals=True caps=video/x-raw,format=RGB`

    2 The pipeline must contain an element named "decoder". This is used
      internally by `kivy.core.camera.camera_gi.CameraGi` to extract the
      texturesize once a successful appsink `pull-sample` is emitter,
      with the following callback:

      .. code-block:: python

         for pad in decoder.srcpads:
             s = pad.get_current_caps().get_structure(0)
             return (s.get_value('width'), s.get_value('height'))

    Additionally, if the pipeline contains an element named "observer".
    It will be used to ectract deepstream metadata

    .. seealso:: kivy.core/camera/camera_gi.CameraGi - this class is
        based on that

    """

    _instances = []

    class MapInfo(Structure):
        _fields_ = [("memory", c_void_p), ("flags", c_int), ("data", c_void_p)]
        # we don't care about the rest

    def __init__(
        self,
        pipeline_string,
        on_first_frame_out: Callable[
            [
                C,
            ],
            None,
        ] = None,
        **kwargs,
    ):
        self.pipeline_string = pipeline_string
        self.on_first_frame_out_ = on_first_frame_out
        self._pipeline: Optional[Gst.Pipeline] = None
        self._register_ref()
        kwargs.setdefault("resolution", (-1, -1))
        super().__init__(**kwargs)

    def _register_ref(self):
        cls = type(self)

        def _on_unref(instance):
            if instance in cls._instances:
                cls._instances.remove(instance)

        cls._instances.append(ref(self, _on_unref))

    def init_camera(self):
        if self._pipeline:
            self._pipeline = None
        self._pipeline = parse_launch(self.pipeline_string)

        self._sink = validate_appsink(self._pipeline)
        get_static_pad(self._sink, "sink").add_probe(
            Gst.PadProbeType.BUFFER, self.on_first_frame_out
        )
        self._sink.connect("new-sample", self._gst_new_sample)

        if self._sink and not self.stopped:
            self.start()

    def on_first_frame_out(self, pad, _):
        struct = pad.get_current_caps().get_structure(0)

        self._texturesize = (
            struct.get_value("width"),
            struct.get_value("height"),
        )
        if self.resolution == (-1, -1):
            self._resolution = self._texturesize

        if self.on_first_frame_out_:
            self.on_first_frame_out_()
        return Gst.PadProbeReturn.REMOVE

    def _gst_new_sample(self, _):
        sample = self._sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.ERROR

        self._sample = sample
        Clock.schedule_once(self._update)
        return Gst.FlowReturn.OK

    def start(self):
        super().start()
        self.set_state(Gst.State.PLAYING)

    def stop(self, on_err="raise"):
        super().stop()
        self.set_state(Gst.State.PAUSED, on_err=on_err)

    def unload(self, on_err="raise"):
        self.set_state(Gst.State.NULL, on_err=on_err)

    def set_state(self, state: Gst.State, on_err="raise"):
        try:
            result = self._pipeline.set_state(state)
            if result == Gst.StateChangeReturn.FAILURE:
                msg = f"{type(self).__name__}: Unable to change state to {state.value_name} - you should check your pipeline"
                raise StateChangeFailed(msg)
        except (AttributeError, StateChangeFailed) as err:
            if on_err == "warn":
                return logger.error(err)
            if on_err == "raise":
                raise

    def _update(self, dt):
        sample, self._sample = self._sample, None
        if sample is None:
            return
        if self._texture is None:
            self._texture = Texture.create(
                size=self._texturesize, colorfmt="rgb"
            )
            self._texture.flip_vertical()
            self.dispatch("on_load")

        # decode sample
        # read the data from the buffer memory
        try:
            buf = sample.get_buffer()
            _, mapinfo = buf.map(Gst.MapFlags.READ)

            # We cannot get the data out of mapinfo, using Gst 1.0.6 + Gi 3.8.0
            # related bug report:
            # https://bugzilla.gnome.org/show_bug.cgi?id=6t8663
            # ie: mapinfo.data is normally a char*, but here, we have an int
            # So right now, we use ctypes instead to read the mapinfo ourself.
            addr = mapinfo.__hash__()
            c_mapinfo = self.MapInfo.from_address(addr)

            # now get the memory
            self._buffer = string_at(c_mapinfo.data, mapinfo.size)
            self._copy_to_gpu()
        finally:
            if mapinfo is not None:
                buf.unmap(mapinfo)

    @classmethod
    def camera_gi_clean(cls):
        """Forcing the stop/unload of all remaining videos before  exiting the
        python process.

        If we leave the python process with some video running, we can
        hit a segfault.

        """
        for weakcamera in cls._instances:
            camera = weakcamera()
            if isinstance(camera, PythiaGsCamera):
                camera.stop(on_err="ignore")
                camera.unload(on_err="ignore")


class GSCameraWidget(Camera):
    """CameraWidget which receives arbitrary Gstreamer pipelines as parameter.

    TODO: sync resolution param with the output of the pipeline_string

    """

    pipeline_string = StringProperty()
    """Pipeline_string to build Gstreamer Pipeline."""

    def __init__(self, **kwargs):
        """Override to `fbind` `pipeline_string` as well."""
        self._camera = None
        super(Image, self).__init__(
            **kwargs
        )  # Image's init to avoid Camera form calling `on_index` at the end of its constructor
        if self.index == -1:
            self.index = 0
        on_index = self._on_index
        fbind = self.fbind
        fbind("index", on_index)
        # fbind("resolution", on_index)
        fbind("pipeline_string", on_index)
        on_index()

    def _on_index(self, *largs):
        """Override super to enforce `PythiaGsCamera`"""
        self._camera = None
        if not self.pipeline_string:
            return
        self._camera = PythiaGsCamera(
            index=self.index,
            # resolution=self.resolution,
            pipeline_string=self.pipeline_string,
            stopped=True,
        )
        if self.play:
            self._camera.start()
        self._camera.bind(on_texture=self.on_tex)


atexit.register(PythiaGsCamera.camera_gi_clean)
