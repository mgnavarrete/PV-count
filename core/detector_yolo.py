from __future__ import annotations

from pathlib import Path
from typing import Any

from ultralytics import YOLO


class DetectorYolo:
    """
    Wrapper ligero para YOLO.

    Formato de salida por imagen:
    {
        "frame_index": int | None,
        "image_path": str | None,
        "image_size": (width, height),
        "detections": [
            {
                "class_id": int,
                "class_name": str,
                "conf": float,
                "bbox_xyxy": [x1, y1, x2, y2],
                "track_id": int | None,
            },
            ...
        ],
    }
    """

    def __init__(
        self,
        weights: str | Path,
        mode: str = "predict",
        conf: float = 0.5,
        imgsz: int = 1024,
        device: str | int | None = None,
        tracker: str = "bytetrack.yaml",
    ) -> None:
        self.weights = str(weights)
        self.mode = mode
        self.conf = conf
        self.imgsz = imgsz
        self.device = device
        self.tracker = tracker
        self.model = YOLO(self.weights)
        self.names = self.model.names

    def detect(self, image, frame_index: int | None = None, image_path: str | None = None) -> dict[str, Any]:
        if self.mode == "track":
            results = self.model.track(
                source=image,
                conf=self.conf,
                imgsz=self.imgsz,
                device=self.device,
                tracker=self.tracker,
                persist=True,
                verbose=False,
            )
        else:
            results = self.model.predict(
                source=image,
                conf=self.conf,
                imgsz=self.imgsz,
                device=self.device,
                verbose=False,
            )

        r = results[0]
        detections: list[dict[str, Any]] = []

        boxes = r.boxes
        if boxes is not None and len(boxes) > 0:
            xyxy = boxes.xyxy.cpu().numpy()
            cls = boxes.cls.cpu().numpy().astype(int)
            confs = boxes.conf.cpu().numpy()
            ids = None
            if self.mode == "track" and getattr(boxes, "id", None) is not None:
                ids = boxes.id.cpu().numpy().astype(int)

            for i in range(len(xyxy)):
                x1, y1, x2, y2 = xyxy[i].tolist()
                class_id = int(cls[i])
                class_name = self.names[class_id] if isinstance(self.names, (list, dict)) else str(class_id)
                det = {
                    "class_id": class_id,
                    "class_name": class_name,
                    "conf": float(confs[i]),
                    "bbox_xyxy": [float(x1), float(y1), float(x2), float(y2)],
                    "track_id": int(ids[i]) if ids is not None else None,
                }
                detections.append(det)

        h, w = r.orig_shape[:2] if r.orig_shape is not None else (None, None)
        return {
            "frame_index": frame_index,
            "image_path": image_path,
            "image_size": (w, h),
            "detections": detections,
        }
