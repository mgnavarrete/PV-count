from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .area_selector import AreaSelector, AreaSelection
from .area_zones import make_inner_outer, AreaZones
from .border_state import classify_bbox_state, BorderState
from .person_gate import person_near_border


@dataclass(frozen=True)
class SignalEvent:
    event_type: str  # "enter" | "exit"
    frame_index: int
    score: float
    reason: str


@dataclass
class SignalsOutput:
    events: list[SignalEvent]
    count_before: int
    count_after: int
    area: AreaSelection | None
    zones: AreaZones | None
    person_near: bool


class SignalsCounterModule:
    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.selector = AreaSelector(warmup_frames=cfg.warmup, conf_min=cfg.conf_area, hu=getattr(cfg, "hu", None))
        self.counts = deque(maxlen=cfg.window_size)
        self.last_stable: int | None = None
        self.up_streak = 0
        self.down_streak = 0
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

    def update(self, detections: list[dict], frame_index: int, image_size: tuple[int, int]) -> SignalsOutput:
        self.selector.update(detections, image_size=image_size, frame_index=frame_index)

        if self.selector.selected is None:
            return SignalsOutput(
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

        events: list[SignalEvent] = []
        if smoothed is not None:
            if self.last_stable is None and len(self.counts) == self.counts.maxlen:
                self.last_stable = smoothed

            if self.last_stable is not None:
                delta = smoothed - self.last_stable
                if delta >= 1:
                    self.up_streak += 1
                    self.down_streak = 0
                elif delta <= -1:
                    self.down_streak += 1
                    self.up_streak = 0
                else:
                    self.up_streak = 0
                    self.down_streak = 0

                if self.up_streak >= self.cfg.persist_frames and (person_near_mem or not self.cfg.require_person):
                    events.append(
                        SignalEvent(
                            event_type="enter",
                            frame_index=frame_index,
                            score=1.0,
                            reason=f"visible+ persist>={self.cfg.persist_frames}",
                        )
                    )
                    self.current_count += 1
                    self.last_stable = smoothed
                    self.up_streak = 0

                if self.down_streak >= self.cfg.persist_frames and (person_near_mem or not self.cfg.require_person):
                    events.append(
                        SignalEvent(
                            event_type="exit",
                            frame_index=frame_index,
                            score=-1.0,
                            reason=f"visible- persist>={self.cfg.persist_frames}",
                        )
                    )
                    self.current_count = max(0, self.current_count - 1)
                    self.last_stable = smoothed
                    self.down_streak = 0

        return SignalsOutput(
            events=events,
            count_before=self.current_count,
            count_after=self.current_count,
            area=area,
            zones=zones,
            person_near=person_near_mem,
        )
