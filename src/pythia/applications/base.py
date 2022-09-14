"""Application.

An application is composed of (at least) a pipeline. It implements two logics:

    State management: Start/Stop/Play/Pause of the pipeline.
    Bus Call

"""
from __future__ import annotations

import inspect
import os
from collections import defaultdict
from logging import getLogger
from pathlib import Path
from threading import Thread
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional
from typing import Type
from typing import TypeVar
from typing import Union

import pyds

from pythia.event_stream.base import Backend
from pythia.pipelines.base import BasePipeline
from pythia.pipelines.base import StringPipeline
from pythia.types import EventStreamUri
from pythia.types import Loop
from pythia.types import Probes
from pythia.types import SupportedCb
from pythia.utils.ds import info2batchmeta
from pythia.utils.gst import get_element
from pythia.utils.gst import get_static_pad
from pythia.utils.gst import GLib
from pythia.utils.gst import Gst
from pythia.utils.gst import gst_init
from pythia.utils.gst import PadDirection
from pythia.utils.message_handlers import on_message_eos
from pythia.utils.message_handlers import on_message_error

logger = getLogger(__name__)

GST_DEBUG_DUMP_DOT_DIR = os.environ.get("GST_DEBUG_DUMP_DOT_DIR", None)


class BackgroundLoop(Thread):
    """Simple thread to run a loop without blocking."""

    def __init__(self, *args, loop: Optional[Loop] = None, **kwargs):
        """Initialize a background thread to run the loop in.

        Args:
            args: Forwarded to thread constructor.
            loop: the loop to run. If not set, uses
                :class:`GLib.MainLoop`
            kwargs: Forwarded to thread constructor.

        """
        kwargs.setdefault("daemon", True)
        super().__init__(*args, **kwargs)
        self._loop = loop or GLib.MainLoop()

    def run(self) -> None:
        """Run and block running the loop."""
        self._loop.run()

    def quit(self) -> None:  # noqa: A003
        """Quit the running loop."""
        self._loop.quit()


def ensure_loop(loop: Optional[Loop]) -> Loop:
    """Return an existing loop.

    Args:
        loop: If set, the loop to return. Else, a new one is provieded.

    Returns:
        An exisitng loop, either the one received, or a new
        `GLib.MainLoop`, if one is received.

    """
    if loop:
        return loop
    return GLib.MainLoop()


BA = TypeVar("BA", bound="BaseApplication")

OnBusMessage = Callable[[BA, Gst.Bus, Gst.Message], None]


BoundGstPadProbeCallback = Callable[
    [BA, Gst.Pad, Gst.PadProbeInfo], Gst.PadProbeReturn
]
"""Gstreamer PadProbe must implement this protocol.

Using upstream 'Gst.PadProbeCallback' raises NotImplementedError.

"""
BoundBatchMetaCb = Callable[[BA, pyds.NvDsBatchMeta], Gst.PadProbeReturn]
BoundFullPadCb = Callable[
    [BA, Gst.Pad, Gst.PadProbeInfo, pyds.NvDsBatchMeta], Gst.PadProbeReturn
]

BoundSupportedCb = Union[
    BoundGstPadProbeCallback,
    BoundBatchMetaCb,
    BoundFullPadCb,
]

CB = TypeVar("CB", SupportedCb, BoundSupportedCb)


