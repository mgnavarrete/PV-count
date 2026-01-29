from dataclasses import dataclass, replace
from datetime import datetime
import json
from pathlib import Path
import sys

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import MAIN, resolve_path
from core import (
    AreaSelector,
    BorderCounter,
    BorderEventTracker,
    DetectorYolo,
    FrameLoader,
    Visualizer,
    make_inner_outer,
    person_near_border,
    BorderState,
    open_video_writer,
    reencode_mp4_ffmpeg,
)


@dataclass
class TestBorderConfig:
    frames_dir: str = MAIN.frames_dir
    model: str = MAIN.model
    mode: str = MAIN.mode
    conf: float = MAIN.conf
    imgsz: int = MAIN.imgsz
    device: str | None = MAIN.device
    tracker: str = MAIN.tracker
    outdir: str = "output/test_border_events"
    out_video: str = "annotated.mp4"
    fps: float = MAIN.fps
    video_container: str = MAIN.video_container
    ffmpeg_reencode: bool = MAIN.ffmpeg_reencode
    recursive: bool = MAIN.recursive
    limit: int | None = MAIN.limit
    draw_classes: tuple[str, ...] | None = ("cajas", "folio", "persona", "producto_en_mano")
    draw_conf_min: float = 0.25
    draw_detections: bool = True
    show_person_gate: bool = True
    show_obj_state: bool = True
    show_counted_label: bool = True
    show_count: bool = True
    show_counted: bool = True
    counted_color: tuple[int, int, int] = (0, 255, 0)
    state_color_inside: tuple[int, int, int] = (0, 255, 0)
    state_color_border: tuple[int, int, int] = (0, 165, 255)
    state_color_outside: tuple[int, int, int] = (0, 0, 255)
    label_border_as_inside: bool = False


