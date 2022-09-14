"""Common gstreamer pipeline bus message handlers."""

from typing import Protocol
from typing import Tuple

from pythia.utils.gst import element_repr
from pythia.utils.gst import Gst

GOT_EOS_FROM = "Got EOS from"


class Stoppable(Protocol):  # noqa: R0903
    """Interface for classes whihc implement the stop method.

    Mainly aimed at (but not restricted to) pythia apps.

    """

    def stop(self) -> None:  # noqa: C0116
        ...


def on_message_error(
    self: Stoppable,  # noqa: W0613
    bus: Gst.Bus,  # noqa: W0613
    message: Gst.Message,
) -> Tuple[str, str]:  # noqa: W0613
    """Stop application on error.

    Args:
        self: A stoppable instance.
        bus: The application's pipeline's bus.
        message: The gstreamer error message.

    Returns:
        Error and debug string.

    """
    err, debug = message.parse_error()
    src = message.src
    if isinstance(src, Gst.Element):
        print(f"ERROR: from element {element_repr(src)}:{err}")
    else:
        print(f"ERROR: from {src}:{err}")
    print(f"Additional debug info:\n{debug}")
    return err, debug


def on_state_change(
    self: Stoppable,  # noqa: W0613
    bus: Gst.Bus,  # noqa: W0613
    message: Gst.Message,
):  # noqa: W0613
    """Report application state changes.

    Args:
        self: A stoppable instance, in case an error arises.
        bus: The application's pipeline's bus.
        message: The gstreamer state change message.


    Returns:
        Old, new, and pending state

    """
    old, new, pending = message.parse_state_changed()
    print(
        f"STATE CHANGE@{element_repr(message.src)}: {old=}, {new=}, {pending=}"
    )
    return old, new, pending


def on_message_eos(
    self: Stoppable, bus: Gst.Bus, message: Gst.Message  # noqa: W0613
):
    """Stop application on EOS event.

    Args:
        self: A stoppable instance.
        bus: The application's pipeline's bus.
        message: The gstreamer state change message.

    """
    print(f"{GOT_EOS_FROM} {element_repr(message.src)}")
    self.stop()
