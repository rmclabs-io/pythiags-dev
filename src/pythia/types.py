"""Types for pythia."""

from __future__ import annotations

from typing import Any
from typing import Callable
from typing import Dict
from typing import Protocol
from typing import TYPE_CHECKING
from typing import TypedDict
from typing import TypeVar
from typing import Union

import pyds

from pythia.utils.gst import Gst
from pythia.utils.gst import PadDirection

if TYPE_CHECKING:
    from pythia.event_stream import base as base_stream


Serializable = Dict[str, Any]
EventStreamUri = str

SourceUri = str
"""should start with `scheme://`.


* multifilesink usese `multifile://` for the uri.
* v4l2src uses `v4l2://` for the uri.
* filesrc uses `file://` for the uri.

See Also:
https://gstreamer.freedesktop.org/documentation/gstreamer/gsturihandler.html?gi-language=c#GstURIHandler
"""

SinkUri = str
"""

Examples:

    /path/to/video.mp4
    /path/to/frames/%04d.jpg
    livesink -> nveglglessink
    fakesink -> fakesink
    appsink -> TODO
"""


class Loop(Protocol):
    """A loop interface, where code is executed.

    Example:
        >>> from gi.repository import GLib
        >>> loop = GLib.MainLoop()

    """

    def run(self) -> Any:  # noqa: A003, C0116
        ...

    def quit(self) -> Any:  # noqa: A003, C0116
        ...


PC = TypeVar("PC", bound="PydsClass")


PydsClass = Union[
    pyds.NvDsAnalyticsFrameMeta,
    pyds.NvDsAnalyticsObjInfo,
    pyds.NvDsInferSegmentationMeta,
    pyds.NvDsUserMeta,
    pyds.NvDsLabelInfo,
    pyds.NvDsFrameMeta,
    pyds.NvDsObjectMeta,
    pyds.NvDsClassifierMeta,
]
"""Common pyds metadata class API."""


class RegisteredProbe(TypedDict):
    """Simple storage for generator-induced buffer probes."""

    probe: SupportedCb
    backend: base_stream.Backend


Probes = Dict[str, Dict[PadDirection, list]]

GstPadProbeCallback = Callable[[Gst.Pad, Gst.PadProbeInfo], Gst.PadProbeReturn]
"""Gstreamer PadProbe must implement this protocol.

Using upstream 'Gst.PadProbeCallback' raises NotImplementedError.

"""
BatchMetaCb = Callable[[pyds.NvDsBatchMeta], Gst.PadProbeReturn]
FullPadCb = Callable[
    [Gst.Pad, Gst.PadProbeInfo, pyds.NvDsBatchMeta], Gst.PadProbeReturn
]
SupportedCb = Union[
    GstPadProbeCallback,
    BatchMetaCb,
    FullPadCb,
]


PT = TypeVar(
    "PT",
    GstPadProbeCallback,
    BatchMetaCb,
    FullPadCb,
)

Con = Dict[str, Dict[str, Callable]]
"""Mapping of element-name to gst elements' signal callbacks.

Example:
    >>> def cb(*a, **kw): ...
    >>> con = {"pgie": {"pad-added": cb}}
"""


class HasConnections(Protocol):
    """Protocol to indicate a class has connections.

    See Also:
        :obj:`Con`

    """

    CONNECTIONS: Con
