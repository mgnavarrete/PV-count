from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class VoteEvent:
    event_type: str  # "enter" | "exit"
    frame_index: int
    score: float
    reason: str


class VotingEngine:
    def __init__(self, weights: dict[str, float], threshold: float = 0.5) -> None:
        self.weights = weights
        self.threshold = threshold

    def vote(self, module_events: dict[str, list], frame_index: int) -> VoteEvent | None:
        score = 0.0
        details = []
        for name, events in module_events.items():
            if not events:
                continue
            ev = events[0]
            w = self.weights.get(name, 1.0)
            if ev.event_type == "enter":
                score += w
                details.append(f"{name}:+{w}")
            elif ev.event_type == "exit":
                score -= w
                details.append(f"{name}:-{w}")
        if abs(score) >= self.threshold:
            event_type = "enter" if score > 0 else "exit"
            reason = " | ".join(details) if details else "no_votes"
            return VoteEvent(event_type=event_type, frame_index=frame_index, score=score, reason=reason)
        return None
