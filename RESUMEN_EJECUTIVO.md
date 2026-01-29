# Resumen Ejecutivo: Plan de Desarrollo del Sistema de Conteo

## Factibilidad: ✅ ALTA

El plan es **totalmente factible** con los recursos disponibles. Tienes:
- ✅ Dataset procesado con labels y tracking
- ✅ Infraestructura base (Python, YOLO, OpenCV)
- ✅ Requisitos claros y bien definidos
- ✅ Reglas de negocio simples (1 objeto a la vez)

**Estimación total**: 12-18 días de desarrollo incremental

---

## Estrategia Recomendada: Desarrollo Incremental

### Fase 0: Preparación (1 día) → **EMPEZAR AQUÍ**
- Analizar dataset
- Crear ground truth manual (10-20 frames)
- Mapear clases

### Fase 1: MVP Básico (2-3 días)
- Parsing de labels
- Detección de área
- Filtrado y conteo simple
- **Resultado**: Sistema que cuenta objetos por frame

### Fase 2: Tracking y Eventos (3-4 días)
- Tracking ligero
- Detección entrada/salida
- **Resultado**: Sistema que detecta eventos y actualiza contador

### Fase 3: Robustez (3-4 días)
- Manejo de oclusiones
- Validaciones avanzadas
- **Resultado**: Sistema robusto a errores

### Fase 4: Producción (2-3 días)
- Logging completo
- Métricas y evaluación
- Optimización
- **Resultado**: Sistema listo para producción

---

## Decisiones Clave

1. **Enfoque**: Tracking Ligero (Enfoque 1 del plan) - balance óptimo
2. **Memoria**: Buffer de 10-15 frames (~1-1.5 segundos)
3. **Validación**: Persistencia de 2-3 frames para eventos
4. **Señales auxiliares**: Opcionales, no requeridas

---

## Próximos Pasos Inmediatos

### HOY (Fase 0):
1. Crear script de análisis de dataset
2. Mapear clases (qué ID = qué clase)
3. Anotar 10-20 frames manualmente para validación

### ESTA SEMANA (Fase 1):
1. Implementar parsing de labels
2. Implementar detección de área
3. Implementar filtrado básico
4. Conteo simple funcionando

---

## Estructura de Código

```
core/
  ├── parsers.py        # Fase 1
  ├── area_detector.py  # Fase 1
  ├── filter.py         # Fase 1
  ├── tracker.py        # Fase 2
  ├── event_detector.py # Fase 2
  ├── validator.py      # Fase 3
  └── logger.py         # Fase 4
```

---

## Riesgos Principales y Mitigación

| Riesgo | Mitigación |
|--------|------------|
| Tracking inconsistente | Fallback espacial, no depender 100% de track_id |
| Falsos positivos | Validación temporal + filtros de confianza |
| Parámetros difíciles | Configuración flexible desde Fase 2 |

---

## Criterios de Éxito por Fase

- **Fase 1**: Cuenta objetos correctamente en frames simples
- **Fase 2**: Detecta entradas/salidas en casos claros
- **Fase 3**: Maneja oclusiones y errores comunes
- **Fase 4**: Sistema completo con métricas >90% precisión

---

## Recursos Necesarios

**Dependencias a agregar:**
- `numpy` (cálculos de bbox, IoU)

**NO se necesitan:**
- Librerías pesadas de tracking
- Bases de datos
- Servicios externos

---

**Ver documentos completos:**
- `PLAN_CONTEOS.md` - Plan arquitectónico detallado
- `ANALISIS_FACTIBILIDAD.md` - Análisis completo y plan de ejecución