class BaseApplication:
    """Base pythia application to reduce boilerplate.

    You can define pipeline message handlers and they will be called
    when pertinent. For example, by defining a method called
    'on_message_error', pythia will connect said method as a signal
    handler for the 'message::eos' detailed signal. Only values from
    `Gst.MessageType` are allowed, see
    http://lazka.github.io/pgi-docs/index.html#Gst-1.0/flags.html#Gst.MessageType

    """

    def __init__(self, pipeline: BasePipeline) -> None:
        """Construct an application from a pipeline.

        Args:
            pipeline: an instantiated `Pipeline`.

        """
        self.pipeline = pipeline
        self.loop: Optional[BackgroundLoop] = None
        self._bus: Optional[Gst.Bus] = None
        self._registered_probes: Probes = defaultdict(
            lambda: defaultdict(list)
        )
        self._message_handlers = self._build_message_handlers()
        self.watch_ids: list[int] = []

    def _build_message_handlers(self) -> Dict[str, OnBusMessage]:
        handlers = {}
        for name in dir(self):
            if not name.startswith("on_message"):
                continue
            if name.startswith("on_message_"):
                key = "message::{}".format(  # noqa: C0209
                    name.split("on_message")[1].lstrip("_").replace("_", "-")
                )
            else:
                key = "message"
            handlers[key] = getattr(self, name)
        return handlers

    @classmethod
    def from_pipeline_string(
        cls: Type[BA], pipeline: str, extractors: Probes | None = None
    ) -> BA:
        """Factory from pipeline string.

        Args:
            pipeline: the string to use to generate the pipeline.
            extractors: buffer probes to inject to the pipeline.

        Returns:
            The instantiated app.

        """
        app = cls(StringPipeline(pipeline))
        app.inject_probes(extractors or {})
        return app

    @classmethod
    def from_pipeline_file(
        cls: Type[BA],
        pipeline_file: str | Path,
        *args,
        params: Dict[str, Any] | None = None,
        **kwargs,
    ) -> BA:
        """Factory from pipeline file.

        Args:
            pipeline_file: the string to use to generate the pipeline.
            params: Parameters to format the pipeline.
            args: Forwarded to :meth:`from_pipeline_file` factory.
            kwargs: Forwarded to :meth:`from_pipeline_file` factory.

        Returns:
            The instantiated app.

        """

        pipeline = Path(pipeline_file).read_text(encoding="utf-8")
        pipeline_string = pipeline.format_map(params or {})
        return cls.from_pipeline_string(pipeline_string, *args, **kwargs)

    @property
    def bus(self) -> Gst.Bus:
        """Get pipeline bus - lazy property.

        Returns:
            The pipeline's bus.

        Raises:
            RuntimeError: Unable to get bus from pipeline.

        """
        if self._bus is None:
            self._bus = self.pipeline.pipeline.get_bus()
            if self._bus is None:
                raise RuntimeError("Unable to get Pipeline bus")
        return self._bus

    def _before_pipeline_start(self, loop) -> BackgroundLoop:
        """Call hook - run before pipeline start.

        Args:
            loop: the loop to run.

        Returns:
            A thread running the background loop.

        """
        for element_name, connection in self.pipeline.CONNECTIONS.items():
            element = get_element(self.pipeline.pipeline, element_name)
            for signal, callback in connection.items():
                element.connect(signal, callback)

        self.connect_bus()
        self.loop = BackgroundLoop(loop=loop)
        self.loop.start()
        self.before_pipeline_start()
        return self.loop

    def before_pipeline_start(self) -> None:
        """Custom call hook - run before pipeline start."""

    def after_pipeline_start(self) -> None:
        """Call hook - run after pipeline start."""

    def before_loop_join(self) -> None:
        """Call hook - run before calling `loop.join`."""

    def before_loop_quit(self) -> None:
        """Call hook - run before calling `loop.quit`."""

    def connect_bus(self):
        """Attach bus signal watch depending on the message type."""
        if not self._message_handlers:
            return

        self.bus.add_signal_watch()
        self.watch_ids = [
            self.bus.connect(signal, handler)
            for signal, handler in self._message_handlers.items()
        ]

    def disconnect_bus(self):
        """Dettach bus signal watch."""
        if self.bus.have_pending():
            self.bus.set_flushing(True)
            self.bus.set_flushing(False)
        self.bus.remove_signal_watch()
        for watch_id in self.watch_ids:
            self.bus.disconnect(watch_id)
        self.watch_ids = []

    def __call__(
        self, *, loop: Optional[Loop] = None, foreground: bool = True
    ) -> None:
        """Execute the aplication and run its loop.

        Args:
            loop: if not set, one is provided.
            foreground: whether to block when running.

        Raises:
            RuntimeError: loop is already running.
            RuntimeError: Unable to start pipeline.

        """
        if self.loop:
            raise RuntimeError("Loop already running")

        gst_init()

        loop = self._before_pipeline_start(loop)
        try:
            self.pipeline.start()
        except RuntimeError:
            self.disconnect_bus()
            loop.quit()
            raise
        self.after_pipeline_start()

        self.before_loop_join()
        try:
            loop.join()
        finally:
            self.stop()

    def stop(
        self,
    ) -> None:
        """Stop application execution.

        A loop must be running, and it is stopped as well.

        Raises:
            RuntimeError: no loop set.
            RuntimeError: unabl to stop loop.

        """

        self.pipeline.stop()
        if self.loop is not None:
            try:
                self.before_loop_quit()
                self.loop.quit()
            except Exception as exc:  # pylint: disable=W0703
                raise RuntimeError(
                    f"Unable to stop application: ({exc})"
                ) from exc
            finally:
                self.loop = None

    def probe(
        self,
        element_name: str,
        pad_direction: PadDirection,
        *probe_args,
        pad_probe_type: Gst.PadProbeType = Gst.PadProbeType.BUFFER,
        backend_uri: Optional[EventStreamUri] = None,
    ):
        """Register function as a probe callback.

        Args:
            element_name: Name of the `Gst.Element` to attach the probe
                to.
            pad_direction: : Direction of the `Gst.Pad` to attach the
                probe to.
            probe_args: Optional additional args - forwarded to the
                decorated callback as varargs.
            pad_probe_type: Buffer probe type.
            backend_uri: If set, used to send messages from the probe to
                this remote backend. Only used (and mandatory in that
                case) when he callable to decorate is a generator.

        Returns:
            decorated callback, registered as an application buffer
                probe.

        This method has two usages: to decorate proper buffer probes,
        where the developer is in charge of handling the data, and to
        decorate a generator which yields incoming data. In the latter a
        'backend_uri' is required and used to connect and send any and
        all generated data into the remote service.

        """

        def decorator(user_probe: CB) -> CB:

            pythia_probe, backend = _build_probe(user_probe, backend_uri)

            element = get_element(self.pipeline.pipeline, element_name)
            pad = get_static_pad(element, pad_direction)
            pad.add_probe(
                pad_probe_type,  # type: ignore[arg-type]
                pythia_probe,  # type: ignore[arg-type]
                *probe_args,
            )
            self._registered_probes[element_name][pad_direction].append(
                {"probe": pythia_probe, "backend": backend}
            )
            return pythia_probe

        return decorator

    def inject_probes(self, extractors: Probes):
        """Register several probes.

        Args:
            extractors: mapping containing a collection of probes
                (callbacks) assigned to their respective element's
                source (or sink) pad.

        """
        for element, padprobes in extractors.items():
            for pad_direction, probes in padprobes.items():
                for probe in probes:
                    self.probe(element, pad_direction=pad_direction)(probe)

    def backend(
        self, element_name: str, pad_direction: PadDirection, idx: int = 0
    ) -> Backend:
        """Retrieve a backend for a registered generator probe.

        Args:
            element_name: Gstreamer element name the probe is registered
                to.
            pad_direction: The element's pad direction where the buffer
                probe is attached.
            idx: position in the registry array for the specified pad.
                As the most usual case a pad will have a single buffer
                probe, if this  value is not set it defaults to `0`,
                meaning the signle element in the list is retrieved.

        Returns:
            The backend associated with the generator probe. The backend
                is in charge of posting the messages from the generator
                probe to an external service.

        """
        return self._registered_probes[element_name][pad_direction][idx][
            "backend"
        ]


