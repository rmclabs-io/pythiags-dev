# region imports ##############################################################
import collections
import enum
from datetime import datetime
from time import sleep
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional

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
    DETTACHED = 0
    BUFFERING = 1
    STARTING = 2
    RECORDING = 4
    FINISHING = 8


OnRecord = Callable[[Any], str]


class VideoRecorder:

    """

    Signals:
        - record (method): external trigger to start recording
        - flowing (callback): internal message when recordbin is pushing
        - timeout (timeout): internal message when timewindow has passed
        - cleanup_done (callback): internal message when timewindow has passed
    """

    def __init__(
        self,
        pipeline: Gst.Pipeline,
        src_tee_name: str,
        filename_generator: Callable,
        timeout_sec: float,
        window_size_sec: float,
    ):
        self.pipeline = pipeline

        self._state = States.DETTACHED
        self._deque: Optional[collections.deque] = None
        self._stop_recording_timer: Optional[PostponedBackgroundThread] = None
        self.ring_buffer = RingBuffer(
            src_tee_name,
            window_size_sec,
        )
        self.record_bin = RecordBin(
            filename_generator,
            timeout_sec,
        )

        self.on_record_dispatch: Dict[State, OnRecord] = {
            States.DETTACHED: self._on_dettached_record,
            States.BUFFERING: self._on_buffering_record,
            States.STARTING: self._on_starting_record,
            States.RECORDING: self._on_recording_record,
            States.FINISHING: self._on_finishing_record,
        }

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
    def state(self):
        return self._state

    # @traced(logger.trace, log_time=True)
    @state.setter
    def state(self, value):
        pre, self._state = self._state, value
        return f"PREVIOUS STATE: {repr(pre)}"
        # logger.info(f"RecorderState: {datetime.now()} - Changed state from {repr(pre)} to {repr(value)}")

    @property
    def deque(self):
        return self._deque

    @deque.setter
    def deque(self, value):
        self._deque = value

    @property
    def stop_recording_timer(self) -> PostponedBackgroundThread:
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
        return self.state != States.BUFFERING

    # endregion properties #############################################

    # region record signals handling ###################################

    # @dotted
    # @traced(logger.info, log_time=True)
    def record_bg(self, *args, **kwargs) -> str:
        """Initiate recording process.

        .. seealso: record

        """
        state = self.state
        try:
            callback = self.on_record_dispatch[state]
        except KeyError as exc:
            raise NotImplementedError(f"Unhandled state {state}") from exc
        return callback(*args, **kwargs)

    @traced(logger.info, log_time=False, log_post=False)
    def record(
        self,
        *args,
        poll_msec=0.001,
        max_delay_sec=0.1,
        **kwargs,
    ) -> str:
        """Initiate and await recording process.

        .. seealso: record_bg

        """
        t0 = datetime.now()
        self.record_bg(*args, **kwargs)
        while True:
            sleep(poll_msec / 1e3)
            if (t0 - datetime.now()).total_seconds() > max_delay_sec:
                raise TimeoutError(f"record took longer than {max_delay_sec}")
            try:
                return self.record_bin.filesink_location
            except Exception as exc:
                logger.exception(exc)
                pass

        state = self.state
        try:
            callback = self.on_record_dispatch[state]
        except KeyError as exc:
            raise NotImplementedError(f"Unhandled state {state}") from exc
        return callback(*args, **kwargs)

    @traced(logger.warning)
    def _on_dettached_record(
        self,
        on_video_finished: Optional[Callable] = None,
    ):
        th = run_later(
            self.record, 1 / 100, on_video_finished=on_video_finished
        )
        th.join()
        return th._output

    @traced(logger.info, log_time=True)
    def _on_buffering_record(
        self,
        on_video_finished: Optional[Callable] = None,
    ):
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
        on_video_finished: Optional[Callable] = None,
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
        on_video_finished: Optional[Callable] = None,
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
        self.stop_recording_timer = run_later(
            self.__on_window_timeout,
            2
            * self.ring_buffer.window_size_sec,  # once backwards (as incoming buffers are delayd by window_size), once into the future.
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
