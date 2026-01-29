#!/usr/bin/env python3
"""
Script para analizar el dataset de labels y entender la distribución de datos.
Fase 0: Preparación y análisis.
"""
import json
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Tuple
import argparse


def parse_label_line(line: str) -> Dict:
    """Parsea una línea de label en formato: class x1 y1 x2 y2 conf track_id"""
    parts = line.strip().split()
    if len(parts) < 6:
        return None
    
    result = {
        'class_id': int(parts[0]),
        'bbox': [float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])],
        'confidence': float(parts[5]),
    }
    
    # track_id opcional
    if len(parts) >= 7:
        result['track_id'] = int(parts[6])
    else:
        result['track_id'] = None
    
    return result


def load_labels_from_folder(labels_dir: Path) -> List[Tuple[int, List[Dict]]]:
    """Carga todos los labels de una carpeta, ordenados por nombre de archivo."""
    labels = []
    label_files = sorted(labels_dir.glob("*.txt"), key=lambda p: p.name)
    
    for frame_num, label_file in enumerate(label_files):
        detections = []
        if label_file.exists():
            with open(label_file, 'r') as f:
                for line in f:
                    if line.strip():
                        det = parse_label_line(line)
                        if det:
                            detections.append(det)
        labels.append((frame_num, detections))
    
    return labels


def analyze_dataset(labels_dir: Path, output_file: Path = None):
    """Analiza el dataset y genera estadísticas."""
    print(f"Analizando dataset en: {labels_dir}")
    
    labels = load_labels_from_folder(labels_dir)
    total_frames = len(labels)
    
    if total_frames == 0:
        print("❌ No se encontraron archivos de labels")
        return
    
    print(f"✅ Encontrados {total_frames} frames")
    
    # Estadísticas
    class_counts = Counter()
    class_with_tracking = defaultdict(set)
    confidences_by_class = defaultdict(list)
    track_ids_seen = set()
    frames_with_area = []
    frames_with_cajas = []
    frames_with_folio = []
    
    for frame_num, detections in labels:
        for det in detections:
            class_id = det['class_id']
            class_counts[class_id] += 1
            confidences_by_class[class_id].append(det['confidence'])
            
            if det['track_id'] is not None:
                class_with_tracking[class_id].add(det['track_id'])
                track_ids_seen.add(det['track_id'])
            
            # Identificar frames con áreas de trabajo (asumiendo clases 0 o 1)
            if class_id in [0, 1]:  # Ajustar según tu mapeo real
                frames_with_area.append(frame_num)
            
            # Identificar frames con objetos de interés (asumiendo clases 2 o 3)
            if class_id in [2, 3]:  # Ajustar según tu mapeo real
                frames_with_cajas.append(frame_num)
            elif class_id in [4, 5]:  # Ajustar según tu mapeo real
                frames_with_folio.append(frame_num)
    
    # Reporte
    print("\n" + "="*60)
    print("ESTADÍSTICAS DEL DATASET")
    print("="*60)
    
    print(f"\n📊 Total de frames: {total_frames}")
    print(f"📦 Total de detecciones: {sum(class_counts.values())}")
    print(f"🆔 Total de track IDs únicos: {len(track_ids_seen)}")
    
    print(f"\n📈 Distribución de clases:")
    for class_id, count in sorted(class_counts.items()):
        avg_conf = sum(confidences_by_class[class_id]) / len(confidences_by_class[class_id]) if confidences_by_class[class_id] else 0
        tracking_count = len(class_with_tracking[class_id])
        print(f"  Clase {class_id}: {count:4d} detecciones | "
              f"Confianza promedio: {avg_conf:.3f} | "
              f"Con tracking: {tracking_count} IDs únicos")
    
    print(f"\n🎯 Frames con áreas de trabajo: {len(set(frames_with_area))} frames únicos")
    print(f"📦 Frames con cajas: {len(set(frames_with_cajas))} frames únicos")
    print(f"📄 Frames con folio: {len(set(frames_with_folio))} frames únicos")
    
    # Análisis de tracking
    print(f"\n🔗 Análisis de Tracking:")
    tracking_consistency = {}
    for class_id in class_with_tracking:
        ids = class_with_tracking[class_id]
        if len(ids) > 0:
            # Calcular cuántas veces cambia el ID (aproximado)
            # Esto requeriría análisis frame por frame, por ahora solo estadísticas básicas
            tracking_consistency[class_id] = {
                'unique_ids': len(ids),
                'total_detections': class_counts[class_id],
                'avg_detections_per_id': class_counts[class_id] / len(ids) if len(ids) > 0 else 0
            }
            print(f"  Clase {class_id}: {len(ids)} IDs únicos, "
                  f"promedio {tracking_consistency[class_id]['avg_detections_per_id']:.1f} detecciones por ID")
    
    # Guardar resultados
    if output_file:
        results = {
            'total_frames': total_frames,
            'total_detections': sum(class_counts.values()),
            'class_distribution': dict(class_counts),
            'class_avg_confidence': {
                cid: sum(confidences_by_class[cid]) / len(confidences_by_class[cid])
                for cid in confidences_by_class
            },
            'tracking_stats': tracking_consistency,
            'frames_with_area': len(set(frames_with_area)),
            'frames_with_cajas': len(set(frames_with_cajas)),
            'frames_with_folio': len(set(frames_with_folio)),
        }
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Resultados guardados en: {output_file}")
    
    print("\n" + "="*60)
    print("⚠️  IMPORTANTE: Ajusta los IDs de clases en el código según tu mapeo real")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description="Analiza el dataset de labels")
    parser.add_argument(
        "--labels-dir",
        type=Path,
        required=True,
        help="Directorio con archivos .txt de labels"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Archivo JSON de salida con resultados"
    )
    
    args = parser.parse_args()
    
    if not args.labels_dir.exists():
        print(f"❌ Error: Directorio no existe: {args.labels_dir}")
        return 1
    
    analyze_dataset(args.labels_dir, args.output)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