def _get_from_positional_arg_name(signature, name) -> Optional[int]:
    try:
        return signature.args.index(name)
    except ValueError:
        return None


def _get_from_annotations(signature, name) -> Optional[int]:
    try:
        return [
            signature.annotations.get(aa, None) for aa in signature.args
        ].index(name)
    except ValueError:
        return None


def _get_probe_batch_meta_idx(signature: inspect.FullArgSpec) -> Optional[int]:
    batch_meta_strats = [
        (_get_from_positional_arg_name, "batch_meta"),
        (_get_from_annotations, "pyds.NvDsBatchMeta"),
    ]
    batch_meta_idx = None
    for strategy, name in batch_meta_strats:
        batch_meta_idx = strategy(signature, name)
        if batch_meta_idx is not None:
            return batch_meta_idx
    return None


def _get_probe_pad_idx(signature: inspect.FullArgSpec) -> Optional[int]:
    pad_idx_strats = [
        (_get_from_positional_arg_name, "pad"),
        (_get_from_positional_arg_name, "gst_pad"),
        (_get_from_annotations, "Gst.Pad"),
    ]
    pad_idx = None
    for strategy, name in pad_idx_strats:
        pad_idx = strategy(signature, name)
        if pad_idx is not None:
            return pad_idx
    return None


