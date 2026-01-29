from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .area_selector import AreaSelector, AreaSelection
from .area_zones import make_inner_outer, AreaZones
from .border_state import classify_bbox_state, BorderState
from .person_gate import person_near_border


@dataclass(frozen=True)
class InteractionEvent:
    event_type: str  # "enter" | "exit"
    frame_index: int
    score: float
    reason: str


@dataclass
class InteractionOutput:
    events: list[InteractionEvent]
    count_before: int
    count_after: int
    area: AreaSelection | None
    zones: AreaZones | None
    person_near: bool


class InteractionCounterModule:
    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.selector = AreaSelector(warmup_frames=cfg.warmup, conf_min=cfg.conf_area, hu=getattr(cfg, "hu", None))
        self.counts = deque(maxlen=cfg.window_size)
        self.active = False
        self.idle_frames = 0
        self.count_before: int | None = None
        self.count_after: int | None = None
        self.person_near_streak = 0
        self.current_count = cfg.start_count

    def _median(self) -> int | None:
        if not self.counts:
            return None
        vals = sorted(self.counts)
        mid = len(vals) // 2
        if len(vals) % 2 == 1:
            return int(vals[mid])
        return int(round((vals[mid - 1] + vals[mid]) / 2))

    def _count_visible_inside(self, detections: list[dict], inner_xyxy: list[float], outer_xyxy: list[float]) -> int:
        n = 0
        for det in detections:
            if det.get("class_name") not in self.cfg.target_classes:
                continue
            if det.get("conf", 0.0) < self.cfg.min_conf:
                continue
            state = classify_bbox_state(
                det["bbox_xyxy"],
                inner_xyxy,
                outer_xyxy,
                inner_ratio_min=self.cfg.inner_ratio_min,
            )
            if state == BorderState.INSIDE:
                n += 1
        return n

    def update(self, detections: list[dict], frame_index: int, image_size: tuple[int, int]) -> InteractionOutput:
        self.selector.update(detections, image_size=image_size, frame_index=frame_index)

        if self.selector.selected is None:
            return InteractionOutput(
                events=[],
                count_before=self.current_count,
                count_after=self.current_count,
                area=None,
                zones=None,
                person_near=False,
            )

        area = self.selector.selected
        zones = make_inner_outer(
            area.bbox_xyxy,
            image_size=image_size,
            shrink_px=self.cfg.shrink,
            expand_px=self.cfg.expand,
        )

        person_near, _ = person_near_border(
            detections,
            inner_xyxy=zones.inner_xyxy,
            outer_xyxy=zones.outer_xyxy,
            conf_min=self.cfg.person_conf_min,
            dist_px=self.cfg.person_dist_px,
        )
        if person_near:
            self.person_near_streak = self.cfg.person_gate_memory
        else:
            self.person_near_streak = max(0, self.person_near_streak - 1)
        person_near_mem = person_near or self.person_near_streak > 0

        n_visible = self._count_visible_inside(detections, zones.inner_xyxy, zones.outer_xyxy)
        self.counts.append(n_visible)
        smoothed = self._median()

        events: list[InteractionEvent] = []
        if self.cfg.require_person and not person_near_mem:
            # Not active; only count idle frames
            self.idle_frames += 1
        else:
            self.idle_frames = 0

        if not self.active and person_near_mem:
            if smoothed is not None and len(self.counts) == self.counts.maxlen:
                self.active = True
                self.count_before = smoothed

        if self.active and self.idle_frames >= self.cfg.min_idle_frames:
            if smoothed is not None:
                self.count_after = smoothed
                delta = self.count_after - (self.count_before or 0)
                if delta >= 1:
                    events.append(
                        InteractionEvent(
                            event_type="enter",
                            frame_index=frame_index,
                            score=1.0,
                            reason="interaction_window+",
                        )
                    )
                    self.current_count += 1
                elif delta <= -1:
                    events.append(
                        InteractionEvent(
                            event_type="exit",
                            frame_index=frame_index,
                            score=-1.0,
                            reason="interaction_window-",
                        )
                    )
                    self.current_count = max(0, self.current_count - 1)

            self.active = False
            self.count_before = None
            self.count_after = None
            self.idle_frames = 0

        return InteractionOutput(
            events=events,
            count_before=self.current_count,
            count_after=self.current_count,
            area=area,
            zones=zones,
            person_near=person_near_mem,
        )
