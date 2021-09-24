# region imports ###################################################################
import collections
import enum
import math
import os
import sys
from collections import deque
from datetime import datetime
from functools import partial
from functools import wraps
from threading import Thread
from time import sleep
from typing import Any
from typing import Callable
from typing import Optional
from uuid import uuid4

import gi

gi.require_version("GstApp", "1.0")
from gi.repository import GLib
from gi.repository import Gst
from gi.repository import GstApp

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

# PULL_COUNT, PUSH_COUNT = 0,0

# region globals-defaults ##############################################
DEFAULT_WINDOW_SIZE_SEC = 2
DEFAULT_TIMEOUT_SEC = 1
DEFAULT_VIDEO_EXT = ".webm"


# endregion globals-defaults ###########################################

# region old ###########################################################
# def default_filename_generator():
#     return f"{uuid4()}{DEFAULT_VIDEO_EXT}"


# class RingBufferMixin:
#     RINGBUFFER_BIN_STRING = f"""
#         queue
#           name=ringbuffer_input_queue
#         ! capsfilter
#           name=ringbuffer_input_capsfilter
#           caps=video/x-raw,format=I420
#         ! appsink
#           name=ringbuffer_appsink
#           emit-signals=true
#           async=false
#     """

#     pipeline: Gst.Pipeline
#     _on_new_sample: Callable
#     _appsink_eos: Callable

#     def __init__(self, window_size):
#         self.window_size = window_size
#         self.ringbuffer_bin: Optional[Gst.Bin] = None
#         self.ringbuffer_input_queue: Optional[Gst.Element] = None
#         self.ringbuffer_appsink: Optional[Gst.Element] = None
#         self.deque: Optional[collections.deque] = None
#         self.framerate: Optional[float] = None
#         self._inject_ringbuffer()

#     @property
#     def app_sink_pad(self) -> Gst.Pad:
#         return self.ringbuffer_appsink.get_static_pad("sink")


#     @property
#     def ringbuffer_caps(self) -> Gst.Caps:
#         caps_raw = self.app_sink_pad.get_current_caps()
#         return caps_raw

#     @property
#     def ringbuffer_caps_str(self) -> Gst.Caps:
#         caps_str = self.ringbuffer_caps.to_string().replace(", ", ",")
#         return caps_str

#     def _inject_ringbuffer(self):
#         self._attach_ringbuffer_to_pipeline()
#         self._link_ringbuffer()

#     def _attach_ringbuffer_to_pipeline(self):
#         self.ringbuffer_bin = Gst.parse_bin_from_description(
#             self.RINGBUFFER_BIN_STRING,
#             True,
#         )
#         self.ringbuffer_bin.set_name("ringbuffer_bin")

#         gst_add(self.pipeline, self.ringbuffer_bin)
#         self.ringbuffer_input_queue = get_by_name(
#             self.ringbuffer_bin, "ringbuffer_input_queue"
#         )

#         self.ringbuffer_appsink = get_by_name(
#             self.ringbuffer_bin, "ringbuffer_appsink"
#         )
#         self.ringbuffer_appsink.connect("new-sample", self._on_new_sample)
#         self.ringbuffer_appsink.get_static_pad("sink").add_probe(
#             Gst.PadProbeType.EVENT_BOTH,
#             self._appsink_eos,
#         )

#         return self.ringbuffer_bin

#     def _link_ringbuffer(self):
#         set_state(self.ringbuffer_bin, Gst.State.PLAYING)

#         link_elements(self.src_tee, self.ringbuffer_bin)
#         sync_state_with_parent(self.ringbuffer_bin)
#         sync_children_states(self.ringbuffer_bin)

#         set_state(self.pipeline, Gst.State.PLAYING)

#         return Gst.PadProbeReturn.REMOVE


# class RecordBinMixin:

#     RECORD_BIN_STRING = f"""
#         appsrc
#           name=appsrc
#           emit-signals=true
#           is-live=true
#           do-timestamp=true
#           stream-type=0
#           format=time
#           caps={{caps}}
#           block=false
#         ! vp8enc
#           deadline=1
#           name=encoder
#         ! webmmux
#           name=muxer
#         ! filesink
#           location={{sink_location}}
#           name=filesink
#     """

#     def __init__(self, sink_location_prefix, timeout_sec):
#         self.record_bin: Optional[Gst.Bin] = None
#         self.appsrc: Optional[Gst.Element] = None
#         self.appsrc_worker: Optional[Thread] = None
#         self.sink_location_prefix: str = sink_location_prefix
#         self.timeout_sec: int = timeout_sec

