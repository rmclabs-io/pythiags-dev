# region imports ###################################################################
import collections
import math
import sys
from typing import Any
from typing import Callable
from typing import Optional

from pythiags import Gst
from pythiags import logger
from pythiags.background import run_later
from pythiags.utils import get_by_name
from pythiags.utils import gst_add
from pythiags.utils import link_elements
from pythiags.utils import send_event
from pythiags.utils import set_state
from pythiags.utils import sync_children_states
from pythiags.utils import sync_state_with_parent

# endregion imports ####################################################


class RingBuffer:

    RINGBUFFER_BIN_STRING = """
        queue
          name=ringbuffer_input_queue
        ! capsfilter
          name=ringbuffer_input_capsfilter
          caps=video/x-raw,format=I420
        ! appsink
          name=ringbuffer_appsink
          emit-signals=true
          async=false
    """

    def __init__(
        self,
        src_tee_name: str,
        window_size_sec: float,
    ):
        self.src_tee_name = src_tee_name
        self.window_size_sec = window_size_sec

        self.pipeline: Optional[Gst.Pipeline] = None
        self.deque: Optional[collections.deque] = None

        self.on_bind_sucess: Optional[Callable] = None
        self.on_bind_failure: Optional[Callable] = None
        self.bind_timeout_sec: Optional[float] = None

    @property
    def ringbuffer_input_queue(self):
        return get_by_name(self.ringbuffer_bin, "ringbuffer_input_queue")

    @property
    def src_tee(self):
        return get_by_name(self.pipeline, self.src_tee_name)

    @property
    def ringbuffer_appsink(self):
        return get_by_name(self.ringbuffer_bin, "ringbuffer_appsink")

    @property
    def ringbuffer_appsink_pad(self):
        return self.ringbuffer_appsink.get_static_pad("sink")

    @property
    def ringbuffer_caps(self) -> Gst.Caps:
        caps_raw = self.ringbuffer_appsink_pad.get_current_caps()
        return caps_raw

    @property
    def ringbuffer_caps_str(self) -> Gst.Caps:
        caps_str = self.ringbuffer_caps.to_string().replace(", ", ",")
        return caps_str

    def bind(
        self,
        pipeline,
        on_success: Callable[[int], collections.deque],
        on_failure: Callable[[str], Any],
        on_timeout,
        on_eos,
        timeout_sec,
    ):
        if self.pipeline:
            raise ValueError("Already bound!")
        self.pipeline = pipeline
        self.on_bind_sucess = on_success
        self.on_bind_failure = on_failure
        self.on_bind_timeout = on_timeout
        self.bind_timeout_sec = timeout_sec
        self.on_eos = on_eos
        # TODO use timeout callback to stop

        try:
            self.__attach()
            self.__link()
            self.__connect_callbacks()
        except Exception as exc:
            logger.exception(exc)
            on_failure(repr(exc))

    def __attach(self):
        self.ringbuffer_bin = Gst.parse_bin_from_description(
            self.RINGBUFFER_BIN_STRING,
            True,
        )
        self.ringbuffer_bin.set_name(f"ringbuffer_bin_for_{self.src_tee_name}")

        gst_add(self.pipeline, self.ringbuffer_bin)

        return self.ringbuffer_bin

    def __link(self):
        # set_state(self.ringbuffer_bin, Gst.State.PLAYING)

        link_elements(self.src_tee, self.ringbuffer_bin)

        sync_state_with_parent(self.ringbuffer_bin)
        sync_children_states(self.ringbuffer_bin)

        # set_state(self.pipeline, Gst.State.PLAYING)

    def __connect_callbacks(self):
        self.ringbuffer_appsink_pad.add_probe(
            Gst.PadProbeType.BUFFER,
            self.__initialize_deque,
        )

        self.ringbuffer_appsink_pad.add_probe(
            Gst.PadProbeType.EVENT_BOTH,
            self.__appsink_eos_probe,
        )

        return self.ringbuffer_bin

    # @traced(logger.trace)
    def __initialize_deque(
        self,
        pad: Gst.Pad,
        info: Gst.PadProbeInfo,
    ):

        try:
            caps = self.ringbuffer_appsink_pad.get_current_caps()
            struct = caps.get_structure(0)
            success, *framerate = struct.get_fraction("framerate")
            if not success:
                raise RuntimeError(
                    "Unable to read `framerate` fraction from the ringbuffer appsink pad's caps"
                )
            framerate = float(framerate[0] / framerate[1])
            rinbugger_len = math.ceil(self.window_size_sec * framerate)
            logger.debug(f"rinbugger_len={rinbugger_len}")
            self.deque = self.on_bind_sucess(
                rinbugger_len,
                framerate,
            )

            self.ringbuffer_appsink.connect("new-sample", self.__on_new_sample)

        except Exception as exc:
            self.on_bind_failure(
                f"Unable to get framerate in order to initialize ringbuffer - {exc}"
            )
        finally:
            return Gst.PadProbeReturn.REMOVE

    def __appsink_eos_probe(
        self,
        pad: Gst.Pad,
        info: Gst.PadProbeInfo,
    ):  # FIXME can we just do this using mesage::eos??
        event_type = info.get_event().type
        if event_type == Gst.EventType.EOS:
            logger.info(
                "_appsink_eos: received EOS - removing ringbuffer_bin bin"
            )
            removed = self.pipeline.remove(self.ringbuffer_bin)
            # Can't set the state of the src to NULL from its streaming thread
            # GLib.idle_add(self._release_bin)  # TODO ESTA WEAS ES PELIGROSA - REVISAR MEMLEAK
            run_later(
                self.__release_ringbuffer_bin,
                delay=0,
                on_success=self.on_eos,
                on_failure=logger.error,
            )
            send_event(self.pipeline, Gst.Event.new_eos())
            # record_bin.unref() TODO: use this if there are memleaks
            if not removed:
                logger.error("BIN remove FAILED")
                sys.exit(42)
            return Gst.PadProbeReturn.DROP
        return Gst.PadProbeReturn.OK

    def __release_ringbuffer_bin(self):
        state = set_state(self.ringbuffer_bin, Gst.State.NULL)
        # self.ringbuffer_bin.unref()  # TODO: check why we get gobject warnings... are they important?
        self.ringbuffer_bin = None
        return state

    # PUSH_COUNT=0
    def __on_new_sample(self, *a) -> Gst.FlowReturn:
        sample = self.ringbuffer_appsink.emit("pull-sample")
        if sample is None:
            logger.warning(f"{self.ringbuffer_appsink} pulled empty sample")
            return Gst.FlowReturn.ERROR

        buffer: Gst.Buffer = sample.get_buffer()

        self.deque.append(buffer)
        # self.PUSH_COUNT +=1
        # logger.info(f"PUSH ({self.PUSH_COUNT}): {datetime.now().isoformat()}: {list(map(lambda buf: buf.pts, self.deque))}")
        # try:
        # except AttributeError:
        #     import pdb;pdb.set_trace()
        #     if self.deque is not None:
        #         raise
        #     self._initialize_dequeue()
        #     logger.info(
        #         f"Ringbuffer queue initialized, size={self.deque.maxlen}"
        #     )
        #     logger.info(
        #         f"Recorder.on_new_sample: FIRST buffer @ {datetime.now()} - pts={buffer.pts}"
        #     )
        #     self.first_pull_buf = datetime.now()
        #     self.deque.append(buffer)
        # else:
        #     logger.debug(
        #         f"Recorder.on_new_sample: INPUT buffer @ {datetime.now()} - pts={buffer.pts}"
        #     )

        return Gst.FlowReturn.OK
