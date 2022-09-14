"""Shortcuts to iterate over `pyds.GList` -from metadata."""
from __future__ import annotations

from typing import Iterator
from typing import Tuple
from typing import Type

import numpy as np
import pyds

from pythia.types import PydsClass
from pythia.utils.ds import FrameAnalytics
from pythia.utils.ds import ObjectAnalytics
from pythia.utils.ds import SemanticMasks
from pythia.utils.ds import SupportedUserMeta
from pythia.utils.maskrcnn import extract_maskrcnn_mask


def glist_iter(
    container_list: pyds.GList,
    klass: Type[PydsClass],
) -> Iterator:
    """Iterate over `pyds.GList` objects.

    A Pythonic way for iterating over deepstream metadata.

    Example:

        When extracting object metadata from frame_metadata, in c++:

        .. code-block:: cpp

            for (
                NvDsMetaList * l_obj = frame_meta->obj_meta_list;
                l_obj != NULL;
                l_obj = l_obj->next
            ) {
                NvDsObjectMeta *object_meta = (NvDsObjectMeta *) (l_obj->data);
                do_something_with(object_meta);
            }

        And its equivalent in python:

        .. code-block:: python

            for object_meta in glist_iter(
                frame_metadata.obj_meta_list,
                pyds.NvDsObjectMeta
            ):
                do_something_with(object_meta)

    Args:
        container_list: The object to iterate over. Its `data` attribute
            (PyCapsule) is used to instantiate objects.
        klass: This class is instantiated via its `cast` constructor,
            using `container_list.data` as its only argument.

    Yields:
        The Object instantiated when calling the `cast` function.

    """
    while container_list is not None:
        try:
            meta = klass.cast(container_list.data)
        except StopIteration:
            break
        yield meta
        try:
            container_list = container_list.next
        except StopIteration:
            break


def _iter_user_meta(
    container_list: pyds.GList,
    kind: Type[SupportedUserMeta],
) -> Iterator:
    for meta in glist_iter(container_list, pyds.NvDsUserMeta):
        if kind.condition(meta):
            try:
                yield kind.klass.cast(meta.user_meta_data)
            except StopIteration:
                break


def frames_per_batch(
    batch_meta: pyds.NvDsBatchMeta,
) -> Iterator[pyds.NvDsFrameMeta]:
    """Yield frame metadata from the batch in a buffer.

    Args:
        batch_meta: deepstream batch metadata from a buffer, as received
            in a bufer pad probe.

    Yields:
        frame metadata. A single batch might have multiple values when
            `nvstreammux` batches its input frames.

    """
    for frame_meta in glist_iter(
        batch_meta.frame_meta_list, pyds.NvDsFrameMeta
    ):
        yield frame_meta


def objects_per_frame(
    frame_meta: pyds.NvDsFrameMeta,
) -> Iterator[pyds.NvDsObjectMeta]:
    """Yield object metadata from a single frame in a batch.

    Args:
        frame_meta: single frame metadata

    Yields:
        object metadata. A single frame might have multiple values when
            a single or multiple `nvinfer` generate multiple detections.

    """
    yield from glist_iter(frame_meta.obj_meta_list, pyds.NvDsObjectMeta)


def classification_per_object(
    object_metadata: pyds.NvDsObjectMeta,
) -> Iterator[pyds.NvDsClassifierMeta]:
    """Yield classification metadata from a single object in a frame.

    Args:
        object_metadata: deepstream detection metadata from `nvinfer`.

    Yields:
        classification metadata. A single object might have multiple
            values.

    """
    yield from glist_iter(
        object_metadata.classifier_meta_list, pyds.NvDsClassifierMeta
    )


