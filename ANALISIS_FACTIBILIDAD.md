# Análisis de Factibilidad y Plan de Ejecución

## 1. Análisis de Factibilidad del Plan

### 1.1 Factibilidad Técnica: ✅ ALTA

**Fortalezas:**
- ✅ **Datos disponibles**: Ya tienes dataset procesado con labels y tracking
- ✅ **Formato conocido**: Labels en formato estándar (class, bbox, conf, track_id)
- ✅ **Infraestructura base**: Código existente para procesar frames
- ✅ **Tecnologías estándar**: Python, OpenCV, YOLO (ya en uso)
- ✅ **Requisitos claros**: Reglas de negocio bien definidas

**Complejidad Estimada:**
- **Baja**: Módulos de área, filtrado, logging básico
- **Media**: Tracking ligero, detección de eventos, manejo de oclusiones
- **Alta**: Validación robusta, manejo de errores avanzado, optimizaciones

### 1.2 Riesgos Identificados

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Tracking inconsistente | Alta | Medio | No depender 100% de track_id, usar fallback espacial |
| Falsos positivos/negativos | Media | Alto | Validación temporal y filtros de confianza |
| Oclusiones complejas | Media | Medio | Timeout ajustable y memoria temporal |
| Performance en edge | Baja | Medio | Optimizaciones graduales, profiling continuo |
| Parámetros difíciles de ajustar | Media | Medio | Sistema de configuración flexible, pruebas iterativas |

### 1.3 Dependencias y Requisitos

**Dependencias Existentes (ya disponibles):**
- Python 3.x
- OpenCV (cv2)
- Ultralytics (YOLO)
- Pathlib (estándar)

**Dependencias a Agregar:**
- `numpy` - Cálculos de bbox, IoU, distancias
- `dataclasses` o `pydantic` - Estructuras de datos (opcional, puede usar dicts)
- `json` - Logging (estándar)
- `typing` - Type hints (estándar)

**NO se requieren:**
- ❌ Librerías pesadas de tracking (implementaremos tracking ligero)
- ❌ Kalman filters complejos (solo si se necesita Enfoque 3)
- ❌ Bases de datos (logs en archivos JSON/JSONL)

### 1.4 Estimación de Esfuerzo

**Fase 1 (MVP Básico)**: 2-3 días
- Módulos fundamentales
- Conteo simple sin validación avanzada

**Fase 2 (Funcional)**: 3-5 días
- Tracking ligero
- Detección de eventos básica
- Manejo de oclusiones simple

**Fase 3 (Robusto)**: 5-7 días
- Validaciones avanzadas
- Manejo de errores
- Logging completo

**Fase 4 (Optimización)**: 2-3 días
- Ajuste de parámetros
- Optimizaciones de performance
- Testing exhaustivo

**Total estimado**: 12-18 días de desarrollo (dependiendo de experiencia y tiempo disponible)

---

## 2. Plan de Ejecución Incremental

### Fase 0: Preparación y Análisis (1 día)

**Objetivo**: Entender el dataset y establecer baseline

**Tareas:**
1. ✅ **Análisis de datos**
   - Revisar distribución de clases en labels
   - Identificar patrones de tracking (consistencia de IDs)
   - Analizar variabilidad de áreas de trabajo
   - Contar frames y duración de secuencias

2. ✅ **Mapeo de clases**
   - Crear diccionario clase_id → nombre_clase
   - Identificar qué IDs corresponden a: cajas, folio, area_de_trabajo, persona, etc.

3. ✅ **Herramientas de visualización básica**
   - Script para visualizar detecciones en frames
   - Script para analizar estadísticas de labels

4. ✅ **Ground truth manual (subset)**
   - Anotar manualmente conteo en 10-20 frames clave
   - Identificar frames con eventos (entrada/salida)
   - Crear dataset de validación pequeño

**Entregables:**
- `utils/analyze_dataset.py` - Script de análisis
- `data/ground_truth_sample.json` - Ground truth manual
- `docs/dataset_analysis.md` - Reporte de análisis

**Criterio de éxito**: Entender bien el dataset y tener subset de validación

---

### Fase 1: MVP - Conteo Básico (2-3 días)

**Objetivo**: Sistema mínimo que cuenta objetos dentro del área

