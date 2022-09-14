"""Simple python MASKRCNN output parser.

The function `extract_maskrcnn_mask` should be used.

The core function, `resize_mask_vec`, is based on its cpp counterpart
`resizeMask`, from deepstream cpp sources. It was ported to python
and vectorized via numpy to improve speed.

Author: <Pablo Woolvett pablowoolvett@gmail.com>

"""

from typing import List
from typing import Tuple
from typing import TypedDict

import numpy as np
import pyds

from pythia.utils.ext import grouped


def _gen_ranges(
    original_height: int,
    original_width: int,
    target_height: int,
    target_width: int,
) -> Tuple[np.ndarray, np.ndarray]:
    ratio_h = float(original_height / target_height)
    ratio_w = float(original_width / target_width)

    height = np.arange(0, original_height, ratio_h)
    width = np.arange(0, original_width, ratio_w)
    return height, width


def _gen_clips(
    width: np.ndarray,
    original_width: int,
    height: np.ndarray,
    original_height: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:

    left = np.clip(np.floor(width), 0.0, original_width - 1)
    right = np.clip(np.ceil(width), 0.0, original_width - 1)
    top = np.clip(np.floor(height), 0.0, original_height - 1)
    bottom = np.clip(np.ceil(height), 0.0, original_height - 1)
    return left, right, top, bottom


def _gen_idxs(
    original_width: int,
    left: np.ndarray,
    right: np.ndarray,
    top: np.ndarray,
    bottom: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:

    left_top_idx = np.add.outer(top * original_width, left).astype(int)
    right_top_idx = np.add.outer(top * original_width, right).astype(int)
    left_bottom_idx = np.add.outer(bottom * original_width, left).astype(int)
    right_bottom_idx = np.add.outer(bottom * original_width, right).astype(int)

    return left_top_idx, right_top_idx, left_bottom_idx, right_bottom_idx


def _take_vals(
    src,
    *idxmats,
):
    return tuple(src.take(idxmat) for idxmat in idxmats)


def _interpolate(  # noqa: R0913
    width: np.ndarray,
    left: np.ndarray,
    height: np.ndarray,
    top: np.ndarray,
    left_top_val: np.ndarray,
    right_top_val: np.ndarray,
    left_bottom_val: np.ndarray,
    right_bottom_val: np.ndarray,
) -> np.ndarray:
    delta_w = width - left
    top_lerp = left_top_val + (right_top_val - left_top_val) * delta_w
    bottom_lerp = (
        left_bottom_val + (right_bottom_val - left_bottom_val) * delta_w
    )
    return top_lerp + ((bottom_lerp - top_lerp).T * (height - top)).T


def resize_mask_vec(  # noqa: R0914
    src: np.ndarray,
    src_shape: Tuple[int, int],
    target_shape: Tuple[int, int],
    threshold: float,
) -> np.ndarray:
    """Resize mask from original deepstream object into numpy array.

    Args:
        src: Mask array from deepstream object.
        src_shape: Shape of the original mask in (height,width) format.
        target_shape: Shape of the target mask in (height,width) format.
        threshold: Threshold for the mask.

    Returns:
        A 2d binary mask of np.uint8 valued 0 and 255.

    See Also:
        * `extract_maskrcnn_mask` in this module for sample usage from
            deepstream.
        * `resizeMask` function at
            `sample_apps/deepstream-mrcnn-app/deepstream_mrcnn_test.cpp`

    """

    original_height, original_width = src_shape
    target_height, target_width = target_shape

    height, width = _gen_ranges(
        original_height,
        original_width,
        target_height,
        target_width,
    )

    left, right, top, bottom = _gen_clips(
        width,
        original_width,
        height,
        original_height,
    )

    left_top_idx, right_top_idx, left_bottom_idx, right_bottom_idx = _gen_idxs(
        original_width,
        left,
        right,
        top,
        bottom,
    )

    (
        left_top_val,
        right_top_val,
        left_bottom_val,
        right_bottom_val,
    ) = _take_vals(
        src,
        left_top_idx,
        right_top_idx,
        left_bottom_idx,
        right_bottom_idx,
    )

    lerp = _interpolate(
        width,
        left,
        height,
        top,
        left_top_val,
        right_top_val,
        left_bottom_val,
        right_bottom_val,
    )

    ret = np.zeros_like(lerp, dtype=np.uint8)
    ret[lerp >= threshold] = 255
    return ret


def extract_maskrcnn_mask(obj_meta: pyds.NvDsObjectMeta) -> np.ndarray:
    """Extract maskrcnn mask from deepstream object.

    Args:
        obj_meta: Deepstream object meta from detection.

    Returns:
        A 2d binary mask of np.uint8 valued 0 and 255.

    Example:
        >>> obj_meta = pyds.NvDsObjectMeta.cast(...)
        >>> mask = extract_maskrcnn_mask(obj_meta)
        >>> mask.shape, mask.dtype
        ((300,100), dtype('uint8'))

    See Also:
        `resize_mask_vec` for the internal implementation.

    """
    rect_height = int(np.ceil(obj_meta.rect_params.height))
    rect_width = int(np.ceil(obj_meta.rect_params.width))
    return resize_mask_vec(
        obj_meta.mask_params.data,
        (obj_meta.mask_params.height, obj_meta.mask_params.width),
        (rect_height, rect_width),
        obj_meta.mask_params.threshold,
    )


class DsBBox(TypedDict):
    """Deepstream-style Bounding box."""

    top: float
    height: float
    width: float
    left: float


def polygon_to_bbox(
    polygons: List[List[int]],
    top: float,
    left: float,
) -> DsBBox:
    """Generate bounding box from polygons.

    The polygons are assumed to be relative to a mask.

    Args:
        polygons: collection of polygons, where each polygon is a
            sequence of the form 'y0,x0,y1,x1,...,yn,xn'.
        top: top offset from the mask.
        left: left offset from the mask.

    Returns:
        Bounding box which circumscribes the mask.

    """
    x_max = 0
    y_max = 0
    x_min = 0
    y_min = 0
    for polygon in polygons:
        coords = np.array(list(grouped(polygon, 2)))
        y_max_, x_max_ = coords.max(0)
        y_min_, x_min_ = coords.min(0)
        x_max = max(x_max, x_max_)
        y_max = max(y_max, y_max_)
        x_min = min(x_min, x_min_)
        y_min = min(y_min, y_min_)
    return {
        "top": top + y_min,
        "left": left + x_min,
        "height": x_max - x_min,
        "width": y_max - y_min,
    }
