# 🚀 Inicio Rápido: Desarrollo del Sistema de Conteo

## 📋 Checklist de Inicio

### Paso 1: Instalar Dependencias (5 minutos)

```bash
# Activar entorno virtual si existe
source venv/bin/activate  # o tu método preferido

# Instalar numpy (única dependencia nueva necesaria)
pip install numpy
```

### Paso 2: Analizar Dataset (15 minutos)

```bash
# Ejecutar análisis del dataset
python scripts/analyze_dataset.py \
    --labels-dir output/frames/pickeoPaletts/secondary/labels \
    --output data/dataset_analysis.json
```

**Qué hacer con los resultados:**
1. Revisar la distribución de clases
2. **IMPORTANTE**: Identificar qué ID corresponde a cada clase:
   - `area_de_trabajo_carro` = ID ?
   - `area_de_trabajo_pallet` = ID ?
   - `cajas` = ID ?
   - `folio` = ID ?
   - `persona` = ID ?
   - etc.

3. Crear archivo de mapeo: `config/class_mapping.json`

### Paso 3: Crear Ground Truth Manual (30-60 minutos)

**Objetivo**: Anotar manualmente el conteo en 10-20 frames clave para validación.

**Formato sugerido** (`data/ground_truth_sample.json`):
```json
{
  "frames": [
    {
      "frame_num": 0,
      "frame_file": "2026-01-28-11-51-31_secondary_camera_0fd47f01.png",
      "conteo_real": 0,
      "eventos": []
    },
    {
      "frame_num": 10,
      "frame_file": "...",
      "conteo_real": 1,
      "eventos": [
        {"tipo": "ENTRADA", "frame": 8, "objeto": "cajas"}
      ]
    }
  ]
}
```

**Frames a anotar:**
- Frame inicial (conteo = 0)
- Frames con eventos claros (entrada/salida)
- Frames con oclusiones (si las identificas)
- Frame final (conteo total)

### Paso 4: Crear Mapeo de Clases (5 minutos)

Crear `config/class_mapping.json`:
```json
{
  "area_de_trabajo_carro": 0,
  "area_de_trabajo_pallet": 1,
  "cajas": 2,
  "carro_vacio": 3,
  "folio": 4,
  "persona": 5,
  "producto_en_mano": 6,
  "transpaleta_sin_pallet": 7,
  "pallet_vacio": 8
}
```

**⚠️ Ajustar según los IDs reales de tu modelo**

---

## 🎯 Plan de Desarrollo (Siguientes Pasos)

### Esta Semana: Fase 1 - MVP Básico

**Día 1-2: Módulos Fundamentales**
- [ ] `core/parsers.py` - Parseo de labels
- [ ] `core/area_detector.py` - Detección de área
- [ ] `core/filter.py` - Filtrado de objetos

**Día 3: Integración**
- [ ] Extender `core/counter.py` con conteo simple
- [ ] Pipeline básico en `main.py` o nuevo script
- [ ] Probar en 10-20 frames

**Resultado esperado**: Sistema que cuenta objetos por frame (sin validación avanzada)

---

## 📚 Documentación Disponible

1. **`PLAN_CONTEOS.md`** - Plan arquitectónico completo
   - Arquitectura detallada
   - 3 estrategias de implementación
   - Lógica de detección de eventos
   - Manejo de oclusiones y errores

2. **`ANALISIS_FACTIBILIDAD.md`** - Análisis y plan de ejecución
   - Factibilidad técnica
   - Plan incremental detallado
   - Estructura de código
   - Riesgos y mitigaciones

3. **`RESUMEN_EJECUTIVO.md`** - Resumen ejecutivo
   - Visión general
   - Decisiones clave
   - Próximos pasos

---

## 🛠️ Estructura de Desarrollo Sugerida

```
core/
  ├── parsers.py          # Fase 1 - Parseo de labels
  ├── area_detector.py    # Fase 1 - Detección de área
  ├── filter.py           # Fase 1 - Filtrado
  ├── counter.py          # Fase 1 - Contador (extender existente)
  ├── tracker.py          # Fase 2 - Tracking ligero
  ├── event_detector.py   # Fase 2 - Detección de eventos
  ├── validator.py        # Fase 3 - Validaciones
  └── logger.py           # Fase 4 - Logging

config/
  ├── class_mapping.json  # Mapeo clase_id → nombre
  └── counter_config.py  # Configuración del contador

scripts/
  ├── analyze_dataset.py  # ✅ Ya creado
  ├── run_counter.py     # Fase 1 - Script principal
  └── evaluate.py        # Fase 4 - Evaluación
```

---

## ✅ Criterios de Éxito por Fase

### Fase 1 (Esta semana)
- ✅ Sistema parsea labels correctamente
- ✅ Detecta área de trabajo
- ✅ Filtra objetos válidos
- ✅ Cuenta objetos por frame
- ✅ Funciona en 10-20 frames de prueba

### Fase 2 (Próxima semana)
- ✅ Tracking ligero funcionando
- ✅ Detecta entradas/salidas básicas
- ✅ Contador se actualiza por eventos

### Fase 3 (Siguiente)
- ✅ Maneja oclusiones
- ✅ Robustez a errores

### Fase 4 (Final)
- ✅ Sistema completo
- ✅ Métricas >90% precisión

---

## 🐛 Troubleshooting

**Problema**: No encuentro las clases correctas
- **Solución**: Revisar análisis del dataset, ajustar mapeo

**Problema**: Tracking muy inconsistente
- **Solución**: Usar fallback espacial (no depender 100% de track_id)

**Problema**: Muchos falsos positivos
- **Solución**: Aumentar umbral de confianza, validación temporal

---

## 📞 Próximos Pasos Inmediatos

1. ✅ Ejecutar `analyze_dataset.py`
2. ✅ Crear `class_mapping.json`
3. ✅ Anotar 10-20 frames manualmente
4. 🚀 Empezar Fase 1: Implementar `parsers.py`

---

**¡Listo para empezar!** 🎉