def _timestamped_name(filename: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = Path(filename)
    suffix = p.suffix if p.suffix else ".mp4"
    return f"{p.stem}_{ts}{suffix}"


def _open_video_writer(out_path: Path, fps: float, size: tuple[int, int], container: str):
    return open_video_writer(out_path, fps, size, container=container)


def main():
    cfg = TestBorderConfig()
    border_cfg = replace(MAIN.border, mode=cfg.mode)

    frames_dir = resolve_path(cfg.frames_dir)
    if not frames_dir.exists():
        raise SystemExit(f"[ERROR] Frames folder not found: {frames_dir}")

    weights = resolve_path(cfg.model)
    if not weights.exists():
        raise SystemExit(f"[ERROR] Model not found: {weights}")

    out_base = resolve_path(cfg.outdir)
    out_base.mkdir(parents=True, exist_ok=True)
    out_video = out_base / _timestamped_name(cfg.out_video)
    events_path = out_base / f"events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    loader = FrameLoader(frames_dir=frames_dir, recursive=cfg.recursive)
    detector = DetectorYolo(
        weights=str(weights),
        mode=cfg.mode,
        conf=cfg.conf,
        imgsz=cfg.imgsz,
        device=cfg.device,
        tracker=cfg.tracker,
    )
    selector = AreaSelector(warmup_frames=border_cfg.warmup, conf_min=border_cfg.conf_area)
    tracker = BorderEventTracker(
        in_frames=border_cfg.in_frames,
        out_frames=border_cfg.out_frames,
        iou_threshold=border_cfg.iou,
        max_missing=border_cfg.max_missing,
        use_track_id=(cfg.mode == "track"),
        max_missing_inside=border_cfg.max_missing_inside,
        border_as_inside=border_cfg.border_as_inside,
        inner_ratio_min=border_cfg.inner_ratio_min,
        prevent_recount=border_cfg.prevent_recount,
        ocluded_ttl=border_cfg.ocluded_ttl,
    )
    counter = BorderCounter(
        start_count=border_cfg.start_count,
        cooldown_frames=border_cfg.cooldown_frames,
        min_count=border_cfg.min_count,
    )
    viz = Visualizer()

    print(f"[INFO] Frames: {len(loader)} -> {frames_dir}")
    print(f"[INFO] Video: {out_video}")
    print(f"[INFO] Events: {events_path}")

    writer = None
    writer_path = None
    target_size = None
    count = 0
    person_near_streak = 0

    def _filter_detections(dets):
        if not cfg.draw_detections:
            return []
        if not cfg.draw_classes:
            return [d for d in dets if d.get("conf", 0.0) >= cfg.draw_conf_min]
        keep = set(cfg.draw_classes)
        return [d for d in dets if d.get("class_name") in keep and d.get("conf", 0.0) >= cfg.draw_conf_min]

    with events_path.open("w", encoding="utf-8") as f_events:
        for frame in loader:
            if cfg.limit is not None and count >= cfg.limit:
                break

            result = detector.detect(frame.image, frame_index=frame.index, image_path=str(frame.path))
            detections = result["detections"]
            selector.update(detections, image_size=(frame.width, frame.height), frame_index=frame.index)

            draw_dets = _filter_detections(detections)
            annotated = viz.draw(frame.image, draw_dets) if draw_dets else frame.image.copy()

            if selector.selected is not None:
                area = selector.selected
                zones = make_inner_outer(
                    area.bbox_xyxy,
                    image_size=(frame.width, frame.height),
                    shrink_px=border_cfg.shrink,
                    expand_px=border_cfg.expand,
                )
                annotated = viz.draw_zones(
                    annotated,
                    inner_xyxy=zones.inner_xyxy,
                    outer_xyxy=zones.outer_xyxy,
                    label_inner="inner",
                    label_outer="outer",
                )

                person_near, _ = person_near_border(
                    detections,
                    inner_xyxy=zones.inner_xyxy,
                    outer_xyxy=zones.outer_xyxy,
                    conf_min=border_cfg.person_conf_min,
                    dist_px=border_cfg.person_dist_px,
                )
                if person_near:
                    person_near_streak = border_cfg.person_gate_memory
                else:
                    person_near_streak = max(0, person_near_streak - 1)
                person_near_mem = person_near or person_near_streak > 0

                events = tracker.update(
                    detections=detections,
                    inner_xyxy=zones.inner_xyxy,
                    outer_xyxy=zones.outer_xyxy,
                    frame_index=frame.index,
                )
                if border_cfg.require_person and not person_near_mem:
                    events = []

                count_before = counter.state.count
                count_after = counter.update(events, frame_index=frame.index)
                for ev in events:
                    ev_data = ev.__dict__.copy()
                    ev_data["count_before"] = count_before
                    ev_data["count_after"] = count_after
                    ev_data["person_near"] = person_near_mem
                    f_events.write(json.dumps(ev_data) + "\n")
                    cv2.putText(
                        annotated,
                        f"{ev.event_type} {ev.class_name}",
                        (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 255),
                        2,
                        cv2.LINE_AA,
                    )

                if cfg.show_person_gate:
                    gate_text = "persona_cerca: SI" if person_near_mem else "persona_cerca: NO"
                    gate_color = (0, 255, 0) if person_near_mem else (0, 0, 255)
                    cv2.putText(
                        annotated,
                        gate_text,
                        (10, 45),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        gate_color,
                        2,
                        cv2.LINE_AA,
                    )

                if cfg.show_obj_state:
                    for obj in tracker.get_objects():
                        color = cfg.state_color_border
                        if obj.last_state == BorderState.INSIDE:
                            color = cfg.state_color_inside
                        elif obj.last_state == BorderState.OUTSIDE:
                            color = cfg.state_color_outside

                        x1, y1, x2, y2 = obj.bbox_xyxy
                        cv2.rectangle(
                            annotated,
                            (int(x1), int(y1)),
                            (int(x2), int(y2)),
                            color,
                            2,
                        )
                        if cfg.show_counted_label:
                            label_state = obj.last_state.value
                            if cfg.label_border_as_inside and obj.last_state == BorderState.BORDER:
                                label_state = "inside"
                            label = label_state
                            label += " counted" if obj.counted else " not"
                            cv2.putText(
                                annotated,
                                label,
                                (int(x1), max(10, int(y1) - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5,
                                color,
                                1,
                                cv2.LINE_AA,
                            )
                elif cfg.show_counted:
                    for obj in tracker.get_objects():
                        if not obj.counted:
                            continue
                        x1, y1, x2, y2 = obj.bbox_xyxy
                        cv2.rectangle(
                            annotated,
                            (int(x1), int(y1)),
                            (int(x2), int(y2)),
                            cfg.counted_color,
                            2,
                        )

                if cfg.show_count:
                    cv2.putText(
                        annotated,
                        f"count: {counter.state.count}",
                        (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 255),
                        2,
                        cv2.LINE_AA,
                    )

            if writer is None:
                w = frame.width - (frame.width % 2)
                h = frame.height - (frame.height % 2)
                target_size = (w, h)
                writer, writer_path = _open_video_writer(out_video, cfg.fps, target_size, cfg.video_container)

            if target_size and (annotated.shape[1] != target_size[0] or annotated.shape[0] != target_size[1]):
                annotated = cv2.resize(annotated, target_size)

            writer.write(annotated)

            count += 1
            if count % 200 == 0:
                print(f"  done {count}")

    if writer is not None:
        writer.release()
        if writer_path is not None:
            final_path = writer_path
            if cfg.ffmpeg_reencode:
                final_path = reencode_mp4_ffmpeg(writer_path)
            print(f"[OK] Video saved: {final_path}")

    print(f"[OK] Processed {count} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
