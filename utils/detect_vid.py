# utils/detect_vid.py
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

from ultralytics import YOLO


def pick_video_dialog() -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    video = filedialog.askopenfilename(
        title="Select a video",
        filetypes=[
            ("Video files", "*.mp4 *.avi *.mov *.mkv *.m4v"),
            ("All files", "*.*"),
        ],
    )
    root.destroy()
    return video


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["predict", "track"], default="predict",
                    help="predict = detections only, track = detections + tracking IDs")
    ap.add_argument("--conf", type=float, default=0.1)
    ap.add_argument("--imgsz", type=int, default=1024)
    ap.add_argument("--device", default=None, help="e.g. 0, 'cpu'")
    ap.add_argument("--tracker", default="bytetrack.yaml",
                    help="Only used in track mode (e.g. bytetrack.yaml / botsort.yaml)")
    ap.add_argument("--outdir", default="output", help="Output base folder")
    args = ap.parse_args()

    video_path = pick_video_dialog()
    if not video_path:
        print("[INFO] No video selected. Exit.")
        return 0

    video_path = str(Path(video_path).resolve())
    weights = str((Path(__file__).resolve().parents[1] / "models" / "MRTN-TRAIN-01.pt").resolve())

    model = YOLO(weights)

    # Obtener el nombre de la carpeta padre del video (ej: pickeoPaletts)
    parent_folder = Path(video_path).parent.name
    # Generar timestamp en formato YYYYMMDD_HHMMSS
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Detectar si es primary o secondary camera basado en el nombre del archivo
    video_name_lower = Path(video_path).stem.lower()
    if "primary" in video_name_lower:
        camera_type = "primarycamera"
    elif "secondary" in video_name_lower:
        camera_type = "secondarycamera"
    else:
        camera_type = "camera"
    
    # Nombre del archivo de salida: pickeoPaletts_timestamp_primarycamera.mp4
    output_filename = f"{parent_folder}_{timestamp}_{camera_type}.mp4"
    
    # Construir la ruta completa de salida directamente en output/
    outdir_path = Path(args.outdir).resolve()
    outdir_path.mkdir(parents=True, exist_ok=True)
    save_dir = str(outdir_path)

    if args.mode == "predict":
        result = model.predict(
            source=video_path,
            save=True,
            save_dir=save_dir,
            name=output_filename.replace(".mp4", ""),  # name sin extensión
            conf=args.conf,
            imgsz=args.imgsz,
            device=args.device,
        )
    else:
        result = model.track(
            source=video_path,
            save=True,
            save_dir=save_dir,
            name=output_filename.replace(".mp4", ""),  # name sin extensión
            conf=args.conf,
            imgsz=args.imgsz,
            device=args.device,
            tracker=args.tracker,
            persist=True,
        )
    
    # Ultralytics guarda el archivo en save_dir/name/archivo.mp4 o .avi
    # Buscar el archivo de video generado y moverlo a la ubicación final
    name_without_ext = output_filename.replace(".mp4", "")
    predicted_dir = Path(save_dir) / name_without_ext
    
    final_output = outdir_path / output_filename
    
    if predicted_dir.exists() and predicted_dir.is_dir():
        # Buscar archivos de video generados en la subcarpeta (mp4 o avi)
        video_files = list(predicted_dir.glob("*.mp4")) + list(predicted_dir.glob("*.avi"))
        if video_files:
            source_file = video_files[0]
            if source_file.suffix == ".avi":
                # Si es .avi, convertirlo a .mp4 usando ffmpeg
                try:
                    subprocess.run(
                        ["ffmpeg", "-i", str(source_file), "-c:v", "libx264", 
                         "-c:a", "aac", "-y", str(final_output)],
                        check=True,
                        capture_output=True
                    )
                    source_file.unlink()  # Eliminar el archivo .avi original
                    print(f"[OK] Converted and saved as: {final_output.resolve()}")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Si ffmpeg no está disponible, simplemente renombrar
                    print("[WARNING] ffmpeg not found, renaming .avi to .mp4 (no conversion)")
                    source_file.rename(final_output)
                    print(f"[OK] Output saved as: {final_output.resolve()}")
            else:
                # Si ya es .mp4, moverlo
                source_file.rename(final_output)
                print(f"[OK] Output saved as: {final_output.resolve()}")
            # Eliminar la carpeta temporal si está vacía
            try:
                predicted_dir.rmdir()
            except OSError:
                pass
        else:
            print(f"[WARNING] No video file found in {predicted_dir.resolve()}")
    else:
        # Buscar directamente en output/ por si acaso
        video_files = list(outdir_path.glob("*.mp4")) + list(outdir_path.glob("*.avi"))
        if video_files:
            # Renombrar el más reciente
            latest_video = max(video_files, key=lambda p: p.stat().st_mtime)
            if latest_video.suffix == ".avi":
                try:
                    subprocess.run(
                        ["ffmpeg", "-i", str(latest_video), "-c:v", "libx264", 
                         "-c:a", "aac", "-y", str(final_output)],
                        check=True,
                        capture_output=True
                    )
                    latest_video.unlink()
                    print(f"[OK] Converted and saved as: {final_output.resolve()}")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    latest_video.rename(final_output)
                    print(f"[OK] Output saved as: {final_output.resolve()}")
            else:
                latest_video.rename(final_output)
                print(f"[OK] Output saved as: {final_output.resolve()}")
        else:
            print(f"[WARNING] Output directory: {outdir_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