def _get_probe_info_idx(signature: inspect.FullArgSpec) -> Optional[int]:
    info_idx_strats = [
        (_get_from_positional_arg_name, "info"),
        (_get_from_positional_arg_name, "gst_info"),
        (_get_from_annotations, "Gst.PadProbeInfo"),
    ]
    info_idx = None
    for strategy, name in info_idx_strats:
        info_idx = strategy(signature, name)
        if info_idx is not None:
            return info_idx
    return None


def _build_probe(probe, backend_uri: Optional[EventStreamUri] = None):
    signature = inspect.getfullargspec(probe)
    is_iterator = inspect.isgeneratorfunction(probe)
    if backend_uri and not is_iterator:
        raise ValueError("'backend_uri' set. Probe must be a generator.")
    if is_iterator and not backend_uri:
        backend_uri = os.getenv("PYTHIA_STREAM_URI", None)
        if not backend_uri:
            backend_uri = "log://?stream=stdout"
            logger.warning(
                "'backend_uri' not set."
                " It is mandatory with generator probes."
                " Defaulting to '%s'",
                backend_uri,
            )
    is_bound = hasattr(probe, "__self__")

    batch_meta_idx = _get_probe_batch_meta_idx(signature)
    pad_idx = _get_probe_pad_idx(signature)
    info_idx = _get_probe_info_idx(signature)

    supported = [
        ["batch_meta"],
        ["pad", "info"],
        ["pad", "info", "batch_meta"],
    ]
    err_tmp = (
        f"Unsupported spec {signature.args} for '{probe.__name__}'."
        f" Muse be one of `{supported}`"
    )

    if is_bound:
        pad_idx = (
            pad_idx - 1 if (is_bound and pad_idx is not None) else pad_idx
        )
        info_idx = (
            info_idx - 1 if (is_bound and info_idx is not None) else info_idx
        )
        batch_meta_idx = (
            batch_meta_idx - 1
            if (is_bound and batch_meta_idx is not None)
            else batch_meta_idx
        )

    if batch_meta_idx == 0 and (pad_idx is None) and (info_idx is None):
        if is_iterator and (backend_uri is not None):
            backend = Backend.from_uri(backend_uri)

            def pythia_iter_probe_batch_meta(
                _: Gst.Pad, info: Gst.PadProbeInfo
            ) -> Gst.PadProbeReturn:
                batch_meta = info2batchmeta(info)
                if not batch_meta:
                    return Gst.PadProbeReturn.OK
                for data in probe(batch_meta):
                    backend.post(data)
                return Gst.PadProbeReturn.OK

            return pythia_iter_probe_batch_meta, backend

        def pythia_probe_batch_meta(
            _: Gst.Pad, info: Gst.PadProbeInfo
        ) -> Gst.PadProbeReturn:
            batch_meta = info2batchmeta(info)
            if not batch_meta:
                return Gst.PadProbeReturn.OK
            return probe(batch_meta)

        return pythia_probe_batch_meta, None

    if pad_idx == 0 and info_idx == 1 and batch_meta_idx == 2:
        if is_iterator:
            raise NotImplementedError

        def pythia_probe_full(
            pad: Gst.Pad, info: Gst.PadProbeInfo
        ) -> Gst.PadProbeReturn:
            batch_meta = info2batchmeta(info)
            if not batch_meta:
                return Gst.PadProbeReturn.OK
            return probe(pad, info, batch_meta)

        return pythia_probe_full, None

    if pad_idx == 0 and info_idx == 1 and batch_meta_idx is None:
        if is_iterator:
            raise NotImplementedError

        return probe, None

    raise ValueError(err_tmp)


class Application(BaseApplication):
    """Typical pythia application."""

    on_message_eos = on_message_eos
    on_message_error = on_message_error