def analytics_per_obj(
    object_metadata: pyds.NvDsObjectMeta,
) -> Iterator[pyds.NvDsAnalyticsObjInfo]:
    """Yield analytics metadata from a single object in a frame.

    Args:
        object_metadata: deepstream detection metadata from `nvinfer`.

    Yields:
        analytics metadata. A single object might have multiple values.

    """
    yield from _iter_user_meta(
        object_metadata.obj_user_meta_list, kind=ObjectAnalytics
    )


def labels_per_classification(
    classifier_meta: pyds.NvDsClassifierMeta,
) -> Iterator[pyds.NvDsLabelInfo]:
    """Yield label metadata from a single classification in an object.

    Args:
        classifier_meta: deepstream classification metadata from
            `nvinfer`.

    Yields:
        label metadata. A single classification might have multiple
            values.

    """
    yield from glist_iter(
        classifier_meta.label_info_list,
        pyds.NvDsLabelInfo,
    )


def labels_per_obj(
    object_metadata: pyds.NvDsObjectMeta,
) -> Iterator[pyds.NvDsLabelInfo]:
    """Yield label metadata from a single object in a frame.

    Args:
        object_metadata: deepstream detection metadata from `nvinfer`.

    Yields:
        label metadata. A single object might have multiple labels.

    """
    for classifier_meta in classification_per_object(object_metadata):
        yield from labels_per_classification(classifier_meta)


def analytics_per_frame(
    frame_meta: pyds.NvDsFrameMeta,
) -> Iterator[pyds.NvDsAnalyticsFrameMeta]:
    """Yield frame-level analytics metadata.

    Args:
        frame_meta: deepstream frame-level metadata from `nvinfer`.

    Yields:
        analytics metadata. A single frame might have multiple values.

    """
    yield from _iter_user_meta(
        frame_meta.frame_user_meta_list,
        kind=FrameAnalytics,
    )


def semantic_masks_per_frame(
    frame_meta: pyds.NvDsFrameMeta,
) -> Iterator[np.ndarray]:
    """Yield frame-level semantic segmentation metadata.

    Args:
        frame_meta: deepstream frame-level metadata from `nvinfer`.

    Yields:
        semantic segmentation bidimensional matrix. A single frame will
            probably have several values.

    """
    for segmeta in _iter_user_meta(
        frame_meta.frame_user_meta_list,
        kind=SemanticMasks,
    ):
        masks_ = pyds.get_segmentation_masks(segmeta)
        masks = np.array(masks_, copy=True, order="C")
        yield masks


def objects_per_batch(
    batch_meta: pyds.NvDsBatchMeta,
) -> Iterator[tuple[pyds.NvDsFrameMeta, pyds.NvDsObjectMeta]]:
    """Yield frame and object metadata from the batch in a buffer.

    Args:
        batch_meta: deepstream batch metadata from a buffer, as received
            in a bufer pad probe.

    Yields:
        frame metadata. A single batch might have multiple values when
            `nvstreammux` batches its input frames.
        object metadata. A single frame might have multiple values when
            a single or multiple `nvinfer` generate multiple detections.

    """
    for frame_meta in frames_per_batch(batch_meta):
        for obj_meta in objects_per_frame(frame_meta):
            yield frame_meta, obj_meta


def instance_masks_per_batch(
    batch_meta: pyds.NvDsBatchMeta,
) -> Iterator[Tuple[pyds.NvDsFrameMeta, pyds.NvDsObjectMeta, np.ndarray]]:
    """Yield frame, object, and mask metadata from the batch in a buffer.

    Args:
        batch_meta: deepstream batch metadata from a buffer, as received
            in a bufer pad probe.

    Yields:
        * frame metadata. A single batch might have multiple values when
            `nvstreammux` batches its input frames.
        * object metadata. A single frame might have multiple values when
            a single or multiple `nvinfer` generate multiple detections.
        * instance segmentation. bidimensional matrix.

    """
    for frame_meta, obj_meta in objects_per_batch(batch_meta):
        yield frame_meta, obj_meta, extract_maskrcnn_mask(obj_meta)
