#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enable pipeline measurements from Deepstream"""

import atexit
from collections import defaultdict
import configparser
from contextlib import contextmanager
from datetime import datetime
import imghdr
import json
import logging
import struct
from pathlib import Path
from queue import Queue
import threading
import sys

from gi.repository import GObject
from tqdm import tqdm

from pythia import Gst
from pythia import logger
from pythia.detections import Detections
from pythia.detections import DetectionsObserver
from pythia.detections import DetectionsHandler
from pythia.video import parse_launch

REPORT_PROGRESS_EVERY_SEC = 10


class GstEos(Exception):
    def ___repr__(self):
        return "Gstreamer End-of-Stream"


class GstError(Exception):
    def ___repr__(self):
        return "Gstreamer Error"


class DeepstreamRunner(DetectionsObserver):
    def __init__(
        self,
        pipeline_string,
        observer_name="observer",
        detections_folder=None,
        classname_mapper=None,
        total_frames=None,
    ):
        """"""
        GObject.threads_init()
        self.running_since = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
        self.pipeline_string = pipeline_string
        self.mainloop = GObject.MainLoop()
        self.pipeline = parse_launch(self.pipeline_string)
        self.observer_name = observer_name
        self.detections_q = Queue()
        self.timings_q = Queue()
        self.detections_folder = (
            Path(detections_folder)
            if detections_folder
            else (Path.cwd() / f"{self.running_since}/labels")
        )
        self.detections_folder.mkdir(exist_ok=False, parents=True)
        self.classname_mapper = self.init_classname_mapper(self.pipeline, classname_mapper)
        self.total_frames = total_frames

    def __call__(
        self,
        control_logs=True,
        count_buffers=False,
        report_progress_every_sec=REPORT_PROGRESS_EVERY_SEC,
    ):
        self.control_gst_logs(
            skip=not control_logs,
            keep_default_logger=False,
            use_own_logger=True,
        )
        self.connect_bus()
        
        self.observer, self.handler = self.attach_detections_monitor()
        self.attach_timing_monitor()
        # self.attach_buffer_counter(
        #     skip=not count_buffers, report_progress_every_sec=report_progress_every_sec
        # )

        queue_workers = self.start_queue_workers()

        before = datetime.now()
        self.pipeline.set_state(Gst.State.PLAYING)
        try:
            self.mainloop.run()
        except BaseException as exc:
            logger.info(f"{type(self).__name__}: Exec Time ={datetime.now() - before}")
            self.stop(workers=queue_workers, exception=exc)
            raise
        else:
            logger.info(f"{type(self).__name__}: Exec Time ={datetime.now() - before}")
            self.stop(
                workers=queue_workers,
            )
        return self.detections_q


    @classmethod
    def init_classname_mapper(cls, pipeline, classname_mapper):
        if not classname_mapper:
            return {}
        if isinstance(classname_mapper, str):
            it = pipeline.iterate_elements()
            while True:
                result, el = it.next()
                if result != Gst.IteratorResult.OK:
                    msg = f"Completed searching the pipeline but found no nvinfer containing {classname_mapper}"
                    raise ValueError(msg)
                if type(el).__name__ != "GstNvInfer":
                    continue
                path = el.get_property("config-file-path")
                if path.endswith(classname_mapper):
                    return cls.gen_classname_mapper(path)
        if isinstance(classname_mapper, dict):
            return classname_mapper
        raise ValueError(f"Invalid classname_mapper=`{classname_mapper}`")


    def start_queue_workers(self):
        def detections_worker():
            while True:
                detection = self.detections_q.get()
                with open(
                    self.detections_folder / f"{detection.frame_num:012d}.txt", "w"
                ) as detection_file:
                    klass = detection.class_id
                    detection_file.write(
                        " ".join(
                            str(x)
                            for x in [
                                self.classname_mapper.get(klass),
                                str(klass),
                                detection.confidence,
                                detection.bbox.x_min,
                                detection.bbox.y_min,
                                detection.bbox.x_max,
                                detection.bbox.y_max,
                            ]
                        )
                        + "\n"
                    )
                self.detections_q.task_done()

        def timings_worker():
            while True:
                padname, datetime = self.timings_q.get()
                with open(
                    self.detections_folder / "timings.jsonl", "a+"
                ) as timings_file:
                    timings_file.write(json.dumps({
                        "padname": padname,
                        "datetime": str(datetime),
                    }) + '\n')
                self.timings_q.task_done()

        detections_th = threading.Thread(target=detections_worker, daemon=True).start()
        timings_th = threading.Thread(target=timings_worker, daemon=True).start()
        return detections_th, timings_th

        def parse_kitti(detection_dict):
            detections = []
            for detection in json.loads(detection_dict["detection_list"]):
                detections.append(
                    f"{CLASS_MAPPING[detection['class']]} {detection['confidence']} {detection['bbox']['x_min']} {detection['bbox']['y_min']} {detection['bbox']['x_max']} {detection['bbox']['y_max']}\n"
                )
            return detections

    def attach_detections_monitor(self):
        observer = self.pipeline.get_by_name(self.observer_name)
        if not observer:
            raise RuntimeError(
                f"Cannot find {self.observer_name} in pipeline ```{self.pipeline_string}```"
            )

        handler = DetectionsHandler(observer, [self])
        return observer, handler

    def attach_timing_monitor(self):
        def buffer_counter(pad, __, padname):
            data = (padname, datetime.now())
            print(data)
            self.timings_q.put(data)
            return Gst.PadProbeReturn.OK

        for pad, name in zip(("src", "sink"), ("src", self.observer_name)):
            el = self.pipeline.get_by_name(name)
            pad = el.get_static_pad(pad)
            pad.add_probe(
                Gst.PadProbeType.BUFFER, buffer_counter, name
            )

    def attach_buffer_counter(self, skip, report_progress_every_sec):
        if skip:
            return

        self.ctr = defaultdict(int)
        atexit.register(lambda: logger.info(f"BufferCounter: {dict(self.ctr)}"))

        self.pbar = tqdm(total=self.total_frames)
        self.pbar.update(1)

        self.last_progress_report = datetime.now()
        first = None
        def buffer_counter(pad, __, loc):
            # import pdb; pdb.set_trace()
            nonlocal first
            if not first:
                first = datetime.now()
            self.ctr[loc] += 1
            if loc != "src":
                return Gst.PadProbeReturn.OK

            # percent = self.ctr[loc] / total
            # if int(percent) != last:
            # last = int(percent)
            percent = self.ctr[loc] / self.total_frames
            now = datetime.now()
            if (
                now - self.last_progress_report
            ).total_seconds() > report_progress_every_sec:
                self.last_progress_report = now
                frameno = pad.parent.get_property("index")
                elapsed=((now-first).total_seconds())
                fps = frameno/elapsed
                info = " | ".join([
                    "PipelineProgress: {percent:<7}",
                    "Current Frame={frameno:<5}",
                    "Time Elapsed={elapsed:<10}",
                    "Average FPS={fps:<15}"
                ]).format(
                    percent=f"{percent:.2%}", frameno=frameno, elapsed=elapsed, fps=fps
                )
                logger.info(info)
            return Gst.PadProbeReturn.OK

        self.pipeline.get_by_name(
            "src"
        ).get_static_pad(
            "src"
        ).add_probe(
            Gst.PadProbeType.BUFFER, buffer_counter, "src"
        )

        self.observer.get_static_pad("sink").add_probe(
            Gst.PadProbeType.BUFFER, buffer_counter, self.observer_name
        )
        return self.pbar

    def connect_bus(self):
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", self.on_eos)
        bus.connect("message::error", self.on_error)

    def stop(self, queue_workers=None, **data):
        if "exception" in data or "error" in data:
            logger.error(data)
        else:
            logger.info(f"GStreamer: STOP - {data}")
        from time import sleep

        sleep(1)
        self.pipeline.set_state(Gst.State.NULL)
        self.mainloop.quit()
        if queue_workers:
            for queue_worker in queue_workers:
                queue_worker.stop()

    def on_eos(self, bus, message):
        logger.info("Gstreamer: End-of-stream")
        self.stop(reason=GstEos)

    def on_error(self, bus, message):
        err, debug = message.parse_error()
        logger.error("Gstreamer: %s: %s" % (err, debug))
        self.stop(error=GstError)
        sys.exit(1)

    def on_message(
        self, category, level, dfile, dfctn, dline, source, message, *user_data
    ):
        log = getattr(logger, level.get_name(level).strip().lower(), "info")
        return log(message.get())

    def control_gst_logs(
        self,
        skip=False,
        disable_debug_logs=False,
        keep_default_logger=False,
        use_own_logger=True,
    ):
        if skip:
            return
        logger.info(
            f"{type(self).__name__}: Taking control of Gst debug logger from now on..."
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

        # If activated, debugging messages are sent to the debugging handlers. It makes sense to deactivate it for speed issues.

    @staticmethod
    def gen_classname_mapper(config_file_path):
        def build_dict(labels_file):
            with open(labels_file, "r") as labelsfile:
                mapper = {
                    lineno: kind.rstrip("\n")
                    for lineno, kind in enumerate(labelsfile.readlines())
                }
            return mapper

        def get_key_or_raise(conf, *keyspath):
            "Walk down a dict-like obj until the end of the path or invalid path"
            out = conf
            road = ""
            for part in keyspath:
                try:
                    road += f"->{str(part)}"
                    out = out[part]
                except Exception as exc:
                    road = road.lstrip("->")
                    raise ValueError(
                        f"Cannot read property {road} in `{conf.__source_file__}`"
                    ) from exc
            return out

        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(config_file_path)
        config.__source_file__ = config_file_path
        labels_file = Path(get_key_or_raise(config, "property", "labelfile-path"))
        if not labels_file.is_absolute():
            labels_file = (Path(config_file_path).parent / labels_file).resolve()
        mapper = build_dict(labels_file)

        return mapper

    @staticmethod
    def guess_resolution(filesrc_pattern):
        def get_image_size(fname):
            """Determine the image type of fhandle and return its size."""
            with open(fname, "rb") as fhandle:
                head = fhandle.read(24)
                if len(head) != 24:
                    raise
                if imghdr.what(fname) == "png":
                    check = struct.unpack(">i", head[4:8])[0]
                    if check != 0x0D0A1A0A:
                        raise
                    return struct.unpack(">ii", head[16:24])
                elif imghdr.what(fname) == "gif":
                    return struct.unpack("<HH", head[6:10])
                elif imghdr.what(fname) == "jpeg":
                    fhandle.seek(0)  # Read 0xff next
                    size = 2
                    ftype = 0
                    while not 0xC0 <= ftype <= 0xCF:
                        fhandle.seek(size, 1)
                        byte = fhandle.read(1)
                        while ord(byte) == 0xFF:
                            byte = fhandle.read(1)
                        ftype = ord(byte)
                        size = struct.unpack(">H", fhandle.read(2))[0] - 2
                    # We are at a SOFn block
                    fhandle.seek(1, 1)  # Skip `precision' byte.
                    return struct.unpack(">HH", fhandle.read(4))

                raise

        path = Path(filesrc_pattern)
        fname = str(next(path.parent.glob(f"*{path.suffix}")))

        return get_image_size(fname)

    @classmethod
    def precision_recall(
        cls,
        config_file_path,
        filesrc_pattern,
        start_index=0,
        draw=False,
    ):
        """
        FIXME: currently using jpegdec because nvjpegdec produces segfault with labs103
        """
        if not draw:
            sink = "fakesink sync=False"
        else:
            sink = """\
                ! nvvideoconvert
                ! nvdsosd
                ! nvvideoconvert
                ! videoconvert
                ! tee name=t
                ! queue 
                ! xvimagesink sync=false"  # TODO: add nvdsosd
                t.src_1
                ! jpegeng
                ! multifilesrc
            """

        height, width = cls.guess_resolution(filesrc_pattern)
        classname_mapper = cls.gen_classname_mapper(config_file_path)

        _path = Path(filesrc_pattern)
        stop_index = (
            sum(1 for x in _path.parent.glob(f"*{_path.suffix}") if len(x.stem) == 12)
            - 1
        )
        observer_name = "monitor"
        pipeline_str = f"""\
            multifilesrc
              name=src
              location={filesrc_pattern}
              caps="image/jpeg"
              stop-index={stop_index}
              start-index={start_index}
            ! jpegdec
              name=decoder
            ! nvvideoconvert
            ! video/x-raw(memory:NVMM), format=NV12, width={width}, height={height}
            ! m.sink_0
              nvstreammux
              name=m
              batch-size=1
              width={width}
              height={height}
              batched-push-timeout=1
            ! nvinfer
              config-file-path={config_file_path}
            ! identity name={observer_name}
            ! {sink}
        """
        runner = cls(
            pipeline_str,
            observer_name=observer_name,
            classname_mapper=classname_mapper,
            total_frames=stop_index - start_index,
        )
        return runner

    def incoming(self, detections: Detections):
        """Callback to report detections"""
        for det in detections:
            self.detections_q.put(det)


def demo():
    pr = DeepstreamRunner.precision_recall(
        "/mnt/nvme/pythia/assets/models/peoplenet/nvinfer.conf",
        "/mnt/nvme/pythia/assets/datasets/labs_v1.0.3/images/%012d.jpg",
        draw=True,
    )

    pr(
        control_logs=True,
        count_buffers=True,
        report_progress_every_sec=1,
    )


if __name__ == "__main__":
    demo()