#         self.sink_location: Optional[str] = None

#     @property
#     def current_video_location(self):
#         return self.filesink.get_property("location")

#     @property
#     def filesink(self):
#         return get_by_name(self.record_bin, "filesink")

#     @property
#     def encoder(self):
#         return get_by_name(self.record_bin, "encoder")


# class VideoRecorder1(
#     RingBufferMixin,
#     RecordBinMixin,
# ):

#     class States(enum.IntFlag):
#         IDLE = 0
#         STARTING = 1
#         RECORDING = 2
#         PUSHING_BUFFERS = 4
#         FINISHING = 8

#     def __init__(
#         self,
#         pipeline: Gst.Pipeline,
#         src_tee_name: str,
#         sink_location_prefix: str,
#         window_size: int = DEFAULT_WINDOW_SIZE_SEC,
#         timeout_sec: int = DEFAULT_TIMEOUT_SEC,
#         on_video_finished: Optional[Callable[[str], Any]] = None,
#         filename_generator: Callable[[], str] = default_filename_generator,
#     ):

#         # pipeline elements
#         self.pipeline = pipeline
#         self.src_tee_name = src_tee_name
#         self.src_tee = get_by_name(self.pipeline, self.src_tee_name)
#         self.filename_generator = filename_generator

#         # recording state handling
#         self.state = self.States.IDLE
#         self._pending_cancel = None

#         RingBufferMixin.__init__(self, window_size)
#         RecordBinMixin.__init__(self, sink_location_prefix, timeout_sec)

#         self.on_video_finished = None


#     def _on_idle_record(self):
#         logger.info(f"Preparing to record")
#         self.sink_location = (
#             f"{self.sink_location_prefix}{self.filename_generator()}"
#         )
#         logger.debug(f"Writing to '{self.sink_location}'")
#         run_later(self._emit_buffers_bg, 0)
#         add_probe(
#             self.app_sink_pad,
#             Gst.PadProbeType.BUFFER,
#             self._connect_bin,
#         )

#         self._reset_stop_recording_timeout()
#         return self.sink_location

#     def _on_recording_record(self):
#         logger.info(f"Recording already recording...")
#         self._reset_stop_recording_timeout()
#         return self.sink_location

#     def _on_starting_record(self):
#         logger.info(f"Recording already starting - rescheduling...")
#         r = run_later(self.record, 1)
#         r.join()
#         return r._output

#     def _on_finishing_record(self):
#         logger.info(
#             f"Recording finising previous state - re-scheduling record event"
#         )
#         r = run_later(self.record, 1e-3)
#         r.join()
#         return r._output

#     @property
#     def current_video_location(self):
#         raise NotImplementedError

#     @traced(logger.info, log_time=True, log_post=False)
#     def record(
#         self,
#     ):

#         # state_change_return, current, pending = self.pipeline.get_state(1000)
#         # logger.debug(
#         #     f"self.pipeline.get_state(1000): {(state_change_return, current, pending)}"
#         # )
#         self._cancel_pending()

#         if self.state == self.States.IDLE:
#             return self._on_idle_record()
#             # self.state = self.States.STARTING
#             return self.sink_location

#         if self.state == self.States.STARTING:
#             return self._on_starting_record()

#         if self.state & self.States.RECORDING:
#             return self._on_recording_record()


#         if self.state == self.States.FINISHING:
#             return self._on_finishing_record()

#         raise NotImplementedError(f"Unhandled state: {self.state}")

#     def _cancel_pending(self, raise_if_no_pending=False):
#         # avoid race condition when two threads call same code

#         try:
#             state = self._pending_cancel.state
#         except AttributeError:
#             if self._pending_cancel is None:
#                 if raise_if_no_pending:
#                     raise AttributeError(
#                         f"cancel_pending called without pending"
#                     )
#                 return
#             raise AttributeError(
#                 f"Unhandled self._pending_cancel={self._pending_cancel}"
#             )

#         if self._pending_cancel.States.WAITING in state:
#             self._pending_cancel.cancel()
#             return

#         raise NotImplementedError(
#             f"Unhandled pending cancel={self._pending_cancel}"
#         )

