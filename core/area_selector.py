from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Iterable


@dataclass(frozen=True)
class AreaSelection:
    class_id: int
    class_name: str
    bbox_xyxy: list[float]
    conf: float
    score: float
    frame_index: int
    hu: str | None = None


class AreaSelector:
    def __init__(
        self,
        target_classes: Iterable[str] | None = None,
        warmup_frames: int = 30,
        conf_min: float = 0.25,
        lock_on_first: bool = False,
        hu: str | None = None,
    ) -> None:
        self.target_classes = set(target_classes or {"area_de_trabajo_pallet", "area_de_trabajo_carro"})
        self.warmup_frames = warmup_frames
        self.conf_min = conf_min
        self.lock_on_first = lock_on_first
        self._hu = hu
        self._best: AreaSelection | None = None
        self._seen_frames = 0
        self._locked = False

    @property
    def locked(self) -> bool:
        return self._locked

    @property
    def selected(self) -> AreaSelection | None:
        return self._best

    def set_hu(self, hu: str | None) -> None:
        self._hu = hu
        if self._best is not None:
            self._best = AreaSelection(
                class_id=self._best.class_id,
                class_name=self._best.class_name,
                bbox_xyxy=self._best.bbox_xyxy,
                conf=self._best.conf,
                score=self._best.score,
                frame_index=self._best.frame_index,
                hu=hu,
            )

    def update(
        self,
        detections: Iterable[dict],
        image_size: tuple[int, int],
        frame_index: int,
    ) -> AreaSelection | None:
        if self._locked:
            return self._best

        self._seen_frames += 1
        img_w, img_h = image_size
        img_cx, img_cy = img_w / 2.0, img_h / 2.0
        img_diag = hypot(img_w, img_h)

        for det in detections:
            class_name = det.get("class_name")
            conf = float(det.get("conf", 0.0))
            if class_name not in self.target_classes or conf < self.conf_min:
                continue

            x1, y1, x2, y2 = det.get("bbox_xyxy", [0.0, 0.0, 0.0, 0.0])
            area = max(0.0, (x2 - x1)) * max(0.0, (y2 - y1))
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            dist = hypot(cx - img_cx, cy - img_cy)
            center_score = 1.0 - min(1.0, dist / img_diag)
            score = area * (0.5 + 0.5 * center_score)

            cand = AreaSelection(
                class_id=int(det.get("class_id", -1)),
                class_name=str(class_name),
                bbox_xyxy=[float(x1), float(y1), float(x2), float(y2)],
                conf=conf,
                score=score,
                frame_index=frame_index,
                hu=self._hu,
            )

            if self._best is None or cand.score > self._best.score:
                self._best = cand
                if self.lock_on_first:
                    self._locked = True

        if not self._locked and self._seen_frames >= self.warmup_frames and self._best is not None:
            self._locked = True

        return self._best
