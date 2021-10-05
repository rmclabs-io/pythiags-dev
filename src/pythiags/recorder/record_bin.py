# region imports ###################################################################
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Callable

from pythiags import Gst
from pythiags import logger
from pythiags.background import run_later
from pythiags.utils import add_probe
from pythiags.utils import appsrc_emit
from pythiags.utils import get_by_name
from pythiags.utils import gst_add
from pythiags.utils import gst_remove
from pythiags.utils import parse_bin
from pythiags.utils import send_event
from pythiags.utils import sync_state_with_parent
from pythiags.utils import traced

# endregion imports ####################################################


class RecordBin:

    RECORD_BIN_STRING = f"""
        appsrc
          name=appsrc
          emit-signals=true
          is-live=true
          do-timestamp=true
          stream-type=0
          format=time
          caps={{caps}}
          block=false
        ! vp8enc
          deadline=1
          name=encoder
        ! webmmux
          name=muxer
        ! filesink
          location={{sink_location}}
          name=filesink
    """

    def __init__(
        self,
        filename_generator: Callable,
        timeout_sec: float,
    ):
        self.filename_generator = filename_generator
        self.timeout_sec = timeout_sec

        self.pipeline = None
        self.pushing_buffers = False

        self.on_unbind_success = None
        self.on_unbind_failure = None

    @property
    def filesink(self):
        return get_by_name(self.record_bin, "filesink")

    @property
    def filesink_sinkpad(self):
        return self.filesink.get_static_pad("sink")

    @property
    def filesink_location(self):
        return self.filesink.get_property("location")

    @property
    def appsrc(self):
        return get_by_name(self.record_bin, "appsrc")

    # @traced(logger.trace, log_time=True)
    def bind(
        self,
        pipeline,
        caps_str,
        framerate,
        deque,
        # pad,
        on_success: Callable,
        on_failure,
        # on_timeout,
        on_eos,
        # timeout_sec,
        on_unbind_failure,
    ):
        if self.pipeline:
            raise ValueError("Already bound!")
        self.pipeline = pipeline
        self.on_bind_sucess = on_success
        self.on_bind_failure = on_failure
        self.framerate = framerate
        self.deque = deque

        self.on_eos = on_eos
        self.on_unbind_failure = on_unbind_failure

        # self.on_bind_timeout = on_timeout
        # self.bind_timeout_sec = timeout_sec
        # # TODO use timeout callback to stop

        try:
            self.__attach(caps_str)
            self.__link()
            self.__connect_callbacks()
        except Exception as exc:
            logger.exception(exc)
            on_failure(repr(exc))

    def __attach(self, caps_str):

        sink_location = self.filename_generator()
        stem = Path(sink_location).stem
        # TODO: Check performance issues
        # if this is too slow, we could build the bin ahead of time,
        #         without adding it to the pipeline. Then, just override: caps,
        #         name, filesink's location properties instead
        # <pwoolvett 2021-10-05T16:16:36Z>
        self.record_bin = parse_bin(
            self.RECORD_BIN_STRING.format(
                sink_location=sink_location,
                caps=caps_str,
            ),
            True,
        )
        self.record_bin.set_name(f"recordbin_for_{stem}")
        gst_add(self.pipeline, self.record_bin)
        return self.record_bin

    def __link(self):

        sync_state_with_parent(self.record_bin)
        # sync_children_states(self.record_bin)

        # sync_state_with_parent(self.ringbuffer_bin)
        # set_state(self.pipeline, Gst.State.PLAYING)

    def __connect_callbacks(self):
        run_later(self.__emit_buffers_bg, 0)
        add_probe(
            self.filesink_sinkpad,
            Gst.PadProbeType.BUFFER,
            self.__on_first_frame_out,
        )

        add_probe(
            self.filesink_sinkpad,
            Gst.PadProbeType.EVENT_BOTH,
            self.__check_eos,
        )

    def __on_first_frame_out(
        self,
        pad: Gst.Pad,
        info: Gst.PadProbeInfo,
    ):
        try:
            self.on_bind_sucess()
        finally:
            return Gst.PadProbeReturn.REMOVE

    def __check_eos(
        self,
        pad: Gst.Pad,
        info: Gst.PadProbeInfo,
    ):  # FIXME: cant we use message::eos
        event_type = info.get_event().type
        if event_type == Gst.EventType.EOS:
            logger.debug(f"RecordBin: eos detected @ {datetime.now()}")
            try:
                location = self.filesink_location
            except AttributeError:
                location = None
            self.pushing_buffers = False
            try:
                logger.debug(
                    "recordbin.filesink: received EOS - removing record_bin"
                )
                gst_remove(self.pipeline, self.record_bin)
                # Can't set the state of the src to NULL from its streaming thread
                # GLib.idle_add(self._release_bin)  # TODO ESTA WEAS ES PELIGROSA - REVISAR MEMLEAK
                run_later(self.cleanup, 0)
                # record_bin.unref() TODO: use this if there are memleaks
            except Exception as exc:
                self.on_unbind_failure(repr(exc))
            else:
                run_later(self.on_eos, 0, location)
            finally:
                return Gst.PadProbeReturn.DROP
        return Gst.PadProbeReturn.OK

    def cleanup(self):
        self.record_bin.set_state(Gst.State.NULL)
        # self.record_bin.unref()  # TODO: check why we get gobject warnings... are they important?
        self.record_bin = None
        self.pipeline = None

    # @traced(logger.info, log_time=True)
    # def unbind(self,):
    #     if not self.pipeline:
    #         raise ValueError("Already unbound!")
    #     # self.pushing_buffers = False
    #     # self.recording = False

    #     self.send_eos()
    # self.__disconnect_callbacks()

    # def __disconnect_callbacks(self):
    # self.pushing_buffers = False
    # self.send_eos()
    # add_probe(
    #     self.appsrc.get_static_pad("src"),
    #     Gst.PadProbeType.BLOCK,
    #     self.send_eos,
    # )

    # @traced(logger.info, log_time=True)
    def send_eos(self, *a, **kw):
        try:
            send_event(self.record_bin, Gst.Event.new_eos())
        except Exception as exc:
            self.on_unbind_failure(repr(exc))
        finally:
            return Gst.PadProbeReturn.REMOVE

    # PULL_COUNT = 0
    @traced(logger.trace, log_time=True)
    def __emit_single(self, delay):
        try:
            gstbuf = self.deque.popleft()
            # self.PULL_COUNT +=1
            # logger.info(f"POP ({self.PULL_COUNT}): {datetime.now().isoformat()}: {gstbuf.pts}")
            appsrc_emit(self.appsrc, "push-buffer", gstbuf)
        except AttributeError as exc:
            if self.deque is not None:
                raise
            logger.debug("deque unset")
            sleep(delay / 1000)
        except IndexError:
            logger.debug("empty deque")
            sleep(delay / 1000)
        except Exception as exc:
            logger.error(f"emit buffers: {exc}")
            raise
        else:
            duration = gstbuf.duration
            if duration != Gst.CLOCK_TIME_NONE:
                delay = duration / 1e9
        return delay

    def __emit_buffers_bg(self):
        # self.pushing_buffers = True
        seconds_per_frame = 1 / self.framerate
        # global PULL_COUNT

        # # NOTE: this ensures the deque (left) pop starts in sync with
        # # the first change after this method has benn called.
        # nxt = self.deque[0]
        # while self.deque[0] == nxt:
        #     sleep(seconds_per_frame/1000)
        #     self.pushing_buffers = True
        self.pushing_buffers = True

        while True:
            duration = self.__emit_single(delay=seconds_per_frame)
            # print(f"Duration: {duration}\n", flush=True)
            sleep(duration)
            if not self.pushing_buffers:
                break