#     def _on_new_sample(self, *a) -> Gst.FlowReturn:
#         sample = self.ringbuffer_appsink.emit("pull-sample")
#         if sample is None:
#             logger.warning(f"{self.ringbuffer_appsink} pulled empty sample")
#             return Gst.FlowReturn.ERROR

#         buffer: Gst.Buffer = sample.get_buffer()
#         try:
#             self.deque.append(buffer)
#         except AttributeError:
#             if self.deque is not None:
#                 raise
#             self._initialize_dequeue()
#             logger.info(
#                 f"Ringbuffer queue initialized, size={self.deque.maxlen}"
#             )
#             logger.info(
#                 f"Recorder.on_new_sample: FIRST buffer @ {datetime.now()} - pts={buffer.pts}"
#             )
#             self.first_pull_buf = datetime.now()
#             self.deque.append(buffer)
#         else:
#             logger.debug(
#                 f"Recorder.on_new_sample: INPUT buffer @ {datetime.now()} - pts={buffer.pts}"
#             )

#         return Gst.FlowReturn.OK

#     @toggles_state(States.PUSHING_BUFFERS)
#     def _emit_buffers_bg(self):
#         delay = 1 / self.framerate

#         while self.state & self.States.RECORDING:
#             try:
#                 gstbuf = self.deque.popleft()
#                 appsrc_emit(self.appsrc, "push-buffer", gstbuf)
#                 sleep(delay)
#             except AttributeError as exc:
#                 if self.deque is not None:
#                     raise
#                 sleep(delay / 10)
#             except IndexError:
#                 sleep(delay / 10)
#             except Exception as exc:
#                 logger.error(f"emit buffers: {exc}")
#                 raise

#     def _appsink_eos(
#         self,
#         pad: Gst.Pad,
#         info: Gst.PadProbeInfo,
#     ):
#         event_type = info.get_event().type
#         if event_type == Gst.EventType.EOS:
#             logger.info(
#                 "_appsink_eos: received EOS - removing ringbuffer_bin bin"
#             )
#             removed = self.pipeline.remove(self.ringbuffer_bin)
#             # Can't set the state of the src to NULL from its streaming thread
#             # GLib.idle_add(self._release_bin)  # TODO ESTA WEAS ES PELIGROSA - REVISAR MEMLEAK
#             run_later(
#                 self._release_ringbuffer_bin, delay=0, on_success=self.destroy
#             )
#             # record_bin.unref() TODO: use this if there are memleaks
#             if not removed:
#                 logger.error("BIN remove FAILED")
#                 sys.exit(42)
#             return Gst.PadProbeReturn.DROP
#         return Gst.PadProbeReturn.OK

#     @traced(logger.debug)
#     def destroy(self, *a):
#         return send_event(self.pipeline, Gst.Event.new_eos())

#     def _release_ringbuffer_bin(self):
#         state = set_state(self.ringbuffer_bin, Gst.State.NULL)
#         # self.ringbuffer_bin.unref()  # TODO: check why we get gobject warnings... are they important?
#         self.ringbuffer_bin = None
#         return state

#     def _release_ringbuffer_bin2(self):
#         gst_remove(self.pipeline, self.ringbuffer_bin)
#         self.ringbuffer_bin.set_state(Gst.State.NULL)
#         # self.ringbuffer_bin.unref()  # TODO: check why we get gobject warnings... are they important?
#         self.ringbuffer_bin = None
#         return "RELEASED"

#     def _initialize_dequeue(self):
#         appsink_pad = self.ringbuffer_appsink.get_static_pad("sink")
#         caps = appsink_pad.get_current_caps()
#         struct = caps.get_structure(0)
#         success, *framerate = struct.get_fraction("framerate")
#         self.framerate = float(framerate[0] / framerate[1])
#         maxlen = math.ceil(self.window_size * self.framerate) + 1
#         self.deque = collections.deque(maxlen=maxlen)


#     def _connect_bin(self, pad, info):
#         # pipe_to_png(self.pipeline, "pre_record_bin")

#         # name=self.sink_location
#         # caps=self.ringbuffer_caps

#         caps_str = self.ringbuffer_caps_str
#         logger.debug(f"caps_str: `{caps_str}`")
#         logger.debug(
#             f"PIPELINE STATE: (state_change_return, current, pending)={self.pipeline.get_state(Gst.CLOCK_TIME_NONE)}"
#         )
#         try:
#             self._create_record_bin(self.sink_location, caps_str)
#         except GLib.Error as exc:
#             logger.error(
#                 f"Could not add record_bin to pipeline - reason: {type(exc)}({exc})"
#             )
#             sys.exit(42)
#             return Gst.PadProbeReturn.REMOVE

