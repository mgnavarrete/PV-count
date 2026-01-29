from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .border_state import BorderState, classify_bbox_state


@dataclass
class TrackedObject:
    obj_id: int
    class_id: int
    class_name: str
    bbox_xyxy: list[float]
    conf: float
    track_id: int | None
    last_state: BorderState
    confirmed_state: BorderState
    counted: bool = False
    inside_streak: int = 0
    outside_streak: int = 0
    missing: int = 0
    last_seen_frame: int = -1
    ocluded: bool = False
    ocluded_frames: int = 0


@dataclass(frozen=True)
class BorderEvent:
    event_type: str  # "enter" | "exit"
    obj_id: int
    class_name: str
    frame_index: int
    conf: float
    bbox_xyxy: list[float]
    reason: str


def _iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    a_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    b_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = a_area + b_area - inter_area
    if union <= 0.0:
        return 0.0
    return inter_area / union


class BorderEventTracker:
    def __init__(
        self,
        target_classes: Iterable[str] | None = None,
        in_frames: int = 2,
        out_frames: int = 2,
        iou_threshold: float = 0.3,
        max_missing: int = 10,
        use_track_id: bool = True,
        max_missing_inside: int = 2,
        border_as_inside: bool = True,
        inner_ratio_min: float | None = None,
        prevent_recount: bool = True,
        ocluded_ttl: int = 45,
    ) -> None:
        self.target_classes = set(target_classes or {"cajas", "folio"})
        self.in_frames = in_frames
        self.out_frames = out_frames
        self.iou_threshold = iou_threshold
        self.max_missing = max_missing
        self.use_track_id = use_track_id
        self.max_missing_inside = max_missing_inside
        self.border_as_inside = border_as_inside
        self.inner_ratio_min = inner_ratio_min
        self.prevent_recount = prevent_recount
        self.ocluded_ttl = ocluded_ttl

        self._next_id = 1
        self._objects: dict[int, TrackedObject] = {}
        self._track_map: dict[int, int] = {}
        self._last_enter_frame: dict[int, int] = {}

    def _new_object(self, det: dict, state: BorderState, frame_index: int) -> TrackedObject:
        obj_id = self._next_id
        self._next_id += 1
        track_id = det.get("track_id", None)
        obj = TrackedObject(
            obj_id=obj_id,
            class_id=int(det.get("class_id", -1)),
            class_name=str(det.get("class_name")),
            bbox_xyxy=list(det.get("bbox_xyxy", [0, 0, 0, 0])),
            conf=float(det.get("conf", 0.0)),
            track_id=int(track_id) if track_id is not None else None,
            last_state=state,
            confirmed_state=BorderState.OUTSIDE,
            counted=False,
            inside_streak=0,
            outside_streak=0,
            missing=0,
            last_seen_frame=frame_index,
            ocluded=False,
            ocluded_frames=0,
        )
        self._objects[obj_id] = obj
        if obj.track_id is not None:
            self._track_map[obj.track_id] = obj_id
        return obj

    def _match_by_iou(self, det: dict, available_ids: set[int]) -> int | None:
        best_id = None
        best_iou = 0.0
        for obj_id in available_ids:
            obj = self._objects[obj_id]
            if obj.class_name != det.get("class_name"):
                continue
            iou = _iou(obj.bbox_xyxy, det["bbox_xyxy"])
            if iou > best_iou:
                best_iou = iou
                best_id = obj_id
        if best_id is not None and best_iou >= self.iou_threshold:
            return best_id
        return None

    def _match_occluded(self, det: dict) -> int | None:
        best_id = None
        best_iou = 0.0
        for obj_id, obj in self._objects.items():
            if not obj.ocluded:
                continue
            if obj.class_name != det.get("class_name"):
                continue
            iou = _iou(obj.bbox_xyxy, det["bbox_xyxy"])
            if iou > best_iou:
                best_iou = iou
                best_id = obj_id
        if best_id is not None and best_iou >= self.iou_threshold:
            return best_id
        return None

    def update(
        self,
        detections: list[dict],
        inner_xyxy: list[float],
        outer_xyxy: list[float],
        frame_index: int,
    ) -> list[BorderEvent]:
        events: list[BorderEvent] = []

        candidates = []
        for det in detections:
            if det.get("class_name") not in self.target_classes:
                continue
            state = classify_bbox_state(
                det["bbox_xyxy"],
                inner_xyxy,
                outer_xyxy,
                inner_ratio_min=self.inner_ratio_min,
            )
            candidates.append((det, state))

        matched_obj_ids: set[int] = set()
        matched_det_idx: set[int] = set()

        # 1) Match by track_id
        if self.use_track_id:
            for idx, (det, state) in enumerate(candidates):
                track_id = det.get("track_id", None)
                if track_id is None:
                    continue
                obj_id = self._track_map.get(int(track_id))
                if obj_id is not None:
                    matched_obj_ids.add(obj_id)
                    matched_det_idx.add(idx)
                    self._update_object(self._objects[obj_id], det, state, frame_index, events)

        # 2) Match remaining by IoU
        available_ids = set(self._objects.keys()) - matched_obj_ids
        for idx, (det, state) in enumerate(candidates):
            if idx in matched_det_idx:
                continue
            # Try to match occluded objects first
            occ_id = self._match_occluded(det)
            if occ_id is not None and occ_id in available_ids:
                matched_obj_ids.add(occ_id)
                matched_det_idx.add(idx)
                available_ids.discard(occ_id)
                self._update_object(self._objects[occ_id], det, state, frame_index, events)
                continue
            obj_id = self._match_by_iou(det, available_ids)
            if obj_id is not None:
                matched_obj_ids.add(obj_id)
                matched_det_idx.add(idx)
                available_ids.discard(obj_id)
                self._update_object(self._objects[obj_id], det, state, frame_index, events)

        # 3) New objects for unmatched detections
        for idx, (det, state) in enumerate(candidates):
            if idx in matched_det_idx:
                continue
            obj = self._new_object(det, state, frame_index)
            self._update_object(obj, det, state, frame_index, events)

        # 4) Aging unmatched objects
        to_remove = []
        for obj_id, obj in self._objects.items():
            if obj_id in matched_obj_ids:
                obj.missing = 0
                obj.ocluded = False
                obj.ocluded_frames = 0
                continue
            obj.missing += 1
            # Tolerancia a misses si estaba dentro: marcar ocluido
            if obj.confirmed_state == BorderState.INSIDE and obj.missing <= self.max_missing_inside:
                obj.ocluded = True
                obj.ocluded_frames += 1
                if obj.ocluded_frames > self.ocluded_ttl:
                    to_remove.append(obj_id)
                continue
            if obj.missing > self.max_missing:
                to_remove.append(obj_id)
        for obj_id in to_remove:
            obj = self._objects.pop(obj_id)
            if obj.track_id is not None and obj.track_id in self._track_map:
                self._track_map.pop(obj.track_id, None)

        return events

    def get_objects(self) -> list[TrackedObject]:
        return list(self._objects.values())

    def _update_object(
        self,
        obj: TrackedObject,
        det: dict,
        state: BorderState,
        frame_index: int,
        events: list[BorderEvent],
    ) -> None:
        obj.bbox_xyxy = list(det.get("bbox_xyxy", obj.bbox_xyxy))
        obj.conf = float(det.get("conf", obj.conf))
        obj.last_state = state
        obj.last_seen_frame = frame_index

        effective_state = state
        if self.border_as_inside and state == BorderState.BORDER:
            effective_state = BorderState.INSIDE

        if effective_state == BorderState.INSIDE:
            obj.inside_streak += 1
            obj.outside_streak = 0
        elif effective_state == BorderState.OUTSIDE:
            obj.outside_streak += 1
            obj.inside_streak = 0
        else:
            obj.inside_streak = 0
            obj.outside_streak = 0

        if obj.inside_streak >= self.in_frames and obj.confirmed_state != BorderState.INSIDE:
            if self.prevent_recount and obj.obj_id in self._last_enter_frame:
                # Ya contada previamente y no hubo salida confirmada
                return
            obj.confirmed_state = BorderState.INSIDE
            obj.counted = True
            self._last_enter_frame[obj.obj_id] = frame_index
            events.append(
                BorderEvent(
                    event_type="enter",
                    obj_id=obj.obj_id,
                    class_name=obj.class_name,
                    frame_index=frame_index,
                    conf=obj.conf,
                    bbox_xyxy=obj.bbox_xyxy,
                    reason=f"inside_streak>={self.in_frames}",
                )
            )

        if obj.outside_streak >= self.out_frames and obj.confirmed_state != BorderState.OUTSIDE:
            obj.confirmed_state = BorderState.OUTSIDE
            obj.counted = False
            if obj.obj_id in self._last_enter_frame:
                self._last_enter_frame.pop(obj.obj_id, None)
            events.append(
                BorderEvent(
                    event_type="exit",
                    obj_id=obj.obj_id,
                    class_name=obj.class_name,
                    frame_index=frame_index,
                    conf=obj.conf,
                    bbox_xyxy=obj.bbox_xyxy,
                    reason=f"outside_streak>={self.out_frames}",
                )
            )
