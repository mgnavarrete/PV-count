from __future__ import annotations

from dataclasses import dataclass

from .border_event_tracker import BorderEvent


@dataclass
class CounterState:
    count: int = 0
    last_event_frame: int = -1


class BorderCounter:
    def __init__(self, start_count: int = 0, cooldown_frames: int = 3, min_count: int = 0) -> None:
        self.state = CounterState(count=start_count)
        self.cooldown_frames = cooldown_frames
        self.min_count = min_count

    def update(self, events: list[BorderEvent], frame_index: int) -> int:
        # En este sistema asumimos máximo 1 evento por frame.
        if not events:
            return self.state.count

        if self.state.last_event_frame >= 0 and frame_index - self.state.last_event_frame < self.cooldown_frames:
            return self.state.count

        ev = events[0]
        if ev.event_type == "enter":
            self.state.count += 1
        elif ev.event_type == "exit":
            self.state.count = max(self.min_count, self.state.count - 1)

        self.state.last_event_frame = frame_index
        return self.state.count