**Tareas:**

#### 1.1 Módulo de Parsing (Día 1, mañana)
- [ ] `core/parsers.py`
  - Función para leer labels de un frame
  - Parsear formato: `class x1 y1 x2 y2 conf track_id`
  - Estructura de datos: `Detection` (dataclass o dict)

#### 1.2 Módulo de Área de Trabajo (Día 1, tarde)
- [ ] `core/area_detector.py`
  - Detectar áreas de trabajo en frame
  - Seleccionar área válida (más grande y centrada)
  - Cachear área (asumir estática)
  - Función: `is_bbox_inside_area(bbox, area_bbox)` → bool

#### 1.3 Módulo de Filtrado (Día 2, mañana)
- [ ] `core/filter.py`
  - Filtrar solo objetos de interés (cajas, folio)
  - Filtrar por confianza mínima
  - Filtrar objetos completamente dentro del área
  - Función: `filter_valid_objects(detections, area, min_conf)` → list

#### 1.4 Conteo Simple (Día 2, tarde)
- [ ] Extender `core/counter.py`
  - Contar objetos válidos en frame actual
  - Sin tracking, sin memoria temporal
  - Solo: `count = len(filtered_objects)`

#### 1.5 Pipeline Básico (Día 3)
- [ ] `core/pipeline.py` o `main.py`
  - Loop sobre frames secuenciales
  - Aplicar pipeline: parse → detect_area → filter → count
  - Mostrar conteo por frame
  - Guardar resultados simples

**Entregables:**
- Sistema que cuenta objetos por frame (sin validación)
- Output: frame_num, conteo_bruto
- Visualización básica del conteo

**Criterio de éxito**: Sistema cuenta objetos correctamente en frames sin eventos complejos

**Testing:**
- Probar en 10-20 frames
- Comparar con conteo manual
- Identificar casos donde falla (para siguiente fase)

---

### Fase 2: Tracking y Eventos Básicos (3-4 días)

**Objetivo**: Detectar entradas y salidas con tracking ligero

**Tareas:**

#### 2.1 Tracking Ligero (Día 4-5)
- [ ] `core/tracker.py`
  - Clase `ObjectTracker`
  - Asociación de objetos entre frames:
    - Primero por track_id (si disponible)
    - Fallback por distancia espacial (IoU o distancia centro)
  - Estados básicos: `FUERA`, `DENTRO`
  - Memoria de objetos activos (últimos N frames)

#### 2.2 Detección de Eventos (Día 5-6)
- [ ] `core/event_detector.py`
  - Detectar transición FUERA → DENTRO (entrada)
  - Detectar transición DENTRO → FUERA (salida)
  - Validación básica: persistencia 2-3 frames
  - Histéresis simple

#### 2.3 Integración con Counter (Día 6)
- [ ] Actualizar `core/counter.py`
  - Mantener contador que se incrementa/decrementa por eventos
  - No solo contar objetos visibles, sino trackear estado

#### 2.4 Pipeline Mejorado (Día 7)
- [ ] Actualizar pipeline
  - Integrar tracking y detección de eventos
  - Aplicar eventos al contador
  - Mostrar: conteo_actual, eventos_detectados

**Entregables:**
- Sistema que detecta entradas/salidas
- Contador que se actualiza por eventos
- Logging básico de eventos

**Criterio de éxito**: Detecta correctamente entradas y salidas en casos simples

**Testing:**
- Probar en secuencias con eventos claros
- Validar que no cuenta movimiento interno
- Identificar problemas con tracking

---

### Fase 3: Robustez y Oclusiones (3-4 días)

**Objetivo**: Manejar oclusiones y errores del detector

**Tareas:**

#### 3.1 Manejo de Oclusiones (Día 8-9)
- [ ] Extender `core/tracker.py`
  - Estado `OCLUIDO`
  - Memoria de objetos ocluidos
  - Timeout de oclusión (10 frames)
  - Lógica: objeto desaparece → esperar timeout → decidir si salida u oclusión

#### 3.2 Validaciones Avanzadas (Día 9-10)
- [ ] `core/validator.py`
  - Validar eventos con señales auxiliares (persona, producto_en_mano)
  - Filtro de confianza más estricto
  - Validación de persistencia temporal
  - Detección de falsos positivos básica

