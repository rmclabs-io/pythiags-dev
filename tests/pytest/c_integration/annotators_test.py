"""I want to have access to typical use case demos."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from py._path.local import LocalPath

from pythia import AnnotateFramesBase
from pythia import AnnotateFramesBbox
from pythia import AnnotateFramesMaskRcnn
from pythia.iterators import frames_per_batch
from pythia.iterators import objects_per_frame
from pythia.utils.gst import Gst
from pythia.utils.maskrcnn import polygon_to_bbox

from tests.paths import ANALYTICS
from tests.paths import DS_PATH
from tests.paths import DS_STREAMS
from tests.paths import TRACKER
from tests.utils import cleanup
from tests.utils import IS_JETSON
from tests.utils import roundup


def _iou(detection_a, detection_b):
    # determine the (x, y)-coordinates of the intersection rectangle
    inner_left = max(detection_a["left"], detection_b["left"])
    inner_top = max(detection_a["top"], detection_b["top"])
    inner_right = min(
        detection_a["left"] + detection_a["width"],
        detection_b["left"] + detection_b["width"],
    )
    inner_bottom = min(
        detection_a["top"] + detection_a["height"],
        detection_b["top"] + detection_b["height"],
    )
    # compute the area of intersection rectangle
    intersection = max(0, inner_right - inner_left + 1) * max(
        0, inner_bottom - inner_top + 1
    )
    if not intersection:
        return 0
    # compute the area of both the prediction and ground-truth
    # rectangles
    detection_a_area = (detection_a["width"] + 1) * (detection_a["height"] + 1)
    detection_b_area = (detection_b["width"] + 1) * (detection_b["height"] + 1)
    # compute the intersection over union by taking the intersection
    # area and dividing it by the sum of prediction + ground-truth
    # areas - the interesection area
    iou = intersection / float(
        detection_a_area + detection_b_area - intersection
    )
    # return the intersection over union value
    return iou


# fmt: off
EXPECTED_BBOX_GPU = [{'frame_num': 0, 'label': 'person', 'engine_id': 1, 'id': 1, 'engine': 'model_0', 'pad_index': 0, 'left': 64.81732177734375, 'top': 301.4888916015625, 'width': 73.27801513671875, 'height': 220.62628173828125, 'confidence': 0.904424786567688}, {'frame_num': 0, 'label': 'person', 'engine_id': 1, 'id': 1, 'engine': 'model_0', 'pad_index': 0, 'left': 288.8456726074219, 'top': 318.9028625488281, 'width': 18.09908103942871, 'height': 45.25007247924805, 'confidence': 0.9598023891448975}, {'frame_num': 0, 'label': 'person', 'engine_id': 1, 'id': 1, 'engine': 'model_0', 'pad_index': 0, 'left': 1.6682027578353882, 'top': 270.26806640625, 'width': 130.8496551513672, 'height': 398.8148498535156, 'confidence': 0.9893208742141724}, {'frame_num': 0, 'label': 'person', 'engine_id': 1, 'id': 1, 'engine': 'model_0', 'pad_index': 0, 'left': 198.725830078125, 'top': 307.57794189453125, 'width': 117.63912200927734, 'height': 265.9861755371094, 'confidence': 0.9998897314071655}]  # noqa: C0301
EXPECTED_BBOX_JETSON = [{'frame_num': 0, 'label': 'person', 'engine_id': 1, 'id': 1, 'engine': 'model_0', 'pad_index': 0, 'left': 306.3999938964844, 'top': 324.1902160644531, 'width': 18.40576171875, 'height': 46.07585906982422, 'confidence': 0.8086320161819458}, {'frame_num': 0, 'label': 'person', 'engine_id': 1, 'id': 1, 'engine': 'model_0', 'pad_index': 0, 'left': 0.1695607453584671, 'top': 267.9074401855469, 'width': 137.39837646484375, 'height': 406.4962463378906, 'confidence': 0.9789136648178101}, {'frame_num': 0, 'label': 'person', 'engine_id': 1, 'id': 1, 'engine': 'model_0', 'pad_index': 0, 'left': 288.3331604003906, 'top': 319.6286926269531, 'width': 17.49056053161621, 'height': 43.15187454223633, 'confidence': 0.983992338180542}, {'frame_num': 0, 'label': 'person', 'engine_id': 1, 'id': 1, 'engine': 'model_0', 'pad_index': 0, 'left': 198.9019012451172, 'top': 307.902099609375, 'width': 117.9039077758789, 'height': 260.23541259765625, 'confidence': 0.9998049736022949}]  # noqa: C0301
# fmt: on


def test_annotate_frames_bbox(
    tmpdir: LocalPath | Path,
    peoplesegnet: Path,
):  # noqa: DAR101
    """Check if the bounding box annotator is able to call the probe."""

    input_frame = Path(DS_STREAMS / "sample_720p.jpg")
    src = f"file://{input_frame}?muxer_width=1280&muxer_height=720"
    dst_folder = Path(tmpdir)

    expected = EXPECTED_BBOX_JETSON if IS_JETSON else EXPECTED_BBOX_GPU

    AnnotateFramesBbox.run(
        src=src,
        model=peoplesegnet,
        dst_folder=dst_folder,
    )
    received = [
        json.loads(line)
        for line in Path(dst_folder / "detections.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    received = [{k: v for k, v in d.items() if k != "id"} for d in received]
    expected = [{k: v for k, v in d.items() if k != "id"} for d in expected]
    assert roundup(received) == roundup(expected)
    output_frame = Path(tmpdir / f"frames/{'0'*12}.jpg")
    assert output_frame.exists, "Output frame expected but not found"


# fmt: off
EXPECTED_MASKRCNN_GPU = [{'frame_num': 0, 'label': 'person', 'engine': 'model_0', 'engine_id': 1, 'pad_index': 0, 'id': 1, 'left': 64.81732177734375, 'top': 301.4888916015625, 'width': 73.27801513671875, 'height': 220.62628173828125, 'confidence': 0.904424786567688, 'mask': [[8, 2, 8, 3, 4, 7, 4, 8, 3, 9, 3, 25, 4, 26, 4, 30, 5, 31, 5, 33, 6, 34, 6, 35, 8, 37, 8, 38, 12, 42, 12, 43, 13, 44, 13, 45, 15, 47, 15, 48, 16, 49, 16, 50, 17, 51, 17, 52, 18, 53, 18, 54, 19, 55, 19, 56, 20, 57, 20, 58, 21, 59, 21, 60, 22, 61, 22, 62, 23, 63, 23, 66, 24, 67, 24, 69, 25, 70, 25, 73, 26, 74, 26, 76, 27, 77, 27, 78, 28, 79, 28, 82, 29, 83, 29, 85, 30, 86, 30, 89, 31, 90, 31, 93, 32, 94, 32, 98, 33, 99, 33, 105, 34, 106, 34, 122, 35, 123, 35, 136, 36, 137, 36, 144, 37, 145, 37, 160, 38, 161, 38, 169, 39, 170, 39, 176, 40, 177, 40, 183, 41, 184, 41, 188, 42, 189, 42, 193, 43, 194, 43, 196, 44, 197, 44, 198, 45, 199, 45, 200, 46, 201, 46, 202, 48, 204, 48, 205, 49, 205, 50, 206, 51, 206, 52, 207, 53, 207, 54, 208, 62, 208, 63, 207, 63, 206, 64, 205, 63, 204, 63, 202, 62, 201, 62, 197, 61, 196, 61, 195, 60, 194, 60, 192, 59, 191, 59, 188, 58, 187, 58, 181, 57, 180, 57, 171, 56, 170, 56, 140, 57, 139, 57, 132, 58, 131, 58, 128, 59, 127, 59, 124, 60, 123, 60, 120, 61, 119, 61, 118, 62, 117, 62, 115, 63, 114, 63, 112, 64, 111, 64, 110, 65, 109, 65, 108, 66, 107, 66, 105, 67, 104, 67, 102, 68, 101, 68, 98, 69, 97, 69, 91, 70, 90, 70, 70, 69, 69, 69, 64, 68, 63, 68, 61, 67, 60, 67, 57, 66, 56, 66, 54, 65, 53, 65, 52, 64, 51, 64, 50, 63, 49, 63, 47, 62, 46, 62, 45, 61, 44, 61, 43, 59, 41, 59, 40, 58, 39, 58, 38, 57, 37, 57, 36, 56, 35, 56, 34, 54, 32, 54, 30, 53, 29, 53, 27, 52, 26, 52, 24, 51, 23, 51, 22, 50, 21, 50, 19, 49, 18, 49, 16, 48, 15, 48, 14, 47, 13, 47, 11, 42, 6, 41, 6, 40, 5, 39, 5, 38, 4, 25, 4, 24, 3, 18, 3, 17, 2, 12, 2, 11, 3, 9, 3]]}, {'frame_num': 0, 'label': 'person', 'engine': 'model_0', 'engine_id': 1, 'pad_index': 0, 'id': 1, 'left': 288.8456726074219, 'top': 318.9028625488281, 'width': 18.09908103942871, 'height': 45.25007247924805, 'confidence': 0.9598023891448975, 'mask': [[6, 0, 5, 1, 5, 5, 4, 6, 4, 7, 2, 9, 2, 10, 1, 11, 1, 13, 0, 14, 0, 21, 1, 22, 1, 25, 2, 26, 2, 28, 10, 36, 12, 36, 12, 35, 13, 34, 13, 33, 14, 32, 14, 31, 15, 30, 15, 29, 17, 27, 17, 25, 18, 24, 18, 14, 17, 13, 17, 11, 16, 10, 16, 9, 15, 8, 15, 7, 13, 5, 13, 4, 12, 3, 12, 1, 11, 0]]}, {'frame_num': 0, 'label': 'person', 'engine': 'model_0', 'engine_id': 1, 'pad_index': 0, 'id': 1, 'left': 1.6682027578353882, 'top': 270.26806640625, 'width': 130.8496551513672, 'height': 398.8148498535156, 'confidence': 0.9893208742141724, 'mask': [[23, 0, 23, 6, 22, 7, 22, 11, 21, 12, 21, 16, 20, 17, 20, 20, 19, 21, 19, 24, 18, 25, 18, 28, 17, 29, 17, 31, 16, 32, 16, 34, 15, 35, 15, 36, 14, 37, 14, 38, 8, 44, 8, 45, 5, 48, 5, 49, 3, 51, 3, 52, 2, 53, 2, 55, 1, 56, 1, 57, 0, 58, 0, 202, 1, 203, 1, 204, 2, 205, 2, 206, 4, 208, 4, 209, 5, 210, 5, 211, 6, 212, 6, 213, 8, 215, 9, 215, 11, 217, 11, 218, 13, 220, 13, 221, 14, 222, 14, 223, 15, 224, 15, 226, 16, 227, 16, 229, 17, 230, 17, 231, 18, 232, 18, 233, 19, 234, 19, 235, 21, 237, 21, 239, 22, 240, 22, 241, 23, 242, 23, 244, 24, 245, 24, 246, 25, 247, 25, 248, 26, 249, 26, 251, 27, 252, 27, 254, 28, 255, 28, 259, 29, 260, 29, 264, 30, 265, 30, 273, 31, 274, 31, 294, 30, 295, 30, 331, 31, 332, 31, 344, 32, 345, 32, 355, 33, 356, 33, 366, 34, 367, 34, 372, 35, 373, 35, 377, 36, 378, 36, 381, 37, 382, 37, 398, 56, 398, 56, 376, 57, 375, 57, 351, 58, 350, 58, 334, 59, 333, 59, 323, 60, 322, 60, 315, 61, 314, 61, 310, 62, 309, 62, 307, 63, 306, 63, 304, 64, 303, 64, 302, 66, 300, 70, 300, 71, 301, 71, 302, 72, 303, 72, 304, 73, 305, 73, 306, 74, 307, 74, 309, 75, 310, 75, 312, 76, 313, 76, 317, 77, 318, 77, 323, 78, 324, 78, 333, 79, 334, 79, 345, 80, 346, 80, 355, 81, 356, 81, 360, 82, 361, 82, 365, 83, 366, 83, 369, 84, 370, 84, 372, 85, 373, 85, 374, 86, 375, 86, 376, 87, 377, 87, 378, 88, 379, 88, 380, 92, 384, 92, 398, 109, 398, 109, 384, 113, 380, 113, 379, 114, 378, 114, 377, 115, 376, 115, 374, 116, 373, 116, 372, 117, 371, 117, 351, 116, 350, 116, 339, 115, 338, 115, 327, 114, 326, 114, 309, 113, 308, 113, 278, 112, 277, 112, 264, 111, 263, 111, 253, 110, 252, 110, 244, 109, 243, 109, 231, 108, 230, 108, 225, 107, 224, 107, 216, 106, 215, 106, 206, 105, 205, 105, 200, 104, 199, 104, 196, 103, 195, 103, 193, 102, 192, 102, 181, 101, 180, 101, 167, 102, 166, 102, 159, 103, 158, 103, 155, 102, 154, 102, 146, 101, 145, 101, 140, 100, 139, 100, 136, 99, 135, 99, 131, 98, 130, 98, 126, 97, 125, 97, 121, 96, 120, 96, 118, 95, 117, 95, 115, 94, 114, 94, 112, 93, 111, 93, 109, 92, 108, 92, 105, 91, 104, 91, 102, 90, 101, 90, 99, 89, 98, 89, 96, 88, 95, 88, 93, 87, 92, 87, 90, 86, 89, 86, 88, 85, 87, 85, 85, 84, 84, 84, 82, 83, 81, 83, 78, 82, 77, 82, 76, 81, 75, 81, 74, 79, 72, 79, 71, 78, 70, 78, 67, 77, 66, 77, 64, 76, 63, 76, 62, 73, 59, 73, 58, 72, 58, 71, 57, 71, 56, 70, 55, 70, 54, 69, 53, 69, 51, 68, 50, 68, 49, 67, 48, 67, 47, 66, 46, 66, 45, 65, 44, 65, 43, 64, 42, 64, 38, 63, 37, 63, 31, 62, 30, 62, 13, 61, 12, 61, 5, 60, 4, 60, 0]]}, {'frame_num': 0, 'label': 'person', 'engine': 'model_0', 'engine_id': 1, 'pad_index': 0, 'id': 1, 'left': 198.725830078125, 'top': 307.57794189453125, 'width': 117.63912200927734, 'height': 265.9861755371094, 'confidence': 0.9998897314071655, 'mask': [[36, 0, 36, 1, 35, 2, 35, 3, 34, 4, 34, 6, 33, 7, 33, 9, 32, 10, 32, 11, 31, 12, 31, 14, 30, 15, 30, 16, 29, 17, 29, 19, 25, 23, 25, 24, 23, 26, 23, 27, 16, 34, 16, 35, 13, 38, 13, 39, 12, 40, 12, 41, 10, 43, 10, 44, 7, 47, 7, 49, 6, 50, 6, 51, 5, 52, 5, 53, 4, 54, 4, 56, 3, 57, 3, 60, 2, 61, 2, 64, 1, 65, 1, 67, 0, 68, 0, 123, 2, 125, 2, 126, 4, 128, 4, 129, 7, 129, 8, 130, 9, 130, 10, 129, 11, 129, 15, 125, 16, 125, 17, 124, 19, 124, 20, 125, 21, 125, 24, 128, 24, 129, 27, 132, 27, 133, 32, 138, 32, 139, 34, 141, 34, 142, 35, 143, 35, 144, 36, 145, 36, 146, 37, 147, 37, 149, 38, 150, 38, 152, 39, 153, 39, 155, 40, 156, 40, 159, 41, 160, 41, 163, 42, 164, 42, 167, 43, 168, 43, 170, 44, 171, 44, 173, 45, 174, 45, 175, 46, 176, 46, 177, 47, 178, 47, 180, 48, 181, 48, 182, 49, 183, 49, 184, 50, 185, 50, 186, 51, 187, 51, 188, 53, 190, 53, 191, 54, 192, 54, 193, 55, 194, 55, 195, 56, 196, 56, 198, 57, 199, 57, 201, 58, 202, 58, 204, 59, 205, 59, 208, 60, 209, 60, 215, 61, 216, 61, 226, 62, 227, 62, 248, 63, 249, 63, 253, 64, 254, 64, 256, 65, 257, 65, 265, 81, 265, 81, 255, 82, 254, 82, 251, 83, 250, 83, 243, 82, 242, 82, 237, 81, 236, 81, 230, 80, 229, 80, 210, 81, 209, 81, 200, 82, 199, 82, 193, 83, 192, 83, 188, 84, 187, 84, 183, 85, 182, 85, 178, 86, 177, 86, 174, 87, 173, 87, 168, 88, 167, 88, 157, 89, 156, 89, 129, 88, 128, 88, 95, 89, 94, 89, 93, 90, 92, 90, 91, 91, 90, 92, 90, 93, 89, 94, 90, 95, 90, 96, 91, 97, 91, 101, 95, 102, 95, 103, 96, 104, 96, 105, 97, 110, 97, 111, 96, 112, 96, 113, 95, 113, 92, 114, 91, 117, 91, 117, 84, 114, 84, 113, 83, 113, 80, 112, 79, 112, 75, 111, 74, 111, 73, 110, 72, 110, 70, 109, 69, 109, 67, 108, 66, 108, 65, 107, 64, 107, 63, 106, 62, 106, 61, 105, 60, 105, 59, 103, 57, 103, 56, 100, 53, 100, 52, 96, 48, 96, 47, 91, 42, 91, 41, 79, 29, 78, 29, 68, 19, 68, 18, 67, 17, 67, 16, 66, 15, 66, 14, 64, 12, 64, 11, 62, 9, 62, 7, 61, 6, 61, 5, 60, 4, 60, 3, 58, 1, 58, 0]]}]  # noqa: C0301  # noqa: C0301
EXPECTED_MASKRCNN_JETSON = [{'frame_num': 0, 'label': 'person', 'engine': 'model_0', 'engine_id': 1, 'pad_index': 0, 'id': 1, 'left': 306.3999938964844, 'top': 324.1902160644531, 'width': 18.40576171875, 'height': 46.07585906982422, 'confidence': 0.8086320161819458, 'mask': [[5, 0, 4, 1, 4, 2, 3, 3, 3, 4, 2, 5, 2, 23, 3, 24, 3, 27, 4, 28, 4, 30, 5, 31, 5, 33, 6, 34, 6, 38, 7, 39, 7, 42, 9, 44, 10, 44, 12, 42, 12, 40, 13, 39, 13, 33, 14, 32, 14, 28, 15, 27, 15, 11, 14, 10, 14, 7, 13, 6, 13, 4, 12, 3, 12, 2, 10, 0]]}, {'frame_num': 0, 'label': 'person', 'engine': 'model_0', 'engine_id': 1, 'pad_index': 0, 'id': 1, 'left': 0.1695607453584671, 'top': 267.9074401855469, 'width': 137.39837646484375, 'height': 406.4962463378906, 'confidence': 0.9789136648178101, 'mask': [[112, 88, 111, 89, 109, 89, 109, 93, 108, 94, 108, 100, 107, 101, 107, 104, 108, 105, 108, 111, 109, 111, 109, 110, 111, 108, 111, 107, 113, 105, 113, 104, 114, 103, 114, 94, 113, 93, 113, 88], [127, 86, 126, 87, 125, 87, 124, 88, 124, 90, 125, 91, 125, 118, 126, 119, 126, 126, 127, 127, 127, 130, 128, 131, 128, 128, 129, 127, 129, 123, 130, 122, 130, 119, 131, 118, 131, 101, 130, 100, 130, 97, 129, 96, 129, 90, 128, 89, 128, 86], [25, 0, 25, 2, 24, 3, 24, 8, 23, 9, 23, 13, 22, 14, 22, 18, 21, 19, 21, 23, 20, 24, 20, 27, 19, 28, 19, 30, 18, 31, 18, 34, 17, 35, 17, 37, 16, 38, 16, 39, 14, 41, 14, 42, 12, 44, 12, 46, 11, 47, 11, 48, 9, 50, 9, 51, 8, 52, 8, 53, 6, 55, 6, 56, 5, 57, 5, 58, 4, 59, 4, 61, 3, 62, 3, 63, 2, 64, 2, 66, 1, 67, 1, 68, 0, 69, 0, 202, 1, 203, 1, 204, 2, 205, 2, 206, 3, 207, 3, 208, 4, 209, 4, 211, 5, 212, 5, 213, 6, 214, 6, 215, 8, 217, 8, 218, 9, 219, 10, 219, 11, 220, 11, 221, 14, 224, 14, 225, 16, 227, 16, 228, 17, 229, 17, 231, 18, 232, 18, 233, 19, 234, 19, 235, 20, 236, 20, 237, 22, 239, 22, 241, 23, 242, 23, 243, 24, 244, 24, 245, 25, 246, 25, 248, 26, 249, 26, 250, 27, 251, 27, 253, 28, 254, 28, 256, 29, 257, 29, 259, 30, 260, 30, 264, 31, 265, 31, 271, 32, 272, 32, 333, 33, 334, 33, 344, 34, 345, 34, 356, 35, 357, 35, 374, 36, 375, 36, 384, 37, 385, 37, 392, 38, 393, 38, 406, 59, 406, 59, 346, 60, 345, 60, 332, 61, 331, 61, 323, 62, 322, 62, 317, 63, 316, 63, 312, 64, 311, 64, 309, 65, 308, 65, 307, 66, 306, 66, 305, 67, 304, 67, 303, 68, 302, 68, 301, 69, 300, 70, 301, 70, 302, 74, 306, 74, 307, 75, 308, 75, 311, 76, 312, 76, 315, 77, 316, 77, 320, 78, 321, 78, 327, 79, 328, 79, 335, 80, 336, 80, 349, 81, 350, 81, 356, 82, 357, 82, 364, 83, 365, 83, 368, 84, 369, 84, 373, 85, 374, 85, 376, 86, 377, 86, 379, 87, 380, 87, 381, 88, 382, 88, 383, 89, 384, 89, 385, 93, 389, 93, 390, 94, 391, 95, 391, 96, 392, 97, 392, 98, 393, 98, 406, 104, 406, 104, 393, 107, 390, 108, 390, 109, 389, 110, 389, 112, 387, 113, 387, 114, 386, 114, 385, 117, 382, 117, 381, 120, 378, 120, 371, 121, 370, 121, 360, 120, 359, 120, 354, 119, 353, 119, 347, 118, 346, 118, 339, 117, 338, 117, 330, 116, 329, 116, 317, 115, 316, 115, 299, 114, 298, 114, 272, 113, 271, 113, 258, 112, 257, 112, 239, 113, 238, 113, 234, 114, 233, 114, 226, 115, 225, 115, 202, 116, 201, 116, 141, 115, 140, 115, 137, 114, 136, 114, 135, 113, 134, 113, 133, 110, 130, 110, 126, 109, 125, 109, 122, 108, 121, 108, 120, 107, 119, 106, 119, 105, 118, 104, 118, 102, 116, 102, 113, 101, 112, 101, 111, 100, 110, 100, 109, 99, 108, 99, 107, 98, 106, 98, 104, 97, 103, 97, 99, 96, 98, 96, 96, 95, 95, 95, 94, 94, 93, 94, 92, 93, 91, 93, 89, 92, 88, 92, 86, 91, 85, 91, 80, 90, 79, 90, 77, 89, 76, 89, 75, 87, 73, 87, 72, 86, 71, 86, 69, 84, 67, 84, 66, 83, 65, 83, 63, 82, 62, 82, 61, 81, 60, 81, 59, 80, 59, 79, 58, 79, 57, 78, 56, 78, 55, 76, 53, 76, 52, 72, 48, 72, 47, 71, 47, 66, 42, 66, 41, 65, 40, 65, 37, 64, 36, 64, 31, 63, 30, 63, 14, 62, 13, 62, 9, 61, 8, 61, 3, 60, 2, 60, 0]]}, {'frame_num': 0, 'label': 'person', 'engine': 'model_0', 'engine_id': 1, 'pad_index': 0, 'id': 1, 'left': 288.3331604003906, 'top': 319.6286926269531, 'width': 17.49056053161621, 'height': 43.15187454223633, 'confidence': 0.983992338180542, 'mask': [[6, 0, 6, 1, 5, 2, 5, 4, 3, 6, 3, 7, 2, 8, 2, 10, 1, 11, 1, 22, 2, 23, 2, 25, 3, 26, 3, 27, 5, 29, 5, 30, 7, 32, 7, 33, 9, 35, 9, 36, 10, 37, 10, 38, 11, 39, 12, 39, 13, 38, 13, 34, 14, 33, 14, 31, 15, 30, 15, 29, 16, 28, 16, 25, 17, 24, 17, 13, 16, 12, 16, 9, 15, 8, 15, 7, 13, 5, 13, 4, 12, 3, 12, 2, 11, 1, 11, 0]]}, {'frame_num': 0, 'label': 'person', 'engine': 'model_0', 'engine_id': 1, 'pad_index': 0, 'id': 1, 'left': 198.9019012451172, 'top': 307.902099609375, 'width': 117.9039077758789, 'height': 260.23541259765625, 'confidence': 0.9998049736022949, 'mask': [[37, 0, 36, 1, 36, 2, 34, 4, 34, 6, 33, 7, 33, 9, 32, 10, 32, 11, 31, 12, 31, 13, 30, 14, 30, 15, 29, 16, 29, 17, 28, 18, 28, 19, 24, 23, 24, 24, 22, 26, 22, 27, 16, 33, 16, 34, 13, 37, 13, 38, 12, 39, 12, 40, 10, 42, 10, 43, 8, 45, 8, 46, 7, 47, 7, 48, 6, 49, 6, 50, 5, 51, 5, 52, 4, 53, 4, 55, 3, 56, 3, 59, 2, 60, 2, 63, 1, 64, 1, 67, 0, 68, 0, 123, 2, 125, 2, 126, 3, 127, 3, 128, 4, 129, 4, 130, 5, 130, 6, 131, 11, 131, 12, 130, 13, 130, 17, 126, 18, 127, 20, 127, 32, 139, 32, 140, 35, 143, 35, 144, 36, 145, 36, 147, 37, 148, 37, 149, 38, 150, 38, 152, 39, 153, 39, 156, 40, 157, 40, 160, 41, 161, 41, 164, 42, 165, 42, 168, 43, 169, 43, 171, 44, 172, 44, 174, 45, 175, 45, 177, 46, 178, 46, 179, 48, 181, 48, 182, 49, 183, 49, 184, 50, 185, 50, 187, 52, 189, 52, 190, 54, 192, 54, 193, 55, 194, 55, 195, 56, 196, 56, 198, 57, 199, 57, 200, 58, 201, 58, 203, 59, 204, 59, 206, 60, 207, 60, 212, 61, 213, 61, 244, 62, 245, 62, 260, 83, 260, 83, 250, 82, 249, 82, 241, 81, 240, 81, 235, 80, 234, 80, 204, 81, 203, 81, 196, 82, 195, 82, 190, 83, 189, 83, 184, 84, 183, 84, 179, 85, 178, 85, 173, 86, 172, 86, 168, 87, 167, 87, 160, 88, 159, 88, 113, 87, 112, 87, 93, 88, 92, 88, 90, 89, 89, 90, 89, 91, 88, 93, 88, 96, 91, 97, 91, 98, 92, 98, 93, 99, 93, 102, 96, 103, 96, 105, 98, 107, 98, 108, 99, 109, 99, 111, 97, 111, 96, 113, 94, 113, 83, 112, 82, 112, 79, 111, 78, 111, 75, 110, 74, 110, 72, 109, 71, 109, 70, 108, 69, 108, 67, 107, 66, 107, 65, 106, 64, 106, 63, 105, 62, 105, 61, 104, 60, 104, 59, 102, 57, 102, 56, 100, 54, 100, 53, 99, 52, 99, 51, 95, 47, 95, 46, 92, 43, 92, 42, 79, 29, 78, 29, 68, 19, 68, 18, 66, 16, 66, 15, 65, 14, 65, 13, 62, 10, 62, 9, 61, 8, 61, 7, 59, 5, 59, 4, 57, 2, 57, 1, 56, 1, 55, 0]]}]  # noqa: C0301
# fmt: on


def test_annotate_frames_mask_rcnn(
    tmpdir: LocalPath | Path,
    peoplesegnet: Path,
):  # noqa: DAR101
    """Check if the maskrcnn annotator is able to call the probe."""

    input_frame = Path(DS_STREAMS / "sample_720p.jpg")
    src = f"file://{input_frame}?muxer_width=1280&muxer_height=720"
    dst_folder = Path(tmpdir)

    expected = EXPECTED_MASKRCNN_JETSON if IS_JETSON else EXPECTED_MASKRCNN_GPU
    AnnotateFramesMaskRcnn.run(
        src=src,
        model=peoplesegnet,
        dst_folder=dst_folder,
    )
    received = [
        json.loads(line)
        for line in Path(dst_folder / "detections.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    output_frame = Path(tmpdir / f"frames/{'0'*12}.jpg")
    received = [{k: v for k, v in d.items() if k != "id"} for d in received]
    expected = [{k: v for k, v in d.items() if k != "id"} for d in expected]
    assert roundup(received) == roundup(expected)
    assert output_frame.exists, "Output frame expected but not found"

    for detection in received:
        masks_bbox = polygon_to_bbox(
            detection["mask"], detection["top"], detection["left"]
        )
        iou = _iou(detection, masks_bbox)
        assert iou > 0.7, "intersection between bbox mask(bbox) too low"


# fmt: off
EXPECTED_BASE_GPU = [{0: [{"person": 0.9044251441955566}, {"person": 0.9598023891448975}, {"person": 0.9893208742141724}, {"person": 0.9998897314071655}]}]  # noqa: C0301
EXPECTED_BASE_JETSON = [{0: [{'person': 0.8086320161819458}, {'person': 0.9789136648178101}, {'person': 0.983992338180542}, {'person': 0.9998049736022949}]}]  # noqa: C0301
# fmt: on


@pytest.mark.usefixtures("_nvidia_cooldown")
def test_annotate_frames_base(
    tmpdir: LocalPath | Path,
    peoplesegnet: Path,
):
    """Check if the base annotator is able to call the probe."""  # noqa: DAR101,C0301

    input_frame = Path(DS_STREAMS / "sample_720p.jpg")
    src = f"file://{input_frame}?muxer_width=1280&muxer_height=720"
    dst_folder = Path(tmpdir)

    expected = EXPECTED_BASE_JETSON if IS_JETSON else EXPECTED_BASE_GPU
    received = []

    def probe(batch_meta) -> Gst.PadProbeReturn:
        for frame in frames_per_batch(batch_meta):
            received.append(
                {
                    frame.frame_num: [
                        {o.obj_label: o.confidence}
                        for o in objects_per_frame(frame)
                    ]
                }
            )
        return Gst.PadProbeReturn.OK

    AnnotateFramesBase.run_with_probe(
        src=src,
        model=peoplesegnet,
        dst_folder=dst_folder,
        probe=probe,
    )
    assert roundup(received) == roundup(expected)
    output_frame = Path(tmpdir / f"frames/{'0'*12}.jpg")
    assert output_frame.exists, "Output frame expected but not found"


TRACKED_PIPELINE = """
uridecodebin
  uri=file://{input_frame}
