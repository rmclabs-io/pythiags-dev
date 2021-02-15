from typing import Any
from typing import List
from typing import NamedTuple
from typing import Union

Event = Any
Events = List[Event]


class Bbox(NamedTuple):
    x_min: int
    y_min: int
    x_max: int
    y_max: int


class Detection(NamedTuple):
    frame_num: int
    source_id: str
    label: str
    detector_bbox: Bbox
    tracker_bbox: Bbox
    confidence: Union[float, str]
    object_id: int
    # classifier_results: str  # Json from Classification


class Classification(NamedTuple):
    class_id: int
    prob: float


class TrackerShadow(NamedTuple):
    frame_num: int
    past_frame_num: int
    label: str
    bbox: Bbox
    confidence: Union[float, str]
    age: int
    object_id: int


Detections = List[Detection]
TrackerList = List[TrackerShadow]
