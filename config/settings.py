from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / p).resolve()


@dataclass
class BorderCounterConfig:
    enabled: bool = True
    warmup: int = 30
    conf_area: float = 0.25
    hu: str | None = None
    shrink: int = -30
    expand: int = 40
    in_frames: int = 1
    out_frames: int = 1
    iou: float = 0.3
    max_missing: int = 30
    max_missing_inside: int = 10
    border_as_inside: bool = False
    inner_ratio_min: float = 0.6
    prevent_recount: bool = True
    ocluded_ttl: int = 45
    person_conf_min: float = 0.25
    person_dist_px: float = 15.0
    person_gate_memory: int = 10
    require_person: bool = False
    start_count: int = 0
    cooldown_frames: int = 3
    min_count: int = 0
    mode: str = "predict"


@dataclass
class SignalsCounterConfig:
    enabled: bool = False
    warmup: int = 30
    conf_area: float = 0.25
    hu: str | None = None
    shrink: int = -30
    expand: int = 40
    inner_ratio_min: float = 0.6
    min_conf: float = 0.25
    target_classes: tuple[str, ...] = ("cajas", "folio")
    window_size: int = 5
    persist_frames: int = 2
    require_person: bool = True
    person_conf_min: float = 0.25
    person_dist_px: float = 15.0
    person_gate_memory: int = 10
    start_count: int = 0


@dataclass
class InteractionCounterConfig:
    enabled: bool = True
    warmup: int = 30
    conf_area: float = 0.25
    hu: str | None = None
    shrink: int = -30
    expand: int = 40
    inner_ratio_min: float = 0.6
    min_conf: float = 0.25
    target_classes: tuple[str, ...] = ("cajas", "folio")
    window_size: int = 7
    require_person: bool = True
    person_conf_min: float = 0.25
    person_dist_px: float = 15.0
    person_gate_memory: int = 10
    min_idle_frames: int = 5
    start_count: int = 0


@dataclass
class MainConfig:
    frames_dir: str = "data/pickeoPaletts/secondary_camera/img"
    model: str = "models/MRTN-TRAIN-01.pt"
    mode: str = "predict"
    conf: float = 0.5
    imgsz: int = 1024
    device: str | None = None
    tracker: str = "bytetrack.yaml"
    outdir: str = "output/main"
    out_video: str = "main.mp4"
    fps: float = 5.0
    video_container: str = "mp4"
    ffmpeg_reencode: bool = True
    recursive: bool = False
    limit: int | None = None
    vote_threshold: float = 0.5
    weights: dict[str, float] = field(default_factory=lambda: {"border": 1.0, "interaction": 0.5})
    save_events: bool = True
    save_frames: bool = True
    show_count: bool = True
    draw_detections: bool = True
    draw_classes: tuple[str, ...] | None = ("persona", "producto_en_mano", "cajas", "folio")
    draw_conf_min: float = 0.25
    show_zones: bool = True
    show_area: bool = True
    border: BorderCounterConfig = field(default_factory=BorderCounterConfig)
    signals: SignalsCounterConfig = field(default_factory=SignalsCounterConfig)
    interaction: InteractionCounterConfig = field(default_factory=InteractionCounterConfig)


MAIN = MainConfig()
