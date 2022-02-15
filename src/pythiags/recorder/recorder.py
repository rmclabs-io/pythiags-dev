"""Video Recorder module for pythiags.

Example:

"""

# region imports ##############################################################
import collections
import enum
from datetime import datetime
from time import sleep
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional
from typing import Type

from pythiags import Gst
from pythiags import logger
from pythiags.background import CancelNotInWaiting
from pythiags.background import PostponedBackgroundThread
from pythiags.background import exit_from_thread
from pythiags.background import run_later
from pythiags.recorder.record_bin import RecordBin
from pythiags.recorder.ring_buffer import RingBuffer
from pythiags.utils import send_event
from pythiags.utils import traced

# endregion imports ####################################################


class States(enum.IntFlag):
    """Possible states for the :class:`Recorder`."""

    DETTACHED = 0
    """The ringbuffer is not connected."""

    BUFFERING = 1
    """The ringbuffer is connected and buffering - pipeline fixed."""

    STARTING = 2
    """Connecting record bin - pipeline in modification."""

    RECORDING = 4
    """Recordbin recording to file - pipeline fixed."""

    FINISHING = 8
    """Recordbin file finishing - pipeline in modification."""


OnVideoFinished = Callable[[str], Any]
OnRecord = Callable[[Optional[OnVideoFinished]], None]


