"""Utilities to convert strings to pythia wrappers."""

from __future__ import annotations

from pythia.models.base import Analytics
from pythia.models.base import InferenceEngine
from pythia.models.base import Tracker
from pythia.utils.gst import Gst
from pythia.utils.gst import gst_iter


def is_inference(element: Gst.Element) -> bool:
    """Check wether a `Gst.Element` is a `nvinfer`.

    Args:
        element: the gstreamer element to check.

    Returns:
        `True` iff the element is a `nvinfer`. False otherwise.

    """
    return "nvinfer" in element.__class__.__name__.lower()


def is_tracker(element: Gst.Element) -> bool:
    """Check wether a `Gst.Element` is a `nvtracker`.

    Args:
        element: the gstreamer element to check.

    Returns:
        `True` iff the element is a `nvtracker`. False otherwise.

    """
    return "nvtracker" in element.__class__.__name__.lower()


def is_analytics(element: Gst.Element) -> bool:
    """Check wether a `Gst.Element` is a `nvdsanalytics`.

    Args:
        element: the gstreamer element to check.

    Returns:
        `True` iff the element is a `nvdsanalytics`. False otherwise.

    """
    return "nvdsanalytics" in element.__class__.__name__.lower()


def find_models(pipeline: Gst.Pipeline) -> list[InferenceEngine]:
    """Extract `nvifer` s from parsed pipeline.

    Args:
        pipeline: The root bin where to look for ninfer elements.

    Returns:
        List of all the nvinfer wrappers wrapped as
            :class:`InferenceEngine`.

    """
    return [
        InferenceEngine.from_element(element)
        for element in gst_iter(pipeline.iterate_elements())
        if is_inference(element)
    ]


def find_analytics(pipeline: Gst.Pipeline) -> Analytics | None:
    """Extract analytics from parsed pipeline.

    Args:
        pipeline: The root bin where to look for `nvdsanalytics`
            elements.

    Returns:
        First `nvdsanalytics` found, wrapped as :class:`Analytics`.

    """
    for element in gst_iter(pipeline.iterate_elements()):
        if is_analytics(element):
            return Analytics.from_element(element)
    return None


def find_tracker(pipeline: Gst.Pipeline) -> Tracker | None:
    """Extract tracker from parsed pipeline.

    Args:
        pipeline: The root bin where to look for `nvtracker` elements.

    Returns:
        First `nvtracker` found, wrapped as :class:`Tracker`.

    """

    for element in gst_iter(pipeline.iterate_elements()):
        if is_tracker(element):
            return Tracker.from_element(element)

    return None
