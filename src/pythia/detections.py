# -*- coding: utf-8 -*-
"""Detections handling"""

import abc
import atexit
from collections import deque
import datetime
import json
from pathlib import Path
from typing import Generator
from typing import List
from typing import NamedTuple
from typing import Union
from typing import Tuple

import pyds

from pythia import Gst
from pythia import logger


class BBox(NamedTuple):
    x_min: int
    y_min: int
    x_max: int
    y_max: int


class Detection(NamedTuple):
    frame_num: int
    source_id: str
    class_id: int
    bbox: BBox
    confidence: Union[float, str]


Detections = List[Detection]


class DetectionsObserver(abc.ABC):
    def incoming(self, detections: Detections):
        """Callback to report detections"""


class Notifier:
    def __init__(self):
        self.observers = []

    def add_observer(self, observer: DetectionsObserver):
        """Add detections observer"""
        if hasattr(observer, "incoming"):
            self.observers.append(observer)
        else:
            raise AttributeError("Observer has not on_detection method.")

    def notify(self, detections: Detections):
        """Notify detections to all observers
        # TODO move this to another thread?
        """
        for observer in self.observers:
            observer.incoming(detections)


class DeepstreamAdapter:
    """Helper class to abstract away Deepstream metadata extraction

    It does not contain instance methods

    """

    @classmethod
    def metadata_extract(cls, pad, info, _) -> List[Detection]:
        """Receive, decode & output metadata from probe."""
        detections = [
            frame_dets
            for buffer, frame in cls.frames(info)
            for frame_dets in cls.parse_frame(buffer, frame)
        ]
        return detections

    @staticmethod
    def frames(info) -> Generator[Tuple, None, None]:
        gst_buffer = info.get_buffer()
        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
        frame_list = batch_meta.frame_meta_list
        while frame_list is not None:
            try:
                yield gst_buffer, frame_list
            except StopIteration:
                break
            try:  # Check if this is the last frame
                frame_list = frame_list.next
            except StopIteration:
                break

    @classmethod
    def parse_frame(cls, buffer, frame) -> Detections:
        """Recieve frame_list (Cython PyCapsule) and return list of detections.
        Compatible with DeepStream 5.0.x
        """
        frame_metadata = pyds.NvDsFrameMeta.cast(frame.data)
        source_id = frame_metadata.source_id
        dets: Detections = []
        frame_num = frame_metadata.frame_num

        for obj_meta in cls.meta_objects(frame_metadata):
            bbox = cls.bounding_box(obj_meta)
            dets.append(
                Detection(
                    frame_num,
                    source_id,
                    obj_meta.class_id,
                    bbox,
                    getattr(obj_meta, "confidence", "NO CONFIDENCE"),
                )
            )
        return dets

    @staticmethod
    def meta_objects(metadata):
        """
        Iterates through object metadata. Compatible with DeepStream 5.0.x
        """
        object_list = metadata.obj_meta_list
        while object_list is not None:
            try:
                yield pyds.NvDsObjectMeta.cast(object_list.data)
            except StopIteration:
                break

            try:
                object_list = object_list.next
            except StopIteration:
                break

    @staticmethod
    def bounding_box(obj_meta) -> BBox:
        return BBox(
            obj_meta.rect_params.left,
            obj_meta.rect_params.top,
            obj_meta.rect_params.left + obj_meta.rect_params.width,
            obj_meta.rect_params.top + obj_meta.rect_params.height,
        )


class DetectionsHandler(Notifier):
    def __init__(self, element, observers=None):
        super().__init__()
        self.running_since_dt = datetime.datetime.now()
        self.adapter = DeepstreamAdapter
        self.attach_buffer_probe(element.get_static_pad("sink"))
        for observer in observers or []:
            self.add_observer(observer)

    def attach_buffer_probe(self, srcpad):
        """Call this with a srcpad (eg tiler's)."""
        srcpad.add_probe(Gst.PadProbeType.BUFFER, self.buffer_probe_cb, 0)

    def buffer_probe_cb(self, pad, info, _):
        detections = self.adapter.metadata_extract(pad, info, _)
        if detections:
            self.notify(detections)
        return Gst.PadProbeReturn.OK


class Storage(DetectionsObserver):
    def __init__(self, datestr: str):
        self.persistence = Path.cwd() / f"{datestr}.jsonl"
        self.q = deque()
        # NOTE: For demonstration purposes, the quueue is dumped to disk In production,
        # another thread must consume the queue, eg with `popleft`
        atexit.register(self.dump)

    def incoming(self, detections: Detections):
        """Callback to report detections"""
        self.q.extend(detections)

    def dump(self):
        if self.q:
            with open(self.persistence, "w") as jsonl:
                for detection in self.q:
                    jsonl.write(f"{json.dumps(detection)}\n")


class DetectionLogger(DetectionsObserver):
    def incoming(self, detections: Detections):
        """Callback to report detections"""
        logger.warning(f"Detection incoming{json.dumps(detections)}")
