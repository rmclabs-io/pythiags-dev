"""Video Recorder package.

Contains default ringbuffer, recordbin and videorecorder
implementations.

Equipped with the ringbuffer and recordbin, the videorecorder allows to
record videos by attaching the ringbuffer to a pipeline, and (once
:meth:`Videorecorder.record` has been called), dynamically attaches the
recordbin to push buffers from the ringbuffer to a :class   :`Gst.Filesink`.

"""

from pythiags.recorder.recorder import VideoRecorder

__all__ = ["VideoRecorder"]
