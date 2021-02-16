from typing import Generator

import pyds
import pyds_tracker_meta

from pythiags import Gst
from pythiags import logger
from pythiags.deepstream.iterators import frames_per_batch
from pythiags.deepstream.iterators import labels_per_object
from pythiags.deepstream.iterators import objects_per_frame
from pythiags.deepstream.iterators import shadow_info_per_batch
from pythiags.deepstream.iterators import tracker_per_batch
from pythiags.deepstream.parsers import detector_bbox
from pythiags.deepstream.parsers import last_bbox
from pythiags.deepstream.parsers import past_bbox
from pythiags.deepstream.parsers import tracker_bbox
from pythiags.models import Detection
from pythiags.models import Detections
from pythiags.models import TrackerList
from pythiags.models import TrackerShadow
from pythiags.producer import Producer


class DetectorMetadataExtractor(Producer):
    """Extract metadata after `nvinfer` elements in detection mode.

    .. seealso:: pyds iterators in `pythiags.pyds_iterators`. ..
    seealso:: pyds parsers in `pythiags.pyds_parsers`.

    """

    def extract_metadata(
        self, pad: Gst.Pad, info: Gst.PadProbeInfo
    ) -> Detections:
        """Extract pyds detection metadata, bufferprobe callback.

        It is in charge of receiving, decoding & outputing metadata from
        probe.

        Args:
            pad: Where the callback is attached
            info: Callback information

        Returns:
            `Detections` for a single buffer batch. May be empty.

        """
        dets = []
        for frame_metadata in frames_per_batch(info):
            # NOTE: Extract & cast frame-level metadata here for performance
            # <pwoolvett 2021-01-04T14:12:02>
            source_id = frame_metadata.source_id
            frame_num = frame_metadata.frame_num
            dets.extend(
                self.dets_per_frame(frame_metadata, source_id, frame_num)
            )
        return dets

    def dets_per_frame(
        self,
        frame_metadata: pyds.NvDsFrameMeta,
        source_id: int,
        frame_num: int,
    ) -> Generator[Detection, None, None]:
        """Obtain detections from pyds metadata.

        .. seealso:: pyds iterators in `pythiags.pyds_iterators`. ..
        seealso:: pyds parsers in in `pythiags.pyds_parsers`.

        """

        for detected_object in objects_per_frame(frame_metadata):
            yield Detection(
                frame_num,
                source_id,
                detected_object.obj_label,
                detector_bbox(detected_object),
                tracker_bbox(detected_object),
                getattr(detected_object, "confidence", "NO CONFIDENCE"),
                detected_object.object_id,
            )


class ClassifierMetadataExtractor(DetectorMetadataExtractor):
    """Extract metadata after `nvinfer` elements in classifier mode."""

    @classmethod
    def dets_per_frame(
        cls,
        frame_metadata: pyds.NvDsFrameMeta,
        source_id: int,
        frame_num: int,
    ) -> Generator[Detection, None, None]:

        for obj_meta in objects_per_frame(frame_metadata):
            detected_label = obj_meta.obj_label
            detector_bbox_ = detector_bbox(obj_meta)
            tracker_bbox_ = tracker_bbox(obj_meta)
            object_id = obj_meta.object_id
            found = False
            for label_info in labels_per_object(obj_meta):
                clasif_label = label_info.result_label
                found = True
                if clasif_label == detected_label:
                    yield Detection(
                        frame_num,
                        source_id,
                        detected_label,
                        detector_bbox_,
                        tracker_bbox_,
                        getattr(obj_meta, "confidence", "NO CONFIDENCE"),
                        object_id,
                    )
            if not found:
                logger.warning(
                    f"Conficting frame with no clasif for detaction: {frame_num}",
                    flush=True,
                )


class TrackerShadowMetadataExtractor(Producer):
    def extract_metadata(
        self, pad: Gst.Pad, info: Gst.PadProbeInfo
    ) -> TrackerList:
        shadows = []
        for tracker_shadow_metadata in tracker_per_batch(info):
            for past_frame_object_list in shadow_info_per_batch(
                tracker_shadow_metadata
            ):
                shadows.extend(self.parse(past_frame_object_list))
        return shadows

    def parse(
        self, past_frame_object_list: pyds.NvDsPastFrameObjList
    ) -> Generator[TrackerShadow, None, None]:
        for past_frame_object in pyds_tracker_meta.NvDsPastFrameObjList_list(
            past_frame_object_list
        ):
            yield TrackerShadow(
                past_frame_object.frameNum + 1,
                past_frame_object.frameNum,
                past_frame_object_list.objLabel,
                past_bbox(past_frame_object),
                past_frame_object.confidence,
                past_frame_object.age,
                past_frame_object_list.uniqueId,
            )
