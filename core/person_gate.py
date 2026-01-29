from __future__ import annotations

from typing import Iterable


def _bbox_inside(bbox: list[float], box: list[float]) -> bool:
    x1, y1, x2, y2 = bbox
    ax1, ay1, ax2, ay2 = box
    return x1 >= ax1 and y1 >= ay1 and x2 <= ax2 and y2 <= ay2


def _bbox_intersects(a: list[float], b: list[float]) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    return inter_x2 > inter_x1 and inter_y2 > inter_y1


def person_near_border(
    detections: Iterable[dict],
    inner_xyxy: list[float],
    outer_xyxy: list[float],
    conf_min: float = 0.25,
    dist_px: float = 20.0,
) -> tuple[bool, list[list[float]]]:
    """
    Retorna (is_near, person_boxes). "Near" si:
      - el bbox intersecta el outer, y
      - NO está completamente dentro del inner, o si está dentro pero su borde está a <= dist_px del inner.
    """
    persons: list[list[float]] = []
    ix1, iy1, ix2, iy2 = inner_xyxy
    for det in detections:
        if det.get("class_name") != "persona":
            continue
        if det.get("conf", 0.0) < conf_min:
            continue
        bbox = list(det.get("bbox_xyxy", [0, 0, 0, 0]))
        persons.append(bbox)
        if not _bbox_intersects(bbox, outer_xyxy):
            continue
        if not _bbox_inside(bbox, inner_xyxy):
            return True, persons
        # Bbox dentro del inner: evaluar distancia del borde del bbox al borde interno
        x1, y1, x2, y2 = bbox
        dist_edge = min(x1 - ix1, ix2 - x2, y1 - iy1, iy2 - y2)
        if dist_edge <= dist_px:
            return True, persons

    return False, persons
