from __future__ import annotations

from enum import Enum


class BorderState(str, Enum):
    INSIDE = "inside"
    BORDER = "border"
    OUTSIDE = "outside"


def bbox_inside(bbox_xyxy: list[float], area_xyxy: list[float]) -> bool:
    x1, y1, x2, y2 = bbox_xyxy
    ax1, ay1, ax2, ay2 = area_xyxy
    return x1 >= ax1 and y1 >= ay1 and x2 <= ax2 and y2 <= ay2


def bbox_outside(bbox_xyxy: list[float], area_xyxy: list[float]) -> bool:
    x1, y1, x2, y2 = bbox_xyxy
    ax1, ay1, ax2, ay2 = area_xyxy
    return x2 < ax1 or x1 > ax2 or y2 < ay1 or y1 > ay2


def _area(bbox_xyxy: list[float]) -> float:
    x1, y1, x2, y2 = bbox_xyxy
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _intersection_area(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    return inter_w * inter_h


def classify_bbox_state(
    bbox_xyxy: list[float],
    inner_xyxy: list[float],
    outer_xyxy: list[float],
    inner_ratio_min: float | None = None,
) -> BorderState:
    # Regla: si >= X% del bbox está dentro del inner, considerar INSIDE
    if inner_ratio_min is not None:
        area = _area(bbox_xyxy)
        if area > 0.0:
            inter = _intersection_area(bbox_xyxy, inner_xyxy)
            if (inter / area) >= inner_ratio_min:
                return BorderState.INSIDE

    if bbox_inside(bbox_xyxy, inner_xyxy):
        return BorderState.INSIDE
    if bbox_outside(bbox_xyxy, outer_xyxy):
        return BorderState.OUTSIDE
    return BorderState.BORDER
