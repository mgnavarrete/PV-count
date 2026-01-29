from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import DetectorYolo, FrameLoader, Visualizer, open_video_writer, reencode_mp4_ffmpeg


def resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / p).resolve()


@dataclass
class TestInitConfig:
    frames_dir: str = "data/pickeoCarros/secondary_camera/img"
    model: str = "models/MRTN-TRAIN-01.pt"
    mode: str = "predict"
    conf: float = 0.5
    imgsz: int = 1024
    device: str | None = None
    tracker: str = "bytetrack.yaml"
    outdir: str = "output/test_init"
    labels_subdir: str = "labels"
    out_video: str = "annotated.mp4"
    fps: float = 5.0
    video_container: str = "mp4"
    ffmpeg_reencode: bool = True
    recursive: bool = False
    limit: int | None = None
    draw_classes: tuple[str, ...] | None = ("cajas", "folio", "persona")
    draw_conf_min: float = 0.25
    draw_detections: bool = True


def _ensure_dirs(base_out: Path, labels_subdir: str):
    base_out.mkdir(parents=True, exist_ok=True)
    lab_dir = base_out / labels_subdir
    lab_dir.mkdir(parents=True, exist_ok=True)
    return lab_dir


def _timestamped_name(filename: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = Path(filename)
    suffix = p.suffix if p.suffix else ".mp4"
    return f"{p.stem}_{ts}{suffix}"


def _open_video_writer(out_path: Path, fps: float, size: tuple[int, int], container: str):
    return open_video_writer(out_path, fps, size, container=container)


def _save_labels(txt_path: Path, detections: list[dict]):
    lines = []
    for det in detections:
        x1, y1, x2, y2 = det["bbox_xyxy"]
        c = det["class_id"]
        cf = det["conf"]
        tid = det.get("track_id", None)
        if tid is not None:
            lines.append(f"{c} {x1:.2f} {y1:.2f} {x2:.2f} {y2:.2f} {cf:.4f} {tid}")
        else:
            lines.append(f"{c} {x1:.2f} {y1:.2f} {x2:.2f} {y2:.2f} {cf:.4f}")
    txt_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _filter_detections(detections: list[dict], classes: tuple[str, ...] | None, conf_min: float) -> list[dict]:
    if not classes:
        return [d for d in detections if d.get("conf", 0.0) >= conf_min]
    keep = set(classes)
    return [d for d in detections if d.get("class_name") in keep and d.get("conf", 0.0) >= conf_min]


def main():
    cfg = TestInitConfig()

    frames_dir = resolve_path(cfg.frames_dir)
    if not frames_dir.exists():
        raise SystemExit(f"[ERROR] Frames folder not found: {frames_dir}")

    weights = resolve_path(cfg.model)
    if not weights.exists():
        raise SystemExit(f"[ERROR] Model not found: {weights}")

    out_base = resolve_path(cfg.outdir)
    lab_dir = _ensure_dirs(out_base, cfg.labels_subdir)
    out_video = out_base / _timestamped_name(cfg.out_video)

    loader = FrameLoader(frames_dir=frames_dir, recursive=cfg.recursive)
    detector = DetectorYolo(
        weights=str(weights),
        mode=cfg.mode,
        conf=cfg.conf,
        imgsz=cfg.imgsz,
        device=cfg.device,
        tracker=cfg.tracker,
    )
    visualizer = Visualizer()

    total = len(loader)
    print(f"[INFO] Frames: {total} -> {frames_dir}")
    print(f"[INFO] Video: {out_video}")
    print(f"[INFO] Labels: {lab_dir}")

    count = 0
    writer = None
    writer_path = None
    target_size = None
    for frame in loader:
        if cfg.limit is not None and count >= cfg.limit:
            break

        result = detector.detect(frame.image, frame_index=frame.index, image_path=str(frame.path))
        detections = result["detections"]

        if cfg.draw_detections:
            draw_dets = _filter_detections(detections, cfg.draw_classes, cfg.draw_conf_min)
            annotated = visualizer.draw(frame.image, draw_dets)
        else:
            annotated = frame.image.copy()

        if writer is None:
            # Asegurar dimensiones pares para compatibilidad con algunos codecs
            w = frame.width - (frame.width % 2)
            h = frame.height - (frame.height % 2)
            target_size = (w, h)
            writer, writer_path = _open_video_writer(out_video, cfg.fps, target_size, cfg.video_container)

        if target_size and (annotated.shape[1] != target_size[0] or annotated.shape[0] != target_size[1]):
            annotated = cv2.resize(annotated, target_size)

        writer.write(annotated)

        out_txt_path = lab_dir / f"{frame.path.stem}.txt"
        _save_labels(out_txt_path, detections)

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
