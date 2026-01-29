from __future__ import annotations

from pathlib import Path
import subprocess

import cv2


def open_video_writer(
    out_path: Path,
    fps: float,
    size: tuple[int, int],
    container: str = "mp4",
) -> tuple[cv2.VideoWriter, Path]:
    container = container.lower().strip(".")

    if container == "avi":
        avi_path = out_path.with_suffix(".avi")
        for fourcc_str in ("XVID", "MJPG"):
            fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
            writer = cv2.VideoWriter(str(avi_path), fourcc, fps, size)
            if writer.isOpened():
                return writer, avi_path
    else:
        # Prefer mp4v (software) to avoid hardware H264 issues like h264_v4l2m2m.
        for fourcc_str in ("mp4v", "avc1", "H264"):
            fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
            writer = cv2.VideoWriter(str(out_path.with_suffix(".mp4")), fourcc, fps, size)
            if writer.isOpened():
                return writer, out_path.with_suffix(".mp4")
        # Fallback to AVI if mp4 cannot be opened
        avi_path = out_path.with_suffix(".avi")
        for fourcc_str in ("XVID", "MJPG"):
            fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
            writer = cv2.VideoWriter(str(avi_path), fourcc, fps, size)
            if writer.isOpened():
                return writer, avi_path

    raise SystemExit(f"[ERROR] Could not open video writer for: {out_path}")


def reencode_mp4_ffmpeg(
    in_path: Path,
    crf: int = 23,
    preset: str = "veryfast",
    profile: str = "baseline",
    level: str = "3.0",
    faststart: bool = True,
) -> Path:
    if in_path.suffix.lower() != ".mp4":
        return in_path
    out_path = in_path.with_name(f"{in_path.stem}_h264.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(in_path),
        "-c:v",
        "libx264",
        "-profile:v",
        profile,
        "-level",
        level,
        "-pix_fmt",
        "yuv420p",
        "-crf",
        str(crf),
        "-preset",
        preset,
    ]
    if faststart:
        cmd += ["-movflags", "+faststart"]
    cmd.append(str(out_path))
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError:
        print("[WARN] ffmpeg not found. Keeping original mp4.")
        return in_path
    except subprocess.CalledProcessError:
        print("[WARN] ffmpeg failed. Keeping original mp4.")
        return in_path

    try:
        in_path.unlink()
        out_path.rename(in_path)
        return in_path
    except OSError:
        return out_path
