"""Deepstream interface, utilities and customization."""
from __future__ import annotations

import ctypes
from typing import Iterator
from typing import Literal

import gi

gi.require_versions(
    {
        "Gst": "1.0",
    }
)
from gi.repository import GLib  # noqa: C0413
from gi.repository import GObject  # noqa: C0413
from gi.repository import Gst  # noqa: C0413


def long_to_uint64(long: int) -> int:
    """Return the C 64-bit unsigned int datatype.

    Args:
        long: the long value to convert.

    Returns:
        The converted unit64

    """
    value = ctypes.c_uint64(long & 0xFFFFFFFFFFFFFFFF).value
    return value


def get_element(gst_bin: Gst.Bin, name) -> Gst.Element:
    """Get element from bin.

    Args:
        gst_bin: parent where the element is to be located.
        name: name of the element to locate.

    Returns:
        The found element.

    Raises:
        NameError: internal gst getter returned `None`.

    """
    element = gst_bin.get_by_name(name)
    if element:
        return element
    raise NameError(
        f"Gst Bin {gst_bin} does not contain an element named '{name}'"
    )


PadDirection = Literal["sink", "src"]


def get_static_pad(element: Gst.Element, direction: PadDirection) -> Gst.Pad:
    """Get static pad from element.

    Args:
        element: element where the pad is located.
        direction: pad direction - "sink" or "source".

    Returns:
        The found pad.

    Raises:
        ValueError: Unable to get the pad.

    """
    pad = element.get_static_pad(direction)  # type: ignore[arg-type]
    if pad:
        return pad
    raise ValueError(f"Unable to get {direction} pad from {element}")


def get_srcpad(gst_bin: Gst.Bin, element_name: str) -> Gst.Pad:
    """Get srcpad element from element.

    Args:
        gst_bin: parent where the element is to be located.
        element_name: name of the element to locate the source pad.

    Returns:
        The found source pad.

    """
    return get_static_pad(get_element(gst_bin, element_name), "src")


def get_sinkpad(gst_bin: Gst.Bin, element_name: str) -> Gst.Pad:
    """Get sinkpad element from element.

    Args:
        gst_bin: parent where the element is to be located.
        element_name: name of the element to locate the sink pad.

    Returns:
        The found source pad.

    """
    return get_static_pad(get_element(gst_bin, element_name), "sink")


def gst_iter(iterator: Gst.Iterator) -> Iterator:
    """Iterate pythonically over a :class:`Gst.Iterator`.

    Args:
        iterator: the iterator which produces values.

    Yields:
        The values from the iterator

    See Also:
        http://lazka.github.io/pgi-docs/index.html#Gst-1.0/classes/Iterator.html#Gst.Iterator

    """
    while iterator is not None:
        try:
            result, elem = iterator.next()
            if result is Gst.IteratorResult.OK:
                yield elem
            elif result is Gst.IteratorResult.DONE:
                break
            else:
                break
        except StopIteration:
            break


def gst_init() -> None:
    """Initialize Gstreamer."""
    if not Gst.is_initialized():
        Gst.init(None)  # type: ignore[call-arg]


def gst_deinit() -> None:
    """Initialize Gstreamer."""
    if Gst.is_initialized():
        Gst.deinit()  # type: ignore[call-arg]


def element_repr(element: Gst.Object) -> str:
    """Compute element strig based on its hierarchy.

    Args:
        element: The gstreamer element.

    Returns:
        The element's string representation.

    Example:
        >>> from gi.repository import Gst
        >>> Gst.init()
        >>> pipeline = Gst.parse_launch(
        ...   "bin ( videotestsrc ! identity name=eye ) ! fakesink"
        ... )
        >>> element_repr(pipeline.get_by_name("eye"))
        '/Pipeline:pipeline0/Bin:bin1/GstIdentity:eye'

    """
    if not isinstance(element, Gst.Element):
        return f"{element.__class__.__name__}:{str(element)}"

    string = ""
    while element:
        string = f"/{element.__class__.__name__}:{element.name}{string}"
        element = element.parent  # type: ignore[assignment]
    return string


__all__ = [
    "GLib",
    "Gst",
    "GObject",
    "long_to_uint64",
    "get_element",
    "PadDirection",
    "get_static_pad",
    "get_srcpad",
    "get_sinkpad",
    "gst_iter",
    "gst_init",
    "element_repr",
]
