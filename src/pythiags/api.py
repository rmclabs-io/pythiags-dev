# -*- coding: utf-8 -*-
"""Common interface for pythiags applications with and without Kivy.

.. seealso:: `pythiags.kivy_app`

"""

import abc
import atexit
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import DefaultDict
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from pythiags import Gst
from pythiags import logger
from pythiags.background import StoppableThread
from pythiags.consumer import Consumer
from pythiags.events import EventsHandler
from pythiags.producer import Producer
from pythiags.utils import traced

GST_DEBUG_DUMP_DOT_DIR = os.environ.get("GST_DEBUG_DUMP_DOT_DIR", None)


def gen_dot_filename(clock, reference_time, old, new):
    delta_ns = (clock.get_time() - reference_time) / 1e9
    hours, remain = divmod(delta_ns, 3600)
    minutes, remain = divmod(remain, 60)
    seconds, remain = divmod(remain, 1)

    hours = int(hours)
    minutes = int(minutes)
    seconds = int(seconds)
    remain = str(remain).lstrip("0.").rjust(9, "0")

    # akin to 0.00.00.328088000-gst-launch.NULL_READY.dot
    name = (
        f"{hours}.{minutes:02}.{seconds:02}.{remain}"
        # f"{self.pipeline.stream_time}"
        f"-pythiags.{Gst.Element.state_get_name(old)}_{Gst.Element.state_get_name(new)}"
    )
    return name