#### 3.3 Smoothing Temporal (Día 10)
- [ ] `core/smoother.py`
  - Buffer circular de últimos N frames
  - Filtro de mediana para suavizar conteo
  - Validación retroactiva de eventos

#### 3.4 Manejo de Errores (Día 11)
- [ ] Extender todos los módulos
  - Manejo de casos edge
  - Validación de límites (máximo 1 evento por frame)
  - Recuperación de tracking perdido

**Entregables:**
- Sistema robusto a oclusiones
- Manejo de errores básico
- Conteo más estable

**Criterio de éxito**: Maneja correctamente oclusiones y errores comunes

**Testing:**
- Probar con frames que tienen oclusiones
- Probar con falsos positivos/negativos
- Validar estabilidad del conteo

---

### Fase 4: Logging, Métricas y Optimización (2-3 días)

**Objetivo**: Sistema completo con monitoreo y ajuste fino

**Tareas:**

#### 4.1 Sistema de Logging (Día 12)
- [ ] `core/logger.py`
  - Formato JSON Lines para eventos
  - Niveles de logging (mínimo, estándar, verbose)
  - Contexto completo en cada evento
  - Archivos organizados

#### 4.2 Métricas y Evaluación (Día 13)
- [ ] `core/metrics.py`
  - Calcular precisión vs ground truth
  - Métricas de eventos (precision, recall)
  - Reportes de errores
  - Visualización de métricas

#### 4.3 Configuración Flexible (Día 14)
- [ ] `config/counter_config.py`
  - Parámetros ajustables (timeouts, umbrales, etc.)
  - Archivo de configuración YAML/JSON
  - Validación de parámetros

#### 4.4 Optimización y Ajuste (Día 14-15)
- [ ] Profiling de performance
- [ ] Ajuste de parámetros con dataset de validación
- [ ] Optimizaciones básicas (caché, reducción de cálculos)

**Entregables:**
- Sistema completo con logging
- Métricas de evaluación
- Configuración flexible
- Documentación de uso

**Criterio de éxito**: Sistema listo para producción con monitoreo

**Testing:**
- Evaluación completa con ground truth
- Análisis de errores
- Ajuste de parámetros

---

## 3. Estructura de Código Propuesta

```
counterV01/
├── core/
│   ├── __init__.py
│   ├── counter.py          # Contador principal (extender)
│   ├── parsers.py           # Parseo de labels
│   ├── area_detector.py     # Detección de área de trabajo
│   ├── filter.py            # Filtrado de objetos
│   ├── tracker.py           # Tracking ligero
│   ├── event_detector.py    # Detección de eventos
│   ├── validator.py         # Validaciones avanzadas
│   ├── smoother.py          # Smoothing temporal
│   ├── logger.py            # Sistema de logging
│   ├── metrics.py           # Métricas y evaluación
│   └── pipeline.py          # Pipeline principal
├── config/
│   ├── __init__.py
│   ├── settings.py          # Configuraciones generales
│   └── counter_config.py    # Configuración del contador
├── utils/
│   ├── analyze_dataset.py   # Análisis de dataset
│   ├── visualize.py         # Visualización de resultados
│   └── ... (existente)
├── tests/
│   ├── test_parsers.py
│   ├── test_area.py
│   ├── test_tracker.py
│   ├── test_events.py
│   └── ... (extender)
├── scripts/
│   ├── run_counter.py       # Script principal de ejecución
│   ├── evaluate.py          # Script de evaluación
│   └── visualize_results.py # Visualización
└── logs/                    # Logs generados
```

---

## 4. Priorización y Decisiones

### 4.1 ¿Qué Implementar Primero?

**CRÍTICO (Fase 1):**
1. Parsing de labels ✅
2. Detección de área ✅
3. Filtrado básico ✅
4. Conteo simple ✅

**IMPORTANTE (Fase 2):**
5. Tracking ligero
6. Detección de eventos
7. Integración con contador

**NECESARIO (Fase 3):**
8. Manejo de oclusiones
9. Validaciones básicas
10. Smoothing temporal

**DESEABLE (Fase 4):**
11. Logging completo
12. Métricas avanzadas
13. Optimizaciones

### 4.2 Decisiones de Diseño

