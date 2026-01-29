from __future__ import annotations

from typing import Iterable

import cv2


def _color_for_class(class_id: int) -> tuple[int, int, int]:
    # Color determinístico por clase (BGR)
    r = (37 * class_id + 17) % 255
    g = (17 * class_id + 29) % 255
    b = (29 * class_id + 43) % 255
    return int(b), int(g), int(r)


class Visualizer:
    def __init__(self, thickness: int = 2, font_scale: float = 0.5) -> None:
        self.thickness = thickness
        self.font_scale = font_scale

    def draw(self, image, detections: Iterable[dict]) -> "cv2.typing.MatLike":
        annotated = image.copy()
        for det in detections:
            class_id = int(det.get("class_id", -1))
            class_name = det.get("class_name", str(class_id))
            conf = det.get("conf", 0.0)
            track_id = det.get("track_id", None)
            x1, y1, x2, y2 = det.get("bbox_xyxy", [0, 0, 0, 0])

            color = _color_for_class(class_id)
            cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), color, self.thickness)

            label = f"{class_name} {conf:.2f}"
            if track_id is not None:
                label = f"{label} id:{track_id}"

            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, 1)
            y_text = max(int(y1) - 4, th + 2)
            cv2.rectangle(
                annotated,
                (int(x1), y_text - th - 4),
                (int(x1) + tw + 4, y_text),
                color,
                -1,
            )
            cv2.putText(
                annotated,
                label,
                (int(x1) + 2, y_text - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                self.font_scale,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
        return annotated

    def draw_area(
        self,
        image,
        bbox_xyxy: list[float],
        label: str = "area",
        color: tuple[int, int, int] = (0, 255, 255),
    ) -> "cv2.typing.MatLike":
        annotated = image.copy()
        x1, y1, x2, y2 = bbox_xyxy
        cv2.rectangle(
            annotated,
            (int(x1), int(y1)),
            (int(x2), int(y2)),
            color,
            max(2, self.thickness),
        )
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, 1)
        y_text = max(int(y1) - 4, th + 2)
        cv2.rectangle(
            annotated,
            (int(x1), y_text - th - 4),
            (int(x1) + tw + 4, y_text),
            color,
            -1,
        )
        cv2.putText(
            annotated,
            label,
            (int(x1) + 2, y_text - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            self.font_scale,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )
        return annotated

    def draw_zones(
        self,
        image,
        inner_xyxy: list[float],
        outer_xyxy: list[float],
        label_inner: str = "inner",
        label_outer: str = "outer",
        color_inner: tuple[int, int, int] = (0, 255, 255),
        color_outer: tuple[int, int, int] = (0, 128, 255),
    ) -> "cv2.typing.MatLike":
        annotated = image.copy()
        annotated = self.draw_area(annotated, outer_xyxy, label=label_outer, color=color_outer)
        annotated = self.draw_area(annotated, inner_xyxy, label=label_inner, color=color_inner)
        return annotated