class PythiaGsRunner(abc.ABC):
    def __init__(
        self,
        pipeline_string: str,
        metadata_extraction_map: Optional[
            Dict[str, Tuple[Producer, Consumer]]
        ] = None,
    ):

        self.running_since = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
        self.pipeline_string = pipeline_string

        self.metadata_extraction_map = metadata_extraction_map or {}
        self.handlers: DefaultDict[str, List[EventsHandler]] = defaultdict(
            list
        )
        self.workers: DefaultDict[str, List[StoppableThread]] = defaultdict(
            list
        )

        self.__joining: bool = False
        self._clock: Optional[Gst.Clock] = None
        self._running_since_gst: Optional[int] = None

    @property
    def clock(self):
        if not self._clock:
            self._clock = self.pipeline.get_pipeline_clock()
        return self._clock

    @abc.abstractmethod
    def __call__(self, control_logs=True, *a, **kw):
        self._running_since_gst = self.clock.get_time()
        self.control_gst_logs(
            skip=not control_logs,
            keep_default_logger=False,
            use_own_logger=True,
        )
        self.connect_bus()

        self.init_events_handlers()
        from logging import shutdown

        atexit.unregister(shutdown)
        atexit.register(self.join)
        atexit.register(shutdown)

    def control_gst_logs(
        self,
        skip=False,
        disable_debug_logs=False,
        keep_default_logger=False,
        use_own_logger=True,
    ):
        """Modify default Gst loggers.

        Args:
            skip: If set, function call does nothing. Useful for
                scripting.
            disable_debug_logs: If set, completely disable debug logs.
            keep_default_logger: If set, keeps the default gst logger.
            use_own_logger: If set, attaches own logger to the list of
                available gst loggers.

        Debugging handlers negatively impact performance
        # If activated, debugging messages are sent to the debugging
        # handlers. It makes sense to deactivate it for speed issues.

        """
        if skip:
            return
        logger.info(
            f"PythiaGsRunner: Taking control of Gst debug logger from now on..."
        )

        if disable_debug_logs:
            Gst.debug_set_active(False)
            return Gst.debug_remove_log_function(None)
        else:
            Gst.debug_set_active(True)

        if not keep_default_logger:
            Gst.debug_remove_log_function(None)

        if use_own_logger:
            Gst.debug_add_log_function(self.on_message)

    def connect_bus(self):
        # import pdb;pdb.set_trace()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", self.on_eos)
        bus.connect("message::error", self.on_error)
        if GST_DEBUG_DUMP_DOT_DIR:
            path = Path(GST_DEBUG_DUMP_DOT_DIR).resolve()
            if not path.exists() or not path.is_dir():
                logger.warning(
                    f"found `GST_DEBUG_DUMP_DOT_DIR={GST_DEBUG_DUMP_DOT_DIR}` but does not exists. Ignoring..."
                )
                return
            bus.connect("message::state-changed", self.on_state_changed, path)

    def init_events_handlers(self):
        for observer_name, (
            extractor,
            consumer,
        ) in self.metadata_extraction_map.items():
            # FIXME: validate this logic, seems outdated <pwoolvett 2021-01-08T15:39:04>
            if observer_name:
                if not (extractor or consumer):
                    msg = f"pythiagsApi: Observer element with name '{observer_name}' supplied, but neither extractor nor consumer provided"
                    logger.warning(msg)
                elif not (extractor and consumer):
                    msg = f"pythiagsApi: Observer element  with name '{observer_name}' supplied, you must supply both and extractor and consumer provided"
                    raise RuntimeError(msg)
            else:
                if not (extractor or consumer):
                    msg = f"pythiagsApi: None of (observer_name, extractor, consumer) provided. Proceeding without extracting deepstream detections"
                    return logger.warning(msg)
                elif extractor and consumer:
                    observer_name = self.pipeline.children[0].name
                    msg = f"pythiagsApi: No name for observer element supplied. As both extractor and consumer provided, pythiags will use the element named '{observer_name}'"
                    logger.warning(msg)
                else:
                    msg = f"pythiagsApi: No name for observer element supplied. you must supply both and extractor and consumer or none of them."
                    return RuntimeError(msg)

            observer = self.pipeline.get_by_name(observer_name)
            if not observer:
                msg = f"pythiagsApi: Cannot find element with name '{observer_name}' in pipeline ```{self.pipeline_string}```"
                raise RuntimeError(msg)

            handler = EventsHandler(
                attach_on=observer,
                producer=extractor,
                consumer=consumer,
            )
            self.handlers[observer_name].append(handler)
            self.workers[observer_name].append(handler.run_in_background())

    @abc.abstractproperty
    def pipeline(self) -> Gst.Pipeline:
        """The low-level Gst.Pipeline Element."""

    @abc.abstractmethod
    def on_eos(self, bus, message):
        logger.info("Gstreamer: End-of-stream")
        self.join()

    @abc.abstractmethod
    def on_error(self, bus, message):
        err, debug = message.parse_error()
        logger.error("Gstreamer: %s: %s" % (err, debug))

    def on_state_changed(self, bus, msg, path):
        try:
            if msg.src != self.pipeline:
                return
            old, new, pending = msg.parse_state_changed()
            name = gen_dot_filename(
                self.clock,
                self._running_since_gst,
                old,
                new,
            )
            Gst.debug_bin_to_dot_file(
                self.pipeline, Gst.DebugGraphDetails.ALL, name
            )

        except Exception as exc:
            logger.exception(exc)

    def on_message(
        self, category, level, dfile, dfctn, dline, source, message, *user_data
    ):
        log = getattr(
            logger, level.get_name(level).strip().lower(), logger.info
        )
        try:
            return log(message.get())
        except TypeError:
            return log(repr(message))

    def join(self):

        if self.__joining:
            logger.info("PythiaGsApi: Already Joining")
            return

        logger.debug("PythiaGsApi: Joining ")
        self.__joining = True

        for observer_name, workers in self.workers.items():
            logger.info(
                f"pythiagsApi: Waiting for {observer_name}'s workers..."
            )
            for worker in workers:
                logger.debug(
                    f"pythiagsApi: Stopping queue {worker.queue} from {worker}..."
                )
                worker.queue.join()
                logger.debug(f"pythiagsApi: Stopping worker {worker}...")
                worker.external_stop = True
            for worker in workers:
                logger.debug(f"pythiagsApi: Joining worker {worker}...")
                worker.join()

        self.workers = defaultdict(list)
        logger.debug("PythiaGsApi: Joining Finished")