**Tracking:**
- ✅ **Decisión**: Empezar con tracking ligero (Enfoque 1)
- ✅ **Razón**: Balance complejidad/precisión, funciona con tracking imperfecto
- ⚠️ **Alternativa**: Si tracking falla mucho, considerar Enfoque 2 (eventos)

**Memoria Temporal:**
- ✅ **Decisión**: Buffer de 10-15 frames (~1-1.5 segundos)
- ✅ **Razón**: Suficiente para validación, no excesivo en memoria

**Validación de Eventos:**
- ✅ **Decisión**: Persistencia de 2-3 frames para confirmar evento
- ✅ **Razón**: Balance entre latencia y robustez

**Señales Auxiliares:**
- ✅ **Decisión**: Usar como validación opcional, no requerida
- ✅ **Razón**: `producto_en_mano` es poco confiable, no depender 100%

---

## 5. Plan de Validación Continua

### 5.1 Testing por Fase

**Fase 1:**
- [ ] Test unitario: parsing de labels
- [ ] Test unitario: detección de área
- [ ] Test unitario: filtrado
- [ ] Test integración: pipeline básico en 10 frames

**Fase 2:**
- [ ] Test unitario: asociación de objetos
- [ ] Test unitario: detección de eventos
- [ ] Test integración: secuencia con eventos claros
- [ ] Validación manual: comparar con ground truth

**Fase 3:**
- [ ] Test: manejo de oclusiones
- [ ] Test: falsos positivos/negativos
- [ ] Test: tracking inconsistente
- [ ] Validación: secuencia completa

**Fase 4:**
- [ ] Evaluación completa con métricas
- [ ] Análisis de errores
- [ ] Ajuste de parámetros

### 5.2 Métricas de Progreso

**Por fase, medir:**
- Precisión del conteo (% frames correctos)
- Precisión de eventos (entradas/salidas)
- Tiempo de procesamiento por frame
- Cobertura de casos edge

---

## 6. Riesgos y Mitigaciones

### 6.1 Riesgos Técnicos

**Riesgo: Tracking muy inconsistente**
- **Mitigación**: Implementar fallback espacial robusto desde inicio
- **Plan B**: Si falla, cambiar a Enfoque 2 (eventos)

**Riesgo: Parámetros difíciles de ajustar**
- **Mitigación**: Sistema de configuración flexible desde Fase 2
- **Plan B**: Usar valores conservadores por defecto

**Riesgo: Performance lenta**
- **Mitigación**: Profiling desde Fase 3, optimizaciones graduales
- **Plan B**: Reducir tamaño de buffers, simplificar cálculos

### 6.2 Riesgos de Alcance

**Riesgo: Requisitos cambian**
- **Mitigación**: Arquitectura modular, fácil de extender
- **Plan B**: Priorizar funcionalidad core, features opcionales después

**Riesgo: Dataset insuficiente para validar**
- **Mitigación**: Crear ground truth manual en Fase 0
- **Plan B**: Usar validación visual y ajuste iterativo

---

## 7. Próximos Pasos Inmediatos

### 7.1 Esta Semana (Fase 0 + Inicio Fase 1)

1. **Hoy/Día 1:**
   - [ ] Crear `utils/analyze_dataset.py`
   - [ ] Analizar distribución de clases
   - [ ] Crear mapeo clase_id → nombre
   - [ ] Anotar 10-20 frames manualmente (ground truth)

2. **Día 2-3:**
   - [ ] Implementar `core/parsers.py`
   - [ ] Implementar `core/area_detector.py`
   - [ ] Test básico de parsing y área

3. **Día 4-5:**
   - [ ] Implementar `core/filter.py`
   - [ ] Extender `core/counter.py` con conteo simple
   - [ ] Pipeline básico funcionando

### 7.2 Próxima Semana (Fase 2)

- Tracking ligero
- Detección de eventos
- Integración completa

---

## 8. Checklist de Inicio

Antes de empezar Fase 1, asegurar:

- [ ] Entender formato de labels completamente
- [ ] Tener subset de validación (10-20 frames anotados)
- [ ] Mapeo de clases definido
- [ ] Entorno de desarrollo configurado
- [ ] Estructura de carpetas creada
- [ ] Dependencias instaladas (numpy mínimo)

---

**Fin del Análisis**

