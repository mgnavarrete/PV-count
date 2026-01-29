# utils/detec_img.py
import argparse
import re
from pathlib import Path

import cv2
from ultralytics import YOLO


def pick_folder_dialog() -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(title="Select nameroot folder (contains primary_camera/ or secondary_camera/)")
    root.destroy()
    return folder


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def list_images(img_dir: Path):
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    files = [p for p in img_dir.iterdir() if p.is_file() and p.suffix.lower() in exts]
    files.sort(key=lambda p: natural_key(p.name))
    return files


def ensure_dirs(base_out: Path):
    ann_dir = base_out / "annotated"
    lab_dir = base_out / "labels"
    ann_dir.mkdir(parents=True, exist_ok=True)
    lab_dir.mkdir(parents=True, exist_ok=True)
    return ann_dir, lab_dir


def save_labels_txt(txt_path: Path, det_lines: list[str]):
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text("\n".join(det_lines) + ("\n" if det_lines else ""), encoding="utf-8")


def run_on_folder(
    model: YOLO,
    img_dir: Path,
    out_base: Path,
    mode: str,
    conf: float,
    imgsz: int,
    device,
    tracker: str,
):
    images = list_images(img_dir)
    if not images:
        print(f"[WARN] No images found in {img_dir}")
        return

    ann_dir, lab_dir = ensure_dirs(out_base)

    print(f"[INFO] Processing {len(images)} images from: {img_dir}")
    print(f"[INFO] Annotated -> {ann_dir}")
    print(f"[INFO] Labels    -> {lab_dir}")

    for i, img_path in enumerate(images):
        # Ultralytics acepta path directamente
        if mode == "predict":
            results = model.predict(
                source=str(img_path),
                conf=conf,
                imgsz=imgsz,
                device=device,
                verbose=False,
            )
        else:
            results = model.track(
                source=str(img_path),
                conf=conf,
                imgsz=imgsz,
                device=device,
                tracker=tracker,
                persist=True,
                verbose=False,
            )

        r = results[0]

        # 1) Guardar imagen anotada (usamos plot() que devuelve BGR ndarray)
        annotated = r.plot()
        out_img_path = ann_dir / img_path.name
        cv2.imwrite(str(out_img_path), annotated)

        # 2) Guardar labels (uno por frame)
        lines = []
        boxes = r.boxes
        if boxes is not None and len(boxes) > 0:
            xyxy = boxes.xyxy.cpu().numpy()
            cls = boxes.cls.cpu().numpy().astype(int)
            confs = boxes.conf.cpu().numpy()
            ids = None
            if mode == "track" and getattr(boxes, "id", None) is not None:
                ids = boxes.id.cpu().numpy().astype(int)

            for j in range(len(xyxy)):
                x1, y1, x2, y2 = xyxy[j]
                c = int(cls[j])
                cf = float(confs[j])
                if ids is not None:
                    tid = int(ids[j])
                    # class x1 y1 x2 y2 conf track_id
                    lines.append(f"{c} {x1:.2f} {y1:.2f} {x2:.2f} {y2:.2f} {cf:.4f} {tid}")
                else:
                    # class x1 y1 x2 y2 conf
                    lines.append(f"{c} {x1:.2f} {y1:.2f} {x2:.2f} {y2:.2f} {cf:.4f}")

        out_txt_path = lab_dir / f"{img_path.stem}.txt"
        save_labels_txt(out_txt_path, lines)

        if (i + 1) % 200 == 0:
            print(f"  done {i+1}/{len(images)}")

    print(f"[OK] Finished: {img_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["predict", "track"], default="predict")
    ap.add_argument("--conf", type=float, default=0.5)
    ap.add_argument("--imgsz", type=int, default=1024)
    ap.add_argument("--device", default=None, help="e.g. 0, 'cpu'")
    ap.add_argument("--tracker", default="bytetrack.yaml", help="only used in track mode")
    ap.add_argument("--outdir", default="output/frames", help="base output folder")
    args = ap.parse_args()

    root = pick_folder_dialog()
    if not root:
        print("[INFO] No folder selected. Exit.")
        return 0

    root_dir = Path(root).resolve()
    name_root = root_dir.name

    weights = (Path(__file__).resolve().parents[1] / "models" / "MRTN-TRAIN-01.pt").resolve()
    if not weights.exists():
        print(f"[ERROR] Model not found: {weights}")
        return 1

    model = YOLO(str(weights))

    # Detecta cámaras disponibles
    cam_map = {
        "primary": root_dir / "primary_camera" / "img",
        "secondary": root_dir / "secondary_camera" / "img",
    }

    any_found = False
    for cam_name, img_dir in cam_map.items():
        if img_dir.exists():
            any_found = True
            out_base = Path(args.outdir) / name_root / cam_name
            run_on_folder(
                model=model,
                img_dir=img_dir,
                out_base=out_base,
                mode=args.mode,
                conf=args.conf,
                imgsz=args.imgsz,
                device=args.device,
                tracker=args.tracker,
            )
        else:
            print(f"[WARN] Missing: {img_dir}")

    if not any_found:
        print("[ERROR] No primary_camera/img or secondary_camera/img found in selected folder.")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