class VideoRecorder:
    """Record videos including past and future frames.

    Allow the creation of video files containing frames before a
    record event is received, by keeping a ringbuffer containing
    previous frames.

    Example:
        The following example creates a `demo_video.webm` file
        containing buffers from two seconds *before* the
        :meth:`record` method is called, and up to two seconds into
        the future (or an EOS is received).

        >>> pipeline:Gst.pipeline = ... # should contain a named `tee`
        >>> recorder = VideoRecorder(
        ...     pipeline=pipeline,
        ...     src_tee_name="t1",  # the name of the menioned tee
        ...     filename_generator=lambda: "demo_video.webm",
        ...     timeout_sec=0.1,
        ...     window_size_sec=2,
        ... )
        >>> video_path = recorder.record()

    """

    def __init__(
        self,
        pipeline: Gst.Pipeline,
        src_tee_name: str,
        filename_generator: Callable[[], str],
        timeout_sec: float,
        window_size_sec: float,
        ring_buffer_cls: Type[RingBuffer] = RingBuffer,
        record_bin_cls: Type[RecordBin] = RecordBin,
    ):
        """Constructor.

        Args:
            pipeline: A :class:`Gst.Pipeline` object to attach to. It must
                contain at least a named :class:`Gst.Tee` element.
            src_tee_name: Name of the pipeline's tee.
            filename_generator: Function to call to dynamically generate
                new filenames on disjoint video records.
            timeout_sec: Raise if unable to attach after this
                value has passed [Unused] .
            window_size_sec: How long before and after a :meth:`record`
                is called to record a video. Together with the
                `pipeline`s framerate, determines the ringbuffer
                size.
            ring_buffer_cls: Custom :class:`RingBuffer` implementation.
            record_bin_cls: Custom :class:`RecordBin` implementation.

        """
        self.pipeline = pipeline

        self._state: States = States.DETTACHED
        self._deque: Optional[collections.deque] = None
        self._stop_recording_timer: Optional[PostponedBackgroundThread] = None
        self.ring_buffer = ring_buffer_cls(
            src_tee_name,
            window_size_sec,
        )
        self.record_bin = record_bin_cls(
            filename_generator,
            timeout_sec,
        )

        self.on_record_dispatch: Dict[States, OnRecord] = {
            States.DETTACHED: self._on_dettached_record,
            States.BUFFERING: self._on_buffering_record,
            States.STARTING: self._on_starting_record,
            States.RECORDING: self._on_recording_record,
            States.FINISHING: self._on_finishing_record,
        }
        """Map :attr:`state`'s to callbacks when :meth:`record` is called.

        By default, the mapping has the following form:

            * States.DETTACHED: Re-schedule the record after a delay.
            * States.BUFFERING: Reset timer and bind the recordbin.
            * States.STARTING: Reset timer.
            * States.RECORDING: Reset timer.
            * States.FINISHING: Re-schedule the record after a delay.

        """

        self.ring_buffer.bind(
            self.pipeline,
            on_success=self._on_ringbuffer_bound,
            on_failure=self._on_ringbuffer_bind_fail,
            on_timeout=self._on_ringbuffer_bind_timeout,
            on_eos=self._on_ringbuffer_eos,
            timeout_sec=1,
        )

        self.recording_start_time: Optional[datetime] = None

    # region properties ################################################

    @property
    def state(self) -> States:
        """The recording state - one of :class:`States`."""
        return self._state

    # @traced(logger.trace, log_time=True)
    @state.setter
    def state(self, value):
        pre, self._state = self._state, value
        return f"PREVIOUS STATE: {repr(pre)}"
        # logger.info(f"RecorderState: {datetime.now()} - Changed state from {repr(pre)} to {repr(value)}")

    @property
    def deque(self) -> Optional[collections.deque]:
        """The ringbuffer container, backed by a :obj:`collections.deque`.

        The :class:`VideoRecorder` is the actual owner of the ringbuffer
        container, and not the :attr:`VideoRecorder.ring_buffer`, as one
        might think, because this allows for easier instantiation, given
        its size must be dynamically set once the caps have been
        negotiated.

        While in :obj:`States.RECORDING`, the
        :attr:`VideoRecorder.record_bin` pops buffers from here.

        See Also:
            The initialization, as performed at
            :meth:`_on_ringbuffer_bound`

        """
        return self._deque

    @deque.setter
    def deque(self, value: collections.deque):
        self._deque = value

    @property
    def stop_recording_timer(self) -> Optional[PostponedBackgroundThread]:
        """Timer to the stop recording event.

        Normally its value is :obj:`None`, except while in
        :obj:`States.RECORDING`, where it contains a background thread
        waiting for a timeout.

        If :meth:`record` is called before the timeout, the timer gets
        reset.

        Once the timeout is reached, the thread signals the
        `VideoRecorder` to stop recording.

        When the recording is done, it returns back to `None`.

        See Also:
            :meth:`reset_stop_recording_timer`

        """
        return self._stop_recording_timer

    @stop_recording_timer.setter
    def stop_recording_timer(self, value: PostponedBackgroundThread):
        if self._stop_recording_timer is not None:
            try:
                self._stop_recording_timer.cancel()
            except CancelNotInWaiting:
                pass
        self._stop_recording_timer = value

    @property
    def busy(self):
        """:obj:`True` unless in :obj:`States.BUFFERING` state.

        Example:

            This can be useful eg when you want to wait for a currently
            recording video to be finished:

                >>> while recorder.busy:
                ...     sleep(.1)
                >>> print("recording finished")

        """
        return self.state != States.BUFFERING

    # endregion properties #############################################

    # region record signals handling ###################################

    # @dotted
    # @traced(logger.info, log_time=True)
    def record_bg(
        self,
        on_video_finished: Optional[OnVideoFinished] = None,
    ) -> None:
        """Initiate recording process without blocking.

        Warning:
            Normal users should use :meth:`record` instead.

        This is used internally, and should only be called if you do not
        care about the delay or actual response of the pipeline. If you
        want to use this method anyway, you'll probably want to check
        for :attr:`RecordBin.filesink_location` manually.

        """
        state = self.state
        try:
            callback = self.on_record_dispatch[state]
        except KeyError as exc:
            raise NotImplementedError(f"Unhandled state {state}") from exc
        return callback(on_video_finished=on_video_finished)

    @traced(logger.info, log_time=False, log_post=False)
    def record(
        self,
        poll_msec: float = 0.001,
        max_delay_sec: float = 0.1,
        on_video_finished: Optional[OnVideoFinished] = None,
    ) -> str:
        """Record and block until video file exists.

        This is the main usage case for the recorder. When calling this
        method the :class:`VideoRecorder` does one of the following,
        depending on its :attr:`state`:


         starts creating a video
        containing past bufers attaches the recordbin and
        connect callbacks to start pushing buffers from the ringbuffer
        ASAP - effectively

        Loops and waits until the recordbin's filesink has a valid
        location, which means the record video is being created.

        Args:
            poll_msec: Time in milliseconds to wait between each check
                for the video file existence.
            max_delay_sec: Maximum time in milliseconds to wait for the
                video file to exist.

        Raises:
            TimoutError: if no file is available after the specified
                `max_delay_sec`.

        See Also:

            * :meth:`record_bg`
                For the backgorund record process.
            * :attr:`on_record_dispatch`
                For the available actions taken by the
                :class:`VideoRecorder`, depending on its :attr:`state`.

        """
        t0 = datetime.now()
        self.record_bg(on_video_finished=on_video_finished)
        while True:
            sleep(poll_msec / 1e3)
            if (datetime.now() - t0).total_seconds() > max_delay_sec:
                raise TimeoutError(f"record took longer than {max_delay_sec}")
            try:
                return self.record_bin.filesink_location
            except Exception as exc:
                logger.exception(exc)
                pass

    @traced(logger.warning)
    def _on_dettached_record(
        self,
        on_video_finished: Optional[OnVideoFinished] = None,
    ):
        """Re-schedule the record after a delay."""
        th = run_later(
            self.record, 1 / 100, on_video_finished=on_video_finished
        )
        th.join()
        return th._output

    @traced(logger.info, log_time=True)
    def _on_buffering_record(
        self,
        on_video_finished: Optional[OnVideoFinished] = None,
    ):
        """Reset timer and bind the recordbin."""
        self.recording_start_time = datetime.now()
        self.reset_stop_recording_timer()
        self.state = (self.state & ~States.BUFFERING) | States.STARTING
        self.record_bin.bind(
            self.pipeline,
            self.ring_buffer.ringbuffer_caps_str,
            self.framerate,
            self.deque,
            # self.ring_buffer.ringbuffer_appsink_pad,
            on_success=self._on_recordbin_bound,
            on_failure=self._on_recordbin_bind_fail,
            on_eos=self._on_recordbin_eos,
            on_unbind_failure=self._on_recordbin_unbind_failure,
            # on_timeout=self._on_recordbin_bind_timeout,
            # timeout_sec=1
        )
        self.on_video_finished = on_video_finished

    @traced(logger.warning)
    def _on_starting_record(
        self,
        on_video_finished: Optional[OnVideoFinished] = None,
    ):
        self.reset_stop_recording_timer()
        self.on_video_finished = on_video_finished

    def _on_recording_record(
        self,
        on_video_finished: Optional[Callable] = None,
    ):
        self.reset_stop_recording_timer()
        self.on_video_finished = on_video_finished

    @traced(logger.warning)
    def _on_finishing_record(
        self,
        on_video_finished: Optional[OnVideoFinished] = None,
    ):
        th = run_later(
            self.record, 1 / 100, on_video_finished=on_video_finished
        )
        th.join()
        return th._output

    def _on_recordbin_recording(self):
        self.state = States.RECORDING

    # endregion record signals handling ################################

    # region ringbuffer signals handling ###############################

    def _on_ringbuffer_bound(
        self,
        rinbugger_len: int,
        framerate,
    ):
        if self.state != States.DETTACHED:
            raise NotImplementedError
        maxlen = rinbugger_len  #  + 1  # TODO verify!
        self.deque = collections.deque(maxlen=maxlen)
        self.state = States.BUFFERING
        self.framerate = framerate
        return self.deque

    def _on_ringbuffer_bind_timeout(self):
        logger.error(f"Ringbuffer not bound - timed out. Exiting")
        exit_from_thread()

    def _on_ringbuffer_bind_fail(self, reason):
        logger.error(f"Unable to bind ringbuffer ({reason}). Exiting")
        exit_from_thread()

    # @traced(logger.trace)
    def _on_ringbuffer_eos(self, *a, **kw):
        send_event(self.pipeline, Gst.Event.new_eos())
        # import pdb;pdb.set_trace()
        # print("oli")

    # endregion ringbuffer signals handling ############################

    # region recordbin signals handling ################################

    @traced(logger.trace)
    def _on_recordbin_bound(self):
        self.state = (self.state & ~States.STARTING) | States.RECORDING
        if self.state != States.RECORDING:
            raise NotImplementedError(f"Unhandled state {self.state}")
        # self.reset_stop_recording_timer()

    # @traced(logger.warning)
    def _on_recordbin_bind_fail(self, reason):
        logger.error(f"Unable to bind recordbin ({reason}). Exiting")
        exit_from_thread()

    def _on_recordbin_bind_timeout(self):
        raise NotImplementedError

    @traced(logger.info, log_post=True)
    def _on_recordbin_eos(self, filesink_location: Optional[str]):
        state = self.state
        if state == States.RECORDING:  #  recordbin received eos internally
            self.state = state = States.FINISHING

        if state != States.FINISHING:  # eos after we called unbind
            raise NotImplementedError(
                f"Unhandled state {repr(self.state)} @ _on_recordbin_unbound"
            )

        self.state = States.BUFFERING

        if self.on_video_finished:
            run_later(self.on_video_finished, 0, filesink_location)

        return {
            "runtime_length_sec": (
                datetime.now() - self.recording_start_time
            ).total_seconds(),
            "filesink_location": filesink_location,
        }

    def _on_recordbin_unbind_failure(self):
        raise NotImplementedError

    # endregion recordbin signals handling ################################

    def reset_stop_recording_timer(self):
        """Cancel and reset :sttr:`stop_recording_timer`.

        Given that the ringbuffer at current time contains buffers from
        `now-`:attr:`RingBuffer.window_size_sec`, the new timeout is
        scheduled in two times the time window: once backwards (as
        incoming buffers are delayed by window_size), once into the
        future.

        """
        self.stop_recording_timer = run_later(
            self.__on_window_timeout,
            2 * self.ring_buffer.window_size_sec,  #
        )

    @traced(logger.trace)
    def __on_window_timeout(self):
        if self.state not in (States.BUFFERING | States.RECORDING):
            raise NotImplementedError(
                f"Unhandled state {repr(self.state)} on window timeout!"
            )

        self.stop_recording_timer = None
        if self.state == States.BUFFERING:
            logger.debug(
                f"Received windo timeout event in buffering state."
                f" An EOS has previously gone through the pipeline."
            )
            return

        self.state = States.FINISHING
        self.record_bin.send_eos()
