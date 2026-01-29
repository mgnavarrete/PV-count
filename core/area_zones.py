from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AreaZones:
    inner_xyxy: list[float]
    outer_xyxy: list[float]


def _clamp(val: float, min_v: float, max_v: float) -> float:
    return max(min_v, min(max_v, val))


def make_inner_outer(
    bbox_xyxy: list[float],
    image_size: tuple[int, int],
    shrink_px: int = 12,
    expand_px: int = 0,
) -> AreaZones:
    x1, y1, x2, y2 = bbox_xyxy
    img_w, img_h = image_size

    # Inner (shrink)
    ix1 = _clamp(x1 + shrink_px, 0, img_w - 1)
    iy1 = _clamp(y1 + shrink_px, 0, img_h - 1)
    ix2 = _clamp(x2 - shrink_px, 0, img_w - 1)
    iy2 = _clamp(y2 - shrink_px, 0, img_h - 1)
    if ix2 < ix1:
        ix1, ix2 = ix2, ix1
    if iy2 < iy1:
        iy1, iy2 = iy2, iy1

    # Outer (expand)
    ox1 = _clamp(x1 - expand_px, 0, img_w - 1)
    oy1 = _clamp(y1 - expand_px, 0, img_h - 1)
    ox2 = _clamp(x2 + expand_px, 0, img_w - 1)
    oy2 = _clamp(y2 + expand_px, 0, img_h - 1)

    return AreaZones(
        inner_xyxy=[float(ix1), float(iy1), float(ix2), float(iy2)],
        outer_xyxy=[float(ox1), float(oy1), float(ox2), float(oy2)],
    )
