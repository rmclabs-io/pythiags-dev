from typing import Union

import pyds
import pyds_bbox_meta
import pyds_tracker_meta

from pythiags.models import Bbox


def _bounding_box(coords: pyds.NvOSD_RectParams) -> Bbox:
    return Bbox(
        int(coords.left),
        int(coords.top),
        int(coords.left + coords.width),
        int(coords.top + coords.height),
    )


def detector_bbox(obj_meta: pyds_bbox_meta.NvDsObjectMeta) -> Bbox:
    """Detector Bounding box from NvDsObjectMeta."""
    return _bounding_box(obj_meta.detector_bbox_info.org_bbox_coords)


def tracker_bbox(obj_meta: pyds_bbox_meta.NvDsObjectMeta) -> Bbox:
    """Tracker Bounding box from NvDsObjectMeta."""
    return _bounding_box(obj_meta.tracker_bbox_info.org_bbox_coords)


def last_bbox(obj_meta: pyds_bbox_meta.NvDsObjectMeta) -> Bbox:
    """Bounding box (NvDsOsd)  box - last edited - from NvDsObjectMeta."""
    return _bounding_box(obj_meta.rect_params)


def past_bbox(past_frame_object: pyds.NvDsPastFrameObj) -> Bbox:
    """Bounding box from NvDsPastFrameObj."""
    return _bounding_box(past_frame_object.tBbox)