! queue
! nvvideoconvert
! video/x-raw(memory:NVMM)
! m.sink_0
nvstreammux
  name=m
  batch-size=1
  width=1280
  height=720
! nvinfer
  config-file-path={pgie_conf}
  name=model_0
  unique-id=1
! nvtracker
  ll-config-file={tracker}
  ll-lib-file={tracker_llib}
{analytics}
! nvvideoconvert
! jpegenc
  quality=100
  idct-method=float
! multifilesink
  location="{location}"
"""


def test_tracker_support(tmpdir: LocalPath | Path, peoplesegnet: Path):
    """Ensure annotators work with tracker."""  # noqa: DAR101,C0301

    input_frame = Path(DS_STREAMS / "sample_720p.jpg")
    src = f"file://{input_frame}?muxer_width=1280&muxer_height=720"
    dst_folder = Path(tmpdir)

    expected_pipeline = TRACKED_PIPELINE.format(
        input_frame=input_frame,
        pgie_conf=peoplesegnet.resolve() / "pgie.conf",
        tracker=TRACKER.resolve(),
        tracker_llib=DS_PATH.resolve() / "lib/libnvds_nvmultiobjecttracker.so",
        DS_PATH=DS_PATH.resolve(),
        location=dst_folder / "frames/%012d.jpg",
        analytics="",
    )

    class _AppUnderTest(AnnotateFramesMaskRcnn):
        def __call__(self, *a, **kw):
            assert cleanup(self.pipeline.gst()) == cleanup(expected_pipeline)

    _AppUnderTest.run(
        src=src,
        model=peoplesegnet,
        dst_folder=dst_folder,
        tracker=TRACKER,
    )


def test_analytics_support(tmpdir: LocalPath | Path, peoplesegnet: Path):
    """Ensure annotators work with tracker."""  # noqa: DAR101,C0301

    input_frame = Path(DS_STREAMS / "sample_720p.mp4")
    src = f"file://{input_frame}?muxer_width=1280&muxer_height=720"
    dst_folder = Path(tmpdir)

    analytics = f"nvdsanalytics config-file={ANALYTICS}"
    expected_pipeline = TRACKED_PIPELINE.format(
        input_frame=input_frame,
        pgie_conf=peoplesegnet.resolve() / "pgie.conf",
        tracker=TRACKER.resolve(),
        tracker_llib=DS_PATH.resolve() / "lib/libnvds_nvmultiobjecttracker.so",
        DS_PATH=DS_PATH.resolve(),
        location=dst_folder / "frames/%012d.jpg",
        analytics=f"! {analytics}",
    )

    buffers = 0

    class _AppUnderTest(AnnotateFramesMaskRcnn):
        def __call__(self, *a, **kw):
            assert cleanup(self.pipeline.gst()) == cleanup(expected_pipeline)
            super().__call__(*a, **kw)

        def annotator_probe(self, pad, info, batch_meta):
            nonlocal buffers
            buffers += 1
            if buffers > 3:
                self.loop.quit()
            return super().annotator_probe(pad, info, batch_meta)

    _AppUnderTest.run(
        src=src,
        model=peoplesegnet,
        dst_folder=dst_folder,
        tracker=TRACKER,
        analytics=ANALYTICS,
    )
    assert any(
        json.loads(line)
        .get("analytics", {"roiStatus": None})
        .get("roiStatus", None)
        == ["RF"]
        for line in (dst_folder / "detections.jsonl").read_text().splitlines()
    ), "No roi ever populated!"
