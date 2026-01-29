from __future__ import annotations

from dataclasses import dataclass

from .area_selector import AreaSelector, AreaSelection
from .area_zones import make_inner_outer, AreaZones
from .border_counter import BorderCounter
from .border_event_tracker import BorderEventTracker, BorderEvent
from .person_gate import person_near_border


@dataclass
class ModuleOutput:
    events: list[BorderEvent]
    count_before: int
    count_after: int
    area: AreaSelection | None
    zones: AreaZones | None
    person_near: bool


class BorderCounterModule:
    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.selector = AreaSelector(warmup_frames=cfg.warmup, conf_min=cfg.conf_area, hu=getattr(cfg, "hu", None))
        self.tracker = BorderEventTracker(
            in_frames=cfg.in_frames,
            out_frames=cfg.out_frames,
            iou_threshold=cfg.iou,
            max_missing=cfg.max_missing,
            use_track_id=(cfg.mode == "track"),
            max_missing_inside=cfg.max_missing_inside,
            border_as_inside=cfg.border_as_inside,
            inner_ratio_min=cfg.inner_ratio_min,
            prevent_recount=cfg.prevent_recount,
            ocluded_ttl=cfg.ocluded_ttl,
        )
        self.counter = BorderCounter(
            start_count=cfg.start_count,
            cooldown_frames=cfg.cooldown_frames,
            min_count=cfg.min_count,
        )
        self.person_near_streak = 0

    def update(self, detections: list[dict], frame_index: int, image_size: tuple[int, int]) -> ModuleOutput:
        self.selector.update(detections, image_size=image_size, frame_index=frame_index)

        if self.selector.selected is None:
            return ModuleOutput(
                events=[],
                count_before=self.counter.state.count,
                count_after=self.counter.state.count,
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

        events = self.tracker.update(
            detections=detections,
            inner_xyxy=zones.inner_xyxy,
            outer_xyxy=zones.outer_xyxy,
            frame_index=frame_index,
        )
        if self.cfg.require_person and not person_near_mem:
            events = []

        count_before = self.counter.state.count
        count_after = self.counter.update(events, frame_index=frame_index)
        return ModuleOutput(
            events=events,
            count_before=count_before,
            count_after=count_after,
            area=area,
            zones=zones,
            person_near=person_near_mem,
        )
