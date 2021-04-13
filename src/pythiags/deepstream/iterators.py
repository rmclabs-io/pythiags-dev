# -*- coding: utf-8 -*-
"""Shortcuts to iterate over `pyds.GList` from metadata."""


from typing import Any
from typing import Callable
from typing import Generator
from typing import Tuple

import pyds
import pyds_analytics_meta
import pyds_bbox_meta
import pyds_tracker_meta

from pythiags import Gst
from pythiags import logger


def glist_iterate(
    iterable: pyds.GList, cast: Callable[["PyCapsule"], Any]
) -> Generator[Tuple, None, None]:
    """Generator for `pyds.GList` objects.

    A Pythonic way for iterating over deepstream metadata.

    Example:

      When extracting object metadata from frame_metadata, in c++::

      ```c++
      for (
          NvDsMetaList * l_obj = frame_meta->obj_meta_list;
          l_obj != NULL;
          l_obj = l_obj->next
      ) {
          NvDsObjectMeta *object_meta = (NvDsObjectMeta *) (l_obj->data);
          do_something_with(object_meta);
      }
      ```

      And its equivalent in python::

      ```python
      for object_meta in glist_iterate(
          frame_metadata.obj_meta_list,
          pyds.NvDsObjectMeta.cast
      ):
          do_something_with(object_meta)
      ```


    Args:
        iterable: The object to iterate over. Its `data` attribute
            (PyCapsule) is used to instantiate objects.
        cast: This function is called to instantiate objects from
            `iterable.data`

    Yields:
        The Object instantiated when calling the `cast` function.

    """
    while iterable is not None:
        try:
            data = cast(iterable.data)
        except StopIteration:
            break
        yield data
        try:
            iterable = iterable.next
        except StopIteration:
            break


def labels_per_batch(
    batch_meta: pyds.NvDsBatchMeta,
) -> Generator[pyds.NvDsLabelInfo, None, None]:
    yield from glist_iterate(
        batch_meta.label_info_meta_pool.full_list, pyds.NvDsLabelInfo.cast
    )


def buf2batchmeta(gst_buffer: Gst.Buffer) -> pyds.NvDsBatchMeta:
    return pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))


def frames_per_batch(
    info: Gst.PadProbeInfo,
) -> Generator[pyds.NvDsFrameMeta, None, None]:
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        return logger.warning("Unable to get GstBuffer ")

    batch_meta = buf2batchmeta(gst_buffer)

    # A Single buffer contains several frames
    yield from glist_iterate(
        batch_meta.frame_meta_list, pyds.NvDsFrameMeta.cast
    )


def objects_per_frame(
    frame_metadata: pyds.NvDsFrameMeta,
) -> Generator[pyds_bbox_meta.NvDsObjectMeta, None, None]:
    yield from glist_iterate(
        frame_metadata.obj_meta_list, pyds_bbox_meta.NvDsObjectMeta.cast
    )


def tracker_per_batch(
    info: Gst.PadProbeInfo,
) -> Generator[pyds.NvDsUserMeta, None, None]:
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        return print("Unable to get GstBuffer")
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))

    for user_meta in glist_iterate(
        batch_meta.batch_user_meta_list, pyds.NvDsUserMeta.cast
    ):
        if (
            user_meta.base_meta.meta_type
            == pyds.NvDsMetaType.NVDS_TRACKER_PAST_FRAME_META
        ):
            yield user_meta


def shadow_info_per_batch(
    shadow_metadata: pyds.NvDsUserMeta,
) -> Generator[pyds.NvDsPastFrameObjList, None, None]:
    past_frame_object_batch = pyds_tracker_meta.NvDsPastFrameObjBatch_cast(
        shadow_metadata.user_meta_data
    )
    for (
        past_frame_object_stream
    ) in pyds_tracker_meta.NvDsPastFrameObjBatch_list(past_frame_object_batch):
        for (
            past_frame_object_list
        ) in pyds_tracker_meta.NvDsPastFrameObjStream_list(
            past_frame_object_stream
        ):
            yield past_frame_object_list


def classification_per_object(
    object_metadata: pyds_bbox_meta.NvDsObjectMeta,
) -> Generator[pyds.NvDsClassifierMeta, None, None]:
    yield from glist_iterate(
        object_metadata.classifier_meta_list, pyds.NvDsClassifierMeta.cast
    )


def labels_per_classification(
    classifier_metadata: pyds.NvDsClassifierMeta,
) -> Generator[pyds.NvDsLabelInfo, None, None]:
    yield from glist_iterate(
        classifier_metadata.label_info_list, pyds.NvDsLabelInfo.cast
    )


def labels_per_object(
    object_metadata: pyds_bbox_meta.NvDsObjectMeta,
) -> Generator[pyds.NvDsLabelInfo, None, None]:
    for classifier_metadata in classification_per_object(object_metadata):
        for label_info in labels_per_classification(classifier_metadata):
            yield label_info


def analytics_per_frame(
    frame_metadata: pyds.NvDsFrameMeta,
) -> Generator[pyds_analytics_meta.NvDsAnalyticsFrameMeta, None, None]:
    for user_meta in glist_iterate(
        frame_metadata.frame_user_meta_list, pyds.NvDsUserMeta.cast
    ):
        if user_meta.base_meta.meta_type != pyds.nvds_get_user_meta_type(
            "NVIDIA.DSANALYTICSFRAME.USER_META"
        ):
            continue
        yield pyds_analytics_meta.NvDsAnalyticsFrameMeta.cast(
            user_meta.user_meta_data
        )


def frame_analytics_per_batch(
    info: Gst.PadProbeInfo,
) -> Generator[pyds_analytics_meta.NvDsAnalyticsFrameMeta, None, None]:
    for frame_meta in frames_per_batch(info):
        yield from analytics_per_frame(frame_meta)


def analytics_per_object(
    obj_meta: pyds_bbox_meta.NvDsObjectMeta,
) -> Generator[pyds_analytics_meta.NvDsAnalyticsObjInfo, None, None]:
    for user_meta in glist_iterate(
        obj_meta.obj_user_meta_list, pyds.NvDsUserMeta.cast
    ):
        if user_meta.base_meta.meta_type != pyds.nvds_get_user_meta_type(
            "NVIDIA.DSANALYTICSOBJ.USER_META"
        ):
            continue
        yield pyds_analytics_meta.NvDsAnalyticsObjInfo.cast(
            user_meta.user_meta_data
        )


def object_analytics_per_frame(
    frame_metadata: pyds.NvDsFrameMeta,
) -> Generator[pyds_analytics_meta.NvDsAnalyticsObjInfo, None, None]:
    for obj_meta in objects_per_frame(frame_metadata):
        yield from analytics_per_object(obj_meta)
