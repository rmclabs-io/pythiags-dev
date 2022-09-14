"""Deepstream interface, utilities and customization."""
from __future__ import annotations

from typing import Any
from typing import Callable
from typing import ClassVar
from typing import Protocol
from typing import Type

import pyds

from pythia.types import PydsClass
from pythia.utils.gst import Gst


def buf2batchmeta(gst_buffer: Gst.Buffer) -> pyds.NvDsBatchMeta:
    """Get batch metadata from gstreamer buffer.

    Args:
        gst_buffer: gstreamer buffer, as received in a pad buffer probe.

    Returns:
        The deepstream metadata contained in the buffer.

    See Also:
        :func:`pyds.gst_buffer_get_nvds_batch_meta`

    """
    return pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))


def info2batchmeta(info: Gst.PadProbeInfo) -> pyds.NvDsBatchMeta | None:
    """Get batch metadata from gstreamer buffer probe info.

    Args:
        info: gstreamer probe info, as received in a pad buffer probe.

    Returns:
        The deepstream metadata contained in the buffer.

    See Also:
        :func:`pyds.gst_buffer_get_nvds_batch_meta`

    """
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return None
    return buf2batchmeta(gst_buffer)


def _is_analytics_meta(user_meta: pyds.NvDsUserMeta) -> bool:
    return user_meta.base_meta.meta_type == pyds.nvds_get_user_meta_type(
        "NVIDIA.DSANALYTICSOBJ.USER_META"
    )


def _is_frameanalytics_meta(user_meta: pyds.NvDsUserMeta) -> bool:
    return user_meta.base_meta.meta_type == pyds.nvds_get_user_meta_type(
        "NVIDIA.DSANALYTICSFRAME.USER_META"
    )


def _is_segmentation_meta(user_meta: pyds.NvDsUserMeta) -> bool:
    return user_meta.base_meta.meta_type == pyds.NVDSINFER_SEGMENTATION_META


def inject_external_classification(
    batch_meta: pyds.NvDsBatchMeta,
    obj_meta: pyds.NvDsObjectMeta,
    **data: dict[str, Any],
) -> None:
    """Inject classification metadata.

    If "label" is present, also injects it into the display meta.

    Args:
        batch_meta: deepstream batch metadata.
        obj_meta: deepstream object metadata to inject classification
            into.
        data: parameters for :class:`pyds.NvDsLabelInfo`.

    """

    classifier_meta = pyds.nvds_acquire_classifier_meta_from_pool(batch_meta)
    label_info = pyds.nvds_acquire_label_info_meta_from_pool(batch_meta)

    for name, value in data.items():
        setattr(label_info, name, value)

    pyds.nvds_add_label_info_meta_to_classifier(classifier_meta, label_info)
    pyds.nvds_add_classifier_meta_to_object(obj_meta, classifier_meta)

    if "label" in data:
        label = data["label"]
        txt_params = obj_meta.text_params
        original = pyds.get_string(txt_params.display_text)
        obj_meta.text_params.display_text = f"{original} {label}"


UserMetaCondition = Callable[[pyds.NvDsUserMeta], bool]


class SupportedUserMeta(Protocol):  # noqa: R0903
    """Minimum API to parse custom user meta."""

    condition: ClassVar[UserMetaCondition]
    """Discriminator to filteruser meta type."""

    klass: ClassVar[Type[PydsClass]]
    """Class to use for casting when filter passes."""


class FrameAnalytics(SupportedUserMeta):  # noqa: R0903
    """Per-frame analytics from `nvdsanalytics`."""

    condition = _is_frameanalytics_meta
    klass = pyds.NvDsAnalyticsFrameMeta


class ObjectAnalytics(SupportedUserMeta):  # noqa: R0903
    """Per-object analytics from `nvdsanalytics`."""

    condition = _is_analytics_meta
    klass = pyds.NvDsAnalyticsObjInfo


class SemanticMasks(SupportedUserMeta):  # noqa: R0903
    """Per-object semantic segmentation masks from `nvinfer`."""

    condition = _is_segmentation_meta
    klass = pyds.NvDsInferSegmentationMeta
