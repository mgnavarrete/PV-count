# utils/img_to_vid.py
import os
import re
import sys
import subprocess
import shutil
from pathlib import Path
from tqdm import tqdm

import cv2

def natural_key(s: str):
    # Orden “humano”: frame2 < frame10
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]

def list_images(img_dir: Path):
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    files = [p for p in img_dir.iterdir() if p.is_file() and p.suffix.lower() in exts]
    files.sort(key=lambda p: natural_key(p.name))
    return files

def make_video_from_folder(img_dir: Path, out_path: Path, fps: int = 30, codec: str = "H264"):
    images = list_images(img_dir)
    if not images:
        print(f"[WARN] No images found in: {img_dir}")
        return False

    # Lee primera imagen para tamaño
    first = cv2.imread(str(images[0]))
    if first is None:
        print(f"[ERROR] Can't read first image: {images[0]}")
        return False

    h, w = first.shape[:2]
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Verificar si ffmpeg está disponible (más confiable para MP4)
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        print("[INFO] Using ffmpeg for video encoding (recommended)")
        return _make_video_with_ffmpeg(images, out_path, fps, w, h)
    else:
        # Fallback a OpenCV
        print("[WARN] ffmpeg not found. Using OpenCV (may produce less compatible videos).")
        print("[INFO] Install ffmpeg for better MP4 compatibility: sudo apt install ffmpeg")
        return _make_video_with_opencv(images, out_path, fps, w, h, codec)

def _make_video_with_ffmpeg(images, out_path: Path, fps: int, w: int, h: int):
    """Usa ffmpeg directamente para generar videos MP4 compatibles"""
    import tempfile
    
    # Crear archivo de lista para ffmpeg (formato concat)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        list_file = f.name
        for img_path in images:
            # Escapar comillas simples en la ruta
            escaped_path = str(img_path.absolute()).replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")
            f.write(f"duration {1.0/fps}\n")
        # Última imagen sin duración para que se muestre correctamente
        escaped_last = str(images[-1].absolute()).replace("'", "'\\''")
        f.write(f"file '{escaped_last}'\n")
    
    try:
        # Usar ffmpeg con concat demuxer y codec libx264 (H.264)
        # yuv420p es necesario para compatibilidad con reproductores
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "23",  # Calidad: 18-28, 23 es buena calidad
            "-preset", "medium",  # Velocidad de codificación
            "-r", str(fps),  # Frame rate de salida
            "-y",  # Sobrescribir si existe
            str(out_path)
        ]
        
        # Ejecutar ffmpeg sin mostrar output a menos que haya error
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            print(f"[ERROR] ffmpeg failed:")
            print(f"  Command: {' '.join(cmd)}")
            if result.stderr:
                print(f"  Error: {result.stderr[-500:]}")  # Últimos 500 caracteres
            return False
        
        # Verificar que el archivo se haya creado correctamente
        if not out_path.exists():
            print(f"[ERROR] Video file was not created: {out_path}")
            return False
        
        file_size = out_path.stat().st_size
        if file_size == 0:
            print(f"[ERROR] Video file is empty: {out_path}")
            return False
        
        print(f"[OK] Saved video with ffmpeg (H.264): {out_path} ({len(images)} frames, {fps} fps, {w}x{h}, {file_size/1024/1024:.2f} MB)")
        return True
    finally:
        # Limpiar archivo temporal
        if os.path.exists(list_file):
            os.unlink(list_file)

def _make_video_with_opencv(images, out_path: Path, fps: int, w: int, h: int, codec: str):
    """Usa OpenCV como fallback"""
    # Intenta codecs compatibles, priorizando los que funcionan mejor
    # XVID funciona bien y es más compatible que mp4v
    codecs_to_try = ["XVID", "MJPG", "mp4v"] if codec == "H264" else [codec]
    writer = None
    used_codec = None
    
    for codec_name in codecs_to_try:
        fourcc = cv2.VideoWriter_fourcc(*codec_name)
        # Para XVID, cambiar extensión a .avi si es necesario
        test_path = str(out_path)
        if codec_name == "XVID" and out_path.suffix == ".mp4":
            test_path = str(out_path.with_suffix(".avi"))
        
        writer = cv2.VideoWriter(test_path, fourcc, fps, (w, h))
        if writer.isOpened():
            used_codec = codec_name
            if test_path != str(out_path):
                print(f"[INFO] XVID codec requires .avi format, using: {test_path}")
            break
        else:
            writer = None
    
    if writer is None or not writer.isOpened():
        print(f"[ERROR] Could not open VideoWriter with any codec: {out_path}")
        print(f"  Tried codecs: {codecs_to_try}")
        return False

    for i, img_path in tqdm(enumerate(images), total=len(images), desc="Processing frames"):
        frame = cv2.imread(str(img_path))
        if frame is None:
            print(f"[WARN] Skipping unreadable image: {img_path}")
            continue

        # Si algún frame cambia de tamaño, lo ajustamos
        if frame.shape[1] != w or frame.shape[0] != h:
            frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)

        writer.write(frame)

        if (i + 1) % 200 == 0:
            print(f"  wrote {i+1}/{len(images)} frames -> {Path(test_path).name}")

    writer.release()
    
    # Verificar que el archivo se haya creado correctamente
    final_path = Path(test_path)
    if not final_path.exists():
        print(f"[ERROR] Video file was not created: {final_path}")
        return False
    
    file_size = final_path.stat().st_size
    if file_size == 0:
        print(f"[ERROR] Video file is empty: {final_path}")
        return False
    
    print(f"[OK] Saved video with OpenCV ({used_codec}): {final_path} ({len(images)} frames, {fps} fps, {w}x{h}, {file_size/1024/1024:.2f} MB)")
    return True

def pick_folder_dialog():
    # Import local para que no reviente en ambientes sin display al importar el módulo
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(title="Select root folder (e.g. .../pickeoPaletts)")
    root.destroy()
    return folder

def main():
    # 1) pick folder
    selected = pick_folder_dialog()
    if not selected:
        print("[INFO] No folder selected. Exit.")
        return 0

    root_dir = Path(selected)
    name_root = root_dir.name  # ej: pickeoPaletts

    # 2) expected structure
    primary_img = root_dir / "primary_camera" / "img"
    secondary_img = root_dir / "secondary_camera" / "img"

    if not primary_img.exists() and not secondary_img.exists():
        print("[ERROR] Folder does not look like expected structure.")
        print(f"  expected: {primary_img}")
        print(f"  expected: {secondary_img}")
        return 1

    # 3) output base: .../data/videos/NameRoot/
    # Si seleccionaste .../data/pickeoPaletts, entonces root_dir.parent = .../data
    data_dir = root_dir.parent
    out_base = data_dir / "videos" / name_root

    # 4) fps configurable por env var o default
    fps = int(os.environ.get("IMG2VID_FPS", "5"))

    # 5) build videos
    ok_any = False
    if primary_img.exists():
        ok_any |= make_video_from_folder(primary_img, out_base / f"{name_root}_primary_vid.mp4", fps=fps)
    else:
        print(f"[WARN] Missing: {primary_img}")

    if secondary_img.exists():
        ok_any |= make_video_from_folder(secondary_img, out_base / f"{name_root}_secondary_vid.mp4", fps=fps)
    else:
        print(f"[WARN] Missing: {secondary_img}")

    return 0 if ok_any else 2

if __name__ == "__main__":
    raise SystemExit(main())