#         add = self.pipeline.add(self.record_bin)
#         if not add:
#             logger.error("Could not add record_bin to pipeline")
#             sys.exit(42)

#         try:
#             synced = self.record_bin.sync_state_with_parent()
#             if not synced:
#                 logger.error("Could not sync record_bin with pipeline")
#                 sys.exit(42)
#             logger.debug(f"SYNC RESULT: {synced}")
#             logger.debug(
#                 f"PIPELINE STATE CON TIMEOUT POST PARENT: (state_change_return, current, pending)={self.pipeline.get_state(1000)}"
#             )
#             logger.debug("Successfully syncd record_bin state to pipeline's")

#             if not self.record_bin.sync_children_states():
#                 logger.error("Could not sync record_bin with children")
#                 sys.exit(42)
#             logger.debug(
#                 "Successfully synced record_bin's state to its childrens'"
#             )
#             logger.debug(
#                 f"PIPELINE STATE CON TIMEOUT POST CHILDREN: (state_change_return, current, pending)={self.pipeline.get_state(1000)}"
#             )

#             self.appsrc = get_by_name(self.record_bin, "appsrc")

#             self.state = self.States.RECORDING
#             logger.debug(f"PIPELINE STATE after change{self.state}")

#             logger.debug(f"Attempting state change to play")
#             play_state = self.pipeline.set_state(Gst.State.PLAYING)
#             run_later(self._emit_buffers_bg, 0)
#             logger.debug(f"Play state result: {play_state}")

#             return Gst.PadProbeReturn.REMOVE
#         except BaseException as exc:
#             logger.exception(exc)
#             raise
#         finally:
#             return Gst.PadProbeReturn.REMOVE

#     @traced(logger.debug, log_time=True)
#     def _reset_stop_recording_timeout(self):
#         if self._pending_cancel is not None:
#             self._pending_cancel.cancel()
#             self._pending_cancel = None
#         self._pending_cancel = run_later(
#             self._stop_recording,
#             2
#             * self.window_size,  # once backwards (as incoming buffers are delayd by window_size), once into the future.
#             on_success=lambda _: setattr(self, "_pending_cancel", None),
#         )

#     @traced(logger.info, log_time=True, log_pre=False)
#     def _stop_recording(self):
#         if not self.record_bin:
#             logger.debug(
#                 f"Record bin already removed - skipping stop recording"
#             )
#             return
#         print("", flush=True)
#         self.state = self.States.FINISHING
#         appsink_src = get_static_pad(self.ringbuffer_appsink, "sink")
#         add_probe(
#             appsink_src,
#             Gst.PadProbeType.BLOCK,
#             self._disconnect_record_bin,
#         )

#     def _disconnect_ringbuffer_bin(self):
#         if not self.ringbuffer_bin:
#             msg = "ringbuffer_bin bin already unset!"
#             logger.warning(msg)
#             return msg

#         state = self.ringbuffer_bin.get_state(3)

#         sync_children_states(self.ringbuffer_bin)

#         capsfilter = self.ringbuffer_bin.get_by_name(
#             "ringbuffer_input_capsfilter"
#         )
#         state = capsfilter.set_state(Gst.State.NULL)

#         state = set_state(self.ringbuffer_bin, Gst.State.NULL)

#         logger.debug("SCHEDULING ringbuffer_bin REMOVAL")
#         remove = self.pipeline.remove(self.ringbuffer_bin)
#         self.ringbuffer_bin = None
#         return remove

#     def _disconnect_record_bin(self, pad, info):
#         record_bin = self.record_bin

#         if not record_bin:
#             logger.debug(
#                 "Record bin already unset! Removing blocking pad on tee..."
#             )
#             return Gst.PadProbeReturn.REMOVE

#         logger.debug(
#             "SCHEDULING RECORD BIN REMOVAL, then removing blocking pad on tee..."
#         )
#         record_bin.send_event(Gst.Event.new_eos())
#         return Gst.PadProbeReturn.REMOVE

#     def _wait_for_bin(self, exist, niter=10):

