import abc

from pythia import Gst
from pythia.models import Events


class Producer(abc.ABC):
    """Interface to connect as buffer probe.

    .. seealso:: pyds iterators in `pythia.pyds_iterators`. .. seealso::
    pyds parsers in `pythia.pyds_parsers`.

    """

    @abc.abstractmethod
    def extract_metadata(self, pad: Gst.Pad, info: Gst.PadProbeInfo) -> Events:
        """Extract metadata (eg pyds detection), bufferprobe callback.

        It is in charge of receiving, decoding & outputing metadata from
        probe.

        Args:
            pad: Where the callback is attached
            info: Callback information

        Returns:
            Events for a single buffer batch. May be empty.

        .. important:: This callback holds buffer flow downstream, so
           its implementation must be as fast as possible.

        """
