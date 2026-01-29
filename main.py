"""
Punto de entrada principal del pipeline de conteo.
"""
from dataclasses import asdict, replace
from datetime import datetime
import json
from pathlib import Path
import sys

import cv2

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import MAIN, resolve_path
from core import (
    BorderCounter,
    BorderCounterModule,
    DetectorYolo,
    FrameLoader,
    VotingEngine,
    open_video_writer,
    reencode_mp4_ffmpeg,
    SignalsCounterModule,
    InteractionCounterModule,
    Visualizer,
    make_inner_outer,
)


def _timestamped_name(filename: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = Path(filename)
    suffix = p.suffix if p.suffix else ".mp4"
    return f"{p.stem}_{ts}{suffix}"


def _open_video_writer(out_path: Path, fps: float, size: tuple[int, int], container: str):
    return open_video_writer(out_path, fps, size, container=container)


def main():
    cfg = MAIN
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    frames_dir = resolve_path(cfg.frames_dir)
    if not frames_dir.exists():
        raise SystemExit(f"[ERROR] Frames folder not found: {frames_dir}")

    weights = resolve_path(cfg.model)
    if not weights.exists():
        raise SystemExit(f"[ERROR] Model not found: {weights}")

    out_base = resolve_path(cfg.outdir)
    out_base.mkdir(parents=True, exist_ok=True)
    out_video = out_base / _timestamped_name(cfg.out_video)
    events_path = out_base / f"events_{run_id}.jsonl"
    frames_path = out_base / f"frames_{run_id}.jsonl"
    meta_path = out_base / f"run_{run_id}.json"

    border_cfg = replace(cfg.border, mode=cfg.mode)

    meta = {
        "run_id": run_id,
        "frames_dir": str(frames_dir),
        "model": str(weights),
        "config": asdict(cfg),
        "counter_border": asdict(border_cfg),
        "counter_signals": asdict(cfg.signals),
        "counter_interaction": asdict(cfg.interaction),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    loader = FrameLoader(frames_dir=frames_dir, recursive=cfg.recursive)
    detector = DetectorYolo(
        weights=str(weights),
        mode=cfg.mode,
        conf=cfg.conf,
        imgsz=cfg.imgsz,
        device=cfg.device,
        tracker=cfg.tracker,
    )
    viz = Visualizer()

    modules = {}
    if border_cfg.enabled:
        modules["border"] = BorderCounterModule(border_cfg)
    if cfg.signals.enabled:
        modules["signals"] = SignalsCounterModule(cfg.signals)
    if cfg.interaction.enabled:
        modules["interaction"] = InteractionCounterModule(cfg.interaction)
    voter = VotingEngine(cfg.weights, threshold=cfg.vote_threshold)
    if border_cfg.enabled:
        start_count = border_cfg.start_count
        cooldown = border_cfg.cooldown_frames
        min_count = border_cfg.min_count
    elif cfg.interaction.enabled:
        start_count = cfg.interaction.start_count
        cooldown = border_cfg.cooldown_frames
        min_count = border_cfg.min_count
    else:
        start_count = 0
        cooldown = border_cfg.cooldown_frames
        min_count = border_cfg.min_count

    global_counter = BorderCounter(
        start_count=start_count,
        cooldown_frames=cooldown,
        min_count=min_count,
    )

    print(f"[INFO] Frames: {len(loader)} -> {frames_dir}")
    print(f"[INFO] Video: {out_video}")
    if cfg.save_events:
        print(f"[INFO] Events: {events_path}")
    if cfg.save_frames:
        print(f"[INFO] Frames log: {frames_path}")

    writer = None
    writer_path = None
    target_size = None
    count = 0
    module_counts = {}

    f_events = events_path.open("w", encoding="utf-8") if cfg.save_events else None
    f_frames = frames_path.open("w", encoding="utf-8") if cfg.save_frames else None

    try:
        for frame in loader:
            if cfg.limit is not None and count >= cfg.limit:
                break

            result = detector.detect(frame.image, frame_index=frame.index, image_path=str(frame.path))
            detections = result["detections"]

            module_events = {}
            for name, module in modules.items():
                out = module.update(
                    detections=detections,
                    frame_index=frame.index,
                    image_size=(frame.width, frame.height),
                )
                module_events[name] = out.events
                module_counts[name] = out.count_after

                if f_events is not None:
                    for ev in out.events:
                        ev_data = ev.__dict__.copy()
                        ev_data["module"] = name
                        ev_data["count_before"] = out.count_before
                        ev_data["count_after"] = out.count_after
                        ev_data["person_near"] = out.person_near
                        ev_data["area_class"] = out.area.class_name if out.area else None
                        f_events.write(json.dumps(ev_data) + "\n")

            vote_event = voter.vote(module_events, frame_index=frame.index)
            if vote_event is not None:
                global_counter.update([vote_event], frame_index=frame.index)
                if f_events is not None:
                    f_events.write(
                        json.dumps(
                            {
                                "module": "vote",
                                "event_type": vote_event.event_type,
                                "frame_index": vote_event.frame_index,
                                "score": vote_event.score,
                                "reason": vote_event.reason,
                                "count_after": global_counter.state.count,
                            }
                        )
                        + "\n"
                    )

            if f_frames is not None:
                f_frames.write(
                    json.dumps(
                        {
                            "frame_index": frame.index,
                            "image_path": str(frame.path),
                            "count": global_counter.state.count,
                            "num_detections": len(detections),
                        }
                    )
                    + "\n"
                )

            # Draw overlays
            if cfg.draw_detections:
                if cfg.draw_classes:
                    keep = set(cfg.draw_classes)
                    draw_dets = [
                        d for d in detections
                        if d.get("class_name") in keep and d.get("conf", 0.0) >= cfg.draw_conf_min
                    ]
                else:
                    draw_dets = [d for d in detections if d.get("conf", 0.0) >= cfg.draw_conf_min]
                out_img = viz.draw(frame.image, draw_dets)
            else:
                out_img = frame.image.copy()

            if cfg.show_zones and "border" in modules:
                border_mod = modules["border"]
                area = border_mod.selector.selected
                if area is not None:
                    zones = make_inner_outer(
                        area.bbox_xyxy,
                        image_size=(frame.width, frame.height),
                        shrink_px=border_mod.cfg.shrink,
                        expand_px=border_mod.cfg.expand,
                    )
                    out_img = viz.draw_zones(out_img, zones.inner_xyxy, zones.outer_xyxy)
                    if cfg.show_area:
                        out_img = viz.draw_area(out_img, area.bbox_xyxy, label=area.class_name)

            if writer is None:
                w = frame.width - (frame.width % 2)
                h = frame.height - (frame.height % 2)
                target_size = (w, h)
                writer, writer_path = _open_video_writer(out_video, cfg.fps, target_size, cfg.video_container)

            if target_size and (out_img.shape[1] != target_size[0] or out_img.shape[0] != target_size[1]):
                out_img = cv2.resize(out_img, target_size)

            if cfg.show_count:
                y = 30
                cv2.putText(
                    out_img,
                    f"count: {global_counter.state.count}",
                    (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                for name in ("border", "signals", "interaction"):
                    if name in module_counts:
                        y += 25
                        cv2.putText(
                            out_img,
                            f"{name}: {module_counts[name]}",
                            (10, y),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (200, 200, 200),
                            2,
                            cv2.LINE_AA,
                        )
            writer.write(out_img)

            count += 1
            if count % 200 == 0:
                print(f"  done {count}")
    finally:
        if f_events is not None:
            f_events.close()
        if f_frames is not None:
            f_frames.close()

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