#         prefix = "No record bin" if exist else "Record bin still present"
#         msg = f"{prefix} after {(self.timeout_sec)}[s]"
#         for _ in range(niter):
#             print(f"self.record_bin: {self.record_bin}\n", flush=True)
#             if (exist and bool(self.record_bin)) or (
#                 (not exist) and (not self.record_bin)
#             ):
#                 break
#             sleep(self.timeout_sec / niter)
#         else:
#             raise TimeoutError(msg)
#         return self.record_bin

#     def _create_record_bin(self, name, caps):
#         bin_str = self.RECORD_BIN_STRING.format(
#             sink_location=name,
#             element_name=name,
#             caps=caps,
#         )

#         logger.debug(f"BIN STRING: ```{bin_str}```")
#         self.record_bin = Gst.parse_bin_from_description(
#             bin_str,
#             True,
#         )

#         add_probe(
#             self.filesink.get_static_pad("sink"),
#             Gst.PadProbeType.EVENT_BOTH,
#             self._check_eos,
#         )

#         # add_probe(
#         #     self.encoder.get_static_pad("sink"),
#         #     Gst.PadProbeType.BUFFER,
#         #     self._append_deepstream_frame_num,
#         # )

#         return self.record_bin

#     def _check_eos(
#         self,
#         pad: Gst.Pad,
#         info: Gst.PadProbeInfo,
#     ):
#         event_type = info.get_event().type
#         if event_type == Gst.EventType.EOS:
#             logger.debug(
#                 "recordbin.filesink: received EOS - removing record_bin"
#             )
#             removed = self.pipeline.remove(self.record_bin)
#             # Can't set the state of the src to NULL from its streaming thread
#             # GLib.idle_add(self._release_bin)  # TODO ESTA WEAS ES PELIGROSA - REVISAR MEMLEAK
#             run_later(self._release_bin, 0)
#             if self.on_video_finished:
#                 self.on_video_finished(self.current_video_location)
#             # record_bin.unref() TODO: use this if there are memleaks
#             if not removed:
#                 logger.error("BIN remove FAILED")
#                 sys.exit(42)
#             return Gst.PadProbeReturn.DROP
#         return Gst.PadProbeReturn.OK

#     def _append_deepstream_frame_num(self, pad, info):
#         try:
#             for frame_metadata in frames_per_batch(info):
#                 frame_num = frame_metadata.frame_num
#             self._inject_framenum_as_tag(frame_num)
#         except Exception as exc:
#             logger.exception(f"ERROR! {exc}")
#         finally:
#             return Gst.PadProbeReturn.OK

#     def _inject_framenum_as_tag(
#         self, frame_num
#     ):  # TODO find out how to inject tags to each frame instead
#         # if frame_num == self.last_frame_number +1: TODO uncomment this to only write non-sequential frame_num (useful on when frame dropping)
#         #     return
#         try:
#             result, data = self.muxer.get_tag_list().get_string(
#                 Gst.TAG_COMMENT
#             )
#         except:
#             result, data = False, "ds frame_num sequence:\t\t"

#         data += str(frame_num) + "\t"
#         value = data
#         taglist = Gst.TagList.new_empty()
#         taglist.add_value(Gst.TagMergeMode.APPEND, Gst.TAG_COMMENT, value)
#         self.muxer.merge_tags(taglist, Gst.TagMergeMode.REPLACE_ALL)
#         self.muxer.get_tag_list().to_string()

#     def _release_bin(self):
#         self.record_bin.set_state(Gst.State.NULL)
#         # self.record_bin.unref()  # TODO: check why we get gobject warnings... are they important?
#         self.state = self.States.IDLE
#         self.record_bin = None
#         return self.state

# endregion old ########################################################

# region nu ###################################################################

# BufferProbeAttacher = Tuple[str, str, Callback[[Any, Gst.Pad, Gst.PadProbeInfo, Any, dict]]]


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
    def _on_dettached_record(self, *a, **kw):
        th = run_later(self.record, 1 / 100, *a, **kw)
        th.join()
        return th._output

    # @traced(logger.info)
    def _on_buffering_record(
        self,
        on_video_finished: Optional[Callable] = None,
    ):
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
    def _on_starting_record(self, *a, **kw):
        self.reset_stop_recording_timer()

    def _on_recording_record(self):
        self.reset_stop_recording_timer()

    @traced(logger.warning)
    def _on_finishing_record(self, *a, **kw):
        th = run_later(self.record, 1 / 100, *a, **kw)
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

    @traced(logger.info, log_post=False)
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


# endregion nu ###################################################################
