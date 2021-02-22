"""Model definitions."""

from typing import Any
from typing import List
from typing import NamedTuple
from typing import Union

Event = Any
Events = List[Event]


class Bbox(NamedTuple):
    """Bounding Box, with coordinates instead of start and length."""

    x_min: int
    y_min: int
    x_max: int
    y_max: int


class Detection(NamedTuple):
    """Detection information extracted from deeptream metadata."""

    frame_num: int
    source_id: str
    label: str
    detector_bbox: Bbox
    tracker_bbox: Bbox
    confidence: Union[float, str]
    object_id: int


class Classification(NamedTuple):
    """Classification information extracted from deeptream metadata."""

    class_id: int
    prob: float


class TrackerShadow(NamedTuple):
    """Past frame shadow information extracted from deeptream metadata."""

    frame_num: int
    past_frame_num: int
    label: str
    bbox: Bbox
    confidence: Union[float, str]
    age: int
    object_id: int


Detections = List[Detection]
TrackerList = List[TrackerShadow]
