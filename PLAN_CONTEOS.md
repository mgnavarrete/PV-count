# Plan de Arquitectura: Sistema de Conteo en Tiempo Real

## 1. Arquitectura del Pipeline

### 1.1 Módulos Principales

```
┌─────────────────────────────────────────────────────────────┐
│                    INPUT LAYER                              │
│  - Frame Loader (secuencial, ~10 FPS)                      │
│  - Detections Parser (bbox, class, conf, track_id)          │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              AREA VALIDATION MODULE                          │
│  - Detectar área de trabajo (area_de_trabajo_pallet/carro)  │
│  - Seleccionar área válida (más grande y centrada)          │
│  - Calcular región de interés (ROI) estática                │
│  - Cachear área para evitar recálculo                      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│           OBJECT FILTERING MODULE                           │
│  - Filtrar solo objetos de interés (cajas, folio)          │
│  - Filtrar por confianza mínima                            │
│  - Validar que bbox esté completamente dentro del área       │
│  - Calcular IoU con área de trabajo                        │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│         TRACKING & STATE MANAGEMENT                          │
│  (Estrategia dependiente del enfoque elegido)               │
│  - Tracking ligero / Memoria temporal                       │
│  - Gestión de estados (dentro/fuera/transición)            │
│  - Historial de objetos                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│          EVENT DETECTION MODULE                              │
│  - Detectar entrada al área                                 │
│  - Detectar salida del área                                 │
│  - Distinguir movimiento interno vs entrada/salida          │
│  - Validar eventos con heurísticas temporales               │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│         OCCLUSION HANDLING MODULE                           │
│  - Detectar oclusiones (objeto desaparece pero debe contar)  │
│  - Mantener memoria de objetos ocluidos                     │
│  - Timeout para objetos ocluidos                            │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│         ERROR RECOVERY MODULE                                │
│  - Manejar falsos positivos/negativos                       │
│  - Smoothing temporal (filtros, histéresis)                 │
│  - Validación cruzada de eventos                            │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│         COUNTING ENGINE                                      │
│  - Mantener contador actual                                 │
│  - Aplicar reglas de negocio                                │
│  - Generar eventos de conteo                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│         LOGGING & MONITORING                                 │
│  - Registrar eventos con contexto                           │
│  - Métricas de rendimiento                                  │
│  - Debugging info                                           │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Flujo de Datos por Frame

1. **Parseo**: Leer frame y detecciones del archivo de labels
2. **Área**: Identificar y validar área de trabajo (una vez, luego cachear)
3. **Filtrado**: Extraer solo cajas/folio completamente dentro del área
4. **Tracking/Asociación**: Asociar detecciones actuales con historial
5. **Eventos**: Detectar cambios de estado (entrada/salida)
6. **Oclusión**: Verificar objetos que desaparecieron pero deben seguir contando
7. **Conteo**: Actualizar contador según eventos validados
8. **Logging**: Registrar eventos y métricas

---

## 2. Estrategias de Implementación

### 2.1 Enfoque 1: Tracking Ligero con Memoria Temporal (RECOMENDADO)

**Filosofía**: Usar tracking IDs cuando estén disponibles, pero complementar con tracking ligero basado en posición/aparición temporal.

#### Componentes Clave:

**A. Estado de Objetos**
- Cada objeto tiene un estado: `FUERA`, `ENTRANDO`, `DENTRO`, `SALIENDO`, `OCLUIDO`
- Máquina de estados con transiciones validadas temporalmente

**B. Memoria Temporal**
- Buffer circular de últimos N frames (ej: 10-15 frames = ~1-1.5 segundos)
- Para cada frame: lista de objetos detectados con posición, confianza, track_id
- Historial de objetos "activos" (vistos recientemente)

**C. Asociación de Objetos**
- **Primero**: Intentar asociar por track_id (si está disponible y consistente)
- **Segundo**: Si track_id falla o no existe, usar asociación por:
  - Distancia euclidiana del centroide (IoU o distancia centro)
  - Proximidad temporal (objeto visto en frame anterior)
  - Tamaño similar (área del bbox)

**D. Detección de Entrada/Salida**
- **Entrada**: Objeto pasa de `FUERA` → `ENTRANDO` → `DENTRO`
  - Validación: bbox completamente dentro del área + persistencia por N frames
  - Histéresis: requiere 2-3 frames consecutivos dentro para confirmar entrada
- **Salida**: Objeto pasa de `DENTRO` → `SALIENDO` → `FUERA`
  - Validación: bbox completamente fuera del área + persistencia por N frames
  - Histéresis: requiere 2-3 frames consecutivos fuera para confirmar salida

**E. Manejo de Oclusiones**
- Cuando un objeto en estado `DENTRO` desaparece:
  - Esperar timeout (ej: 5-10 frames = 0.5-1 segundo)
  - Si reaparece dentro del timeout → mantener estado `DENTRO` (fue oclusión)
  - Si no reaparece → transición a `FUERA` (fue salida real)
- Mantener lista de objetos ocluidos con timestamp de última detección

**F. Robustez a Errores**
- **Falsos positivos**: Validar con confianza mínima + persistencia temporal
- **Falsos negativos**: Usar memoria temporal para "rellenar" frames perdidos
- **Tracking inconsistente**: No depender 100% de track_id, usar fallback espacial

#### Ventajas:
- ✅ Balance entre precisión y complejidad
- ✅ Funciona incluso con tracking imperfecto
- ✅ Maneja oclusiones de forma natural
- ✅ Bajo overhead computacional

#### Desventajas:
- ⚠️ Requiere tuning de parámetros (timeouts, histéresis)
- ⚠️ Puede tener latencia pequeña en detección de eventos (2-3 frames)

---

### 2.2 Enfoque 2: Conteo por Eventos con Validación Multi-Señal

**Filosofía**: En lugar de trackear objetos individuales, detectar eventos de entrada/salida usando múltiples señales auxiliares.

#### Componentes Clave:

**A. Señales de Evento**
- **Señal principal**: Cambio en número de objetos dentro del área (frame a frame)
- **Señal auxiliar 1**: Presencia de `producto_en_mano` (indica actividad)
- **Señal auxiliar 2**: Presencia de `persona` cerca del área
- **Señal auxiliar 3**: Cambio en área total ocupada por objetos

**B. Detección de Eventos**
- **Entrada detectada** cuando:
  - Número de objetos dentro aumenta
  - Y (`producto_en_mano` presente O `persona` cerca)
  - Y cambio es persistente (2-3 frames)
- **Salida detectada** cuando:
  - Número de objetos dentro disminuye
  - Y (`producto_en_mano` presente O `persona` cerca)
  - Y cambio es persistente (2-3 frames)

**C. Validación Temporal**
- Buffer de últimos M frames con conteo de objetos
- Aplicar filtro de mediana o promedio móvil para suavizar saltos
- Solo confirmar evento si persiste después del filtrado

**D. Manejo de Oclusiones**
- Mantener "conteo estimado" basado en última detección visible
- Si objeto desaparece pero `persona` está presente → asumir oclusión temporal
- Timeout: si no hay actividad de `persona` por X frames → decrementar conteo

**E. Robustez a Errores**
- Usar múltiples señales reduce dependencia de una sola fuente
- Filtros temporales suavizan falsos positivos/negativos
- Validación cruzada entre señales

#### Ventajas:
- ✅ Más simple conceptualmente
- ✅ No requiere tracking complejo
- ✅ Usa señales auxiliares disponibles
- ✅ Menor memoria requerida

#### Desventajas:
- ⚠️ Menos preciso si señales auxiliares fallan frecuentemente
- ⚠️ Puede confundirse con movimiento interno
- ⚠️ Depende de calidad de detección de `producto_en_mano` y `persona`

---

### 2.3 Enfoque 3: Híbrido con Tracking Robusto y Validación de Eventos

**Filosofía**: Combinar tracking robusto (múltiples hipótesis) con validación de eventos usando señales auxiliares.

#### Componentes Clave:

**A. Tracking Multi-Hipótesis**
- Mantener múltiples hipótesis de asociación para cada objeto
- Usar Kalman Filter ligero para predecir posición
- Asociación por IoU + predicción de movimiento

**B. Validación de Eventos con Señales**
- Similar a Enfoque 2, pero aplicado a objetos trackeados individualmente
- Cada objeto tiene probabilidad de estar dentro/fuera
- Evento confirmado solo si:
  - Tracking indica transición clara
  - Y señal auxiliar (`producto_en_mano` o `persona`) confirma actividad

**C. Manejo de Oclusiones Avanzado**
- Usar predicción de Kalman para estimar posición durante oclusión
- Si predicción indica que objeto sigue dentro → mantener estado `OCLUIDO`
- Timeout basado en incertidumbre de predicción

**D. Robustez a Errores**
- Múltiples hipótesis permiten recuperación de tracking perdido
- Validación cruzada entre tracking y señales auxiliares
- Filtros de suavizado temporal

#### Ventajas:
- ✅ Mayor precisión potencial
- ✅ Manejo robusto de oclusiones
- ✅ Recuperación de tracking perdido

#### Desventajas:
- ⚠️ Mayor complejidad computacional
- ⚠️ Más difícil de implementar y depurar
- ⚠️ Puede ser excesivo para el problema

---

## 3. Lógica Detallada: Detección de Entrada/Salida vs Movimiento Interno

### 3.1 Criterios para Entrada

**Condiciones necesarias (todas deben cumplirse):**
1. **Posición**: Bbox completamente dentro del área de trabajo (IoU con área = 1.0 o muy cercano)
2. **Novedad**: Objeto no estaba en estado `DENTRO` en frame anterior
3. **Persistencia**: Objeto permanece dentro por al menos N frames consecutivos (ej: N=2 o 3)
4. **Validación opcional**: Presencia de `persona` o `producto_en_mano` en frames cercanos

**Algoritmo:**
```
Para cada objeto detectado en frame actual:
  Si bbox completamente dentro del área:
    Si objeto NO estaba en memoria (nuevo):
      Agregar a lista de "candidatos a entrada"
      Inicializar contador de persistencia = 1
    Si objeto YA estaba en memoria con estado != DENTRO:
      Incrementar contador de persistencia
      Si contador >= N:
        Confirmar ENTRADA
        Cambiar estado a DENTRO
        Incrementar contador global
    Si objeto YA estaba en estado DENTRO:
      Mantener estado (movimiento interno)
```

### 3.2 Criterios para Salida

**Condiciones necesarias:**
1. **Posición**: Bbox completamente fuera del área de trabajo (IoU con área = 0.0 o muy bajo)
2. **Estado previo**: Objeto estaba en estado `DENTRO` o `OCLUIDO`
3. **Persistencia**: Objeto permanece fuera por al menos M frames consecutivos (ej: M=2 o 3)
4. **Validación opcional**: Presencia de `persona` o `producto_en_mano` en frames cercanos

**Algoritmo:**
```
Para cada objeto en memoria con estado DENTRO o OCLUIDO:
  Si objeto NO detectado en frame actual:
    Incrementar contador de "frames sin detectar"
    Si contador >= timeout_oclusion:
      Confirmar SALIDA (fue oclusión que terminó en salida)
      Cambiar estado a FUERA
      Decrementar contador global
  Si objeto detectado pero bbox fuera del área:
    Incrementar contador de persistencia fuera
    Si contador >= M:
      Confirmar SALIDA
      Cambiar estado a FUERA
      Decrementar contador global
```

### 3.3 Distinción de Movimiento Interno

**Movimiento interno** se identifica cuando:
- Objeto está en estado `DENTRO`
- Bbox se mueve pero sigue completamente dentro del área
- No hay cambio de estado (permanece `DENTRO`)

**Estrategia:**
- No generar eventos para movimiento interno
- Solo actualizar posición en memoria
- Mantener estado `DENTRO` sin cambios

---

## 4. Manejo de Oclusiones

### 4.1 Detección de Oclusión

**Oclusión detectada cuando:**
- Objeto en estado `DENTRO` desaparece de las detecciones
- Pero NO hay señal de salida (bbox no se movió hacia fuera antes de desaparecer)
- Y hay actividad reciente (objeto visto en últimos X frames)

### 4.2 Estrategia de Manejo

**A. Memoria de Objetos Ocluidos**
```
Estructura:
{
  track_id o id_interno: int,
  ultima_posicion: (x, y, w, h),
  ultimo_frame_visto: int,
  frames_ocluido: int,
  estado: OCLUIDO
}
```

**B. Timeout de Oclusión**
- Inicializar `frames_ocluido = 0` cuando objeto desaparece
- Incrementar cada frame que no se detecta
- Si `frames_ocluido >= TIMEOUT_OCLUSION` (ej: 10 frames = 1 segundo):
  - Asumir que objeto fue retirado (salida real)
  - Cambiar estado a `FUERA`
  - Decrementar contador

**C. Reaparición**
- Si objeto reaparece dentro del timeout:
  - Si nueva posición está dentro del área → mantener `DENTRO`
  - Si nueva posición está fuera → transición a `FUERA` (fue salida)

**D. Validación con Señales Auxiliares**
- Si `persona` está presente durante oclusión → aumentar timeout (actividad en curso)
- Si `persona` no está presente → timeout normal (menos probable que sea oclusión)

### 4.3 Casos Especiales

**Apilado múltiple:**
- Si varios objetos desaparecen simultáneamente → posible apilado
- Mantener todos en estado `OCLUIDO` con timeout individual
- No decrementar contador hasta que todos excedan timeout

**Oclusión parcial:**
- Si bbox se reduce significativamente pero sigue dentro → posible oclusión parcial
- Mantener objeto en `DENTRO` (sigue contando)

---

## 5. Manejo de Fallas del Detector

### 5.1 Falsos Positivos

**Detección:**
- Objeto detectado con confianza baja
- Objeto aparece y desaparece rápidamente (no persistente)
- Objeto en posición improbable (fuera de contexto esperado)

**Mitigación:**
- **Filtro de confianza**: Solo considerar objetos con confianza > umbral (ej: 0.6)
- **Filtro de persistencia**: Requerir N frames consecutivos antes de confirmar
- **Validación espacial**: Verificar que posición sea consistente con movimiento esperado
- **Validación con señales**: Si `persona` no está presente, ser más estricto

### 5.2 Falsos Negativos

**Detección:**
- Objeto conocido desaparece sin razón aparente
- Conteo disminuye inesperadamente
- Objeto debería estar visible pero no se detecta

**Mitigación:**
- **Memoria temporal**: Mantener objetos en memoria por X frames después de desaparecer
- **Predicción de posición**: Si tracking disponible, predecir posición esperada
- **Suavizado temporal**: Usar filtro de mediana en conteo para suavizar saltos
- **Validación cruzada**: Si objeto estaba `DENTRO` y desaparece, asumir oclusión primero

### 5.3 Tracking Inconsistente

**Problemas:**
- Track IDs cambian para el mismo objeto
- Track IDs se reutilizan para objetos diferentes
- Track IDs desaparecen y reaparecen

**Mitigación:**
- **No depender 100% de track_id**: Usar como señal auxiliar, no única fuente
- **Asociación híbrida**: Combinar track_id con asociación espacial (IoU, distancia)
- **Validación de transiciones**: Si track_id cambia pero posición es consistente → mantener objeto
- **Tracking ligero propio**: Implementar asociación simple basada en posición si track_id falla

### 5.4 Saltos en el Conteo

**Causas:**
- Múltiples objetos entran/salen simultáneamente (aunque raro según reglas)
- Falla masiva del detector en un frame
- Cambio de iluminación o condiciones

**Mitigación:**
- **Límite de cambio por frame**: Máximo 1 objeto puede entrar/salir por frame (según reglas)
- **Validación de saltos**: Si cambio > 1, revisar frames anteriores para validar
- **Filtro de mediana**: Aplicar en ventana de últimos 5 frames para suavizar
- **Alerta de anomalía**: Registrar cuando cambio > 1 para revisión manual

---

## 6. Estado del Sistema

### 6.1 Estructura de Estado Principal

```python
EstadoGlobal = {
    # Área de trabajo
    area_trabajo: {
        bbox: (x1, y1, x2, y2),
        tipo: "area_de_trabajo_pallet" | "area_de_trabajo_carro",
        validada: bool
    },
    
    # Contador
    contador_actual: int,
    contador_maximo: int,  # máximo alcanzado
    
    # Objetos activos
    objetos_dentro: {
        id: {
            track_id: int | None,
            clase: "cajas" | "folio",
            bbox_actual: (x1, y1, x2, y2),
            estado: "DENTRO" | "OCLUIDO" | "ENTRANDO" | "SALIENDO",
            frames_en_estado: int,
            ultimo_frame_visto: int,
            confianza_promedio: float,
            historial_posiciones: [(frame, bbox), ...]  # últimos N
        },
        ...
    },
    
    # Objetos en transición
    objetos_transicion: {
        id: {
            # Similar a objetos_dentro pero en estados transitorios
            frames_persistencia: int,
            requiere_validacion: bool
        },
        ...
    },
    
    # Buffer temporal
    buffer_frames: [
        {
            frame_num: int,
            timestamp: float,
            detecciones: [...],
            conteo_bruto: int,  # sin validación
            señales_auxiliares: {
                persona_presente: bool,
                producto_en_mano: bool
            }
        },
        ...  # últimos 10-15 frames
    ],
    
    # Estadísticas
    estadisticas: {
        total_entradas: int,
        total_salidas: int,
        falsos_positivos_detectados: int,
        falsos_negativos_detectados: int,
        eventos_validados: int,
        eventos_rechazados: int
    }
}
```

### 6.2 Colas y Buffers

**A. Buffer Circular de Frames (10-15 frames)**
- Propósito: Historial temporal para validación y suavizado
- Contenido: Detecciones, conteos brutos, señales auxiliares
- Uso: Filtros temporales, validación de persistencia

**B. Cola de Eventos Pendientes**
- Propósito: Eventos que requieren validación antes de aplicar
- Contenido: Tipo (ENTRADA/SALIDA), objeto, frame, confianza
- Uso: Validar con frames siguientes antes de confirmar

**C. Memoria de Objetos Ocluidos**
- Propósito: Trackear objetos que desaparecieron pero deben seguir contando
- Contenido: ID, última posición, frames ocluido, timeout
- Uso: Decidir si fue oclusión o salida real

### 6.3 Timeouts y Umbrales

**Timeouts (en frames, asumiendo ~10 FPS):**
- `TIMEOUT_OCLUSION`: 10 frames (1 segundo) - tiempo máximo para considerar oclusión
- `TIMEOUT_TRACKING`: 5 frames (0.5 segundos) - tiempo para perder tracking
- `TIMEOUT_VALIDACION`: 3 frames (0.3 segundos) - tiempo para validar evento

**Umbrales:**
- `CONFIANZA_MINIMA`: 0.6 - confianza mínima para considerar detección
- `PERSISTENCIA_ENTRADA`: 2-3 frames - frames necesarios para confirmar entrada
- `PERSISTENCIA_SALIDA`: 2-3 frames - frames necesarios para confirmar salida
- `IOU_MINIMO_AREA`: 0.95 - IoU mínimo para considerar "completamente dentro"
- `DISTANCIA_MAX_ASOCIACION`: 100 píxeles - distancia máxima para asociar objetos

### 6.4 Histéresis y Smoothing

**Histéresis de Estados:**
- Estados transitorios (`ENTRANDO`, `SALIENDO`) requieren persistencia antes de confirmar
- Evita cambios de estado por ruido o detecciones intermitentes

**Smoothing Temporal:**
- **Filtro de mediana**: Aplicar en ventana de 5 frames para conteo
- **Promedio móvil exponencial**: Para suavizar cambios graduales
- **Validación retroactiva**: Revisar últimos N frames antes de confirmar evento

---

## 7. Métricas de Evaluación y Plan de Pruebas

### 7.1 Métricas Principales

**A. Precisión del Conteo**
- **Error absoluto**: |conteo_predicho - conteo_real|
- **Error relativo**: error_absoluto / conteo_real
- **Precisión por frame**: % de frames con conteo correcto
- **Precisión final**: Conteo al final del video vs conteo real

**B. Precisión de Eventos**
- **Precisión de entradas**: TP_entradas / (TP_entradas + FP_entradas)
- **Recall de entradas**: TP_entradas / (TP_entradas + FN_entradas)
- **Precisión de salidas**: TP_salidas / (TP_salidas + FP_salidas)
- **Recall de salidas**: TP_salidas / (TP_salidas + FN_salidas)

**C. Robustez**
- **Tasa de falsos positivos**: FP / total_detecciones
- **Tasa de falsos negativos**: FN / total_objetos_reales
- **Latencia de detección**: Frames entre evento real y detección
- **Tasa de recuperación**: % de eventos correctamente detectados después de falla inicial

**D. Rendimiento**
- **Tiempo de procesamiento por frame**: ms/frame
- **Uso de memoria**: MB
- **Latencia end-to-end**: tiempo desde frame hasta conteo actualizado

### 7.2 Plan de Pruebas

**Fase 1: Pruebas Unitarias por Módulo**
- **Área de trabajo**: Validar detección y selección correcta
- **Filtrado**: Validar que solo objetos dentro del área se consideren
- **Asociación**: Validar matching correcto entre frames
- **Estados**: Validar transiciones de estado correctas

**Fase 2: Pruebas de Integración**
- **Flujo completo**: Procesar secuencia completa de frames
- **Validar conteo**: Comparar con conteo manual frame por frame
- **Validar eventos**: Comparar eventos detectados con eventos reales

**Fase 3: Casos Borde**
- **Oclusión simple**: Un objeto desaparece temporalmente
- **Oclusión múltiple**: Varios objetos desaparecen (apilado)
- **Tracking inconsistente**: Simular cambios de track_id
- **Falsos positivos**: Objetos detectados incorrectamente
- **Falsos negativos**: Objetos reales no detectados
- **Entrada rápida**: Objeto entra muy rápido
- **Salida rápida**: Objeto sale muy rápido
- **Movimiento interno**: Objeto se mueve dentro pero no sale
- **Área múltiple**: Múltiples áreas detectadas (validar selección)

**Fase 4: Pruebas de Estrés**
- **Secuencia larga**: Procesar video completo (330+ frames)
- **Condiciones variables**: Diferentes iluminaciones, ángulos
- **Carga computacional**: Medir rendimiento bajo carga

**Fase 5: Validación con Dataset Real**
- **Anotación manual**: Crear ground truth para subset de frames clave
- **Comparación sistemática**: Comparar frame por frame
- **Análisis de errores**: Categorizar tipos de errores y ajustar parámetros

### 7.3 Herramientas de Evaluación

**A. Visualización**
- Overlay de conteo en frames anotados
- Gráfico de conteo vs tiempo (frame)
- Marcadores de eventos (entrada/salida) en timeline
- Highlight de objetos ocluidos

**B. Reportes**
- Matriz de confusión de eventos
- Distribución de errores por tipo
- Análisis de frames con mayor error
- Estadísticas de rendimiento

**C. Debugging**
- Modo verbose con logs detallados
- Exportar estado interno por frame
- Visualización de estados de objetos
- Trazabilidad de decisiones

---

## 8. Formato de Logs de Eventos

### 8.1 Estructura de Log

**Formato recomendado: JSON Lines (una línea por evento)**

```json
{
  "timestamp": "2026-01-28T11:51:31.500",
  "frame_num": 0,
  "event_type": "ENTRADA" | "SALIDA" | "OCLUSION_START" | "OCLUSION_END" | "ERROR" | "INFO",
  "objeto": {
    "id_interno": 123,
    "track_id": 137,
    "clase": "cajas" | "folio",
    "bbox": [x1, y1, x2, y2],
    "confianza": 0.8860,
    "estado_anterior": "FUERA" | "DENTRO" | "OCLUIDO",
    "estado_nuevo": "DENTRO" | "FUERA" | "OCLUIDO"
  },
  "conteo": {
    "antes": 5,
    "despues": 6,
    "total_acumulado": 6
  },
  "validacion": {
    "persistencia_frames": 3,
    "señales_auxiliares": {
      "persona_presente": true,
      "producto_en_mano": false
    },
    "razon_decision": "Objeto persistió dentro del área por 3 frames consecutivos",
    "confianza_decision": 0.95
  },
  "contexto": {
    "objetos_dentro": 6,
    "objetos_ocluidos": 1,
    "objetos_transicion": 0,
    "area_trabajo": {
      "tipo": "area_de_trabajo_pallet",
      "bbox": [x1, y1, x2, y2]
    }
  },
  "metadata": {
    "tiempo_procesamiento_ms": 45.2,
    "version_algoritmo": "1.0",
    "parametros": {
      "confianza_minima": 0.6,
      "persistencia_entrada": 3,
      "timeout_oclusion": 10
    }
  }
}
```

### 8.2 Tipos de Eventos

**ENTRADA**
- Objeto confirmado como entrado al área
- Incrementa contador

**SALIDA**
- Objeto confirmado como salido del área
- Decrementa contador

**OCLUSION_START**
- Objeto en estado DENTRO desaparece
- Se inicia timeout de oclusión

**OCLUSION_END**
- Objeto ocluido reaparece o excede timeout
- Confirma si fue oclusión o salida real

**ERROR**
- Falso positivo detectado y rechazado
- Falso negativo detectado
- Anomalía en el sistema

**INFO**
- Cambios de estado internos
- Validaciones realizadas
- Información de debugging

### 8.3 Niveles de Logging

**Nivel 1: Mínimo (Producción)**
- Solo eventos confirmados (ENTRADA, SALIDA)
- Errores críticos

**Nivel 2: Estándar (Desarrollo)**
- Eventos confirmados
- Transiciones de estado
- Oclusiones
- Errores y advertencias

**Nivel 3: Verbose (Debugging)**
- Todos los eventos
- Estado interno completo
- Decisiones de validación
- Métricas de rendimiento

### 8.4 Archivos de Log Recomendados

```
logs/
  eventos_{timestamp}.jsonl          # Eventos principales
  debug_{timestamp}.jsonl              # Logs detallados (nivel verbose)
  metricas_{timestamp}.json            # Métricas agregadas por frame
  errores_{timestamp}.jsonl            # Solo errores y anomalías
```

---

## 9. Recomendaciones Finales

### 9.1 Enfoque Recomendado

**Empezar con Enfoque 1 (Tracking Ligero con Memoria Temporal)** porque:
- Balance óptimo entre complejidad y precisión
- Funciona bien con tracking imperfecto
- Maneja oclusiones de forma natural
- Fácil de depurar y ajustar

**Evolucionar hacia Enfoque 3 (Híbrido)** si:
- Se requiere mayor precisión
- Tracking inconsistente es problema crítico
- Hay recursos computacionales disponibles

### 9.2 Orden de Implementación

1. **Módulos básicos**: Área, Filtrado, Conteo simple
2. **Tracking ligero**: Asociación básica, estados
3. **Detección de eventos**: Entrada/salida con validación
4. **Manejo de oclusiones**: Timeout y memoria
5. **Robustez**: Filtros, validaciones, manejo de errores
6. **Logging y métricas**: Sistema completo de monitoreo

### 9.3 Parámetros a Ajustar

**Críticos (ajustar primero):**
- `CONFIANZA_MINIMA`
- `PERSISTENCIA_ENTRADA` / `PERSISTENCIA_SALIDA`
- `TIMEOUT_OCLUSION`

**Secundarios (fine-tuning):**
- `DISTANCIA_MAX_ASOCIACION`
- `IOU_MINIMO_AREA`
- Tamaño de buffers temporales

### 9.4 Validación Continua

- Comparar con ground truth manual en subset de frames
- Monitorear métricas en tiempo real durante desarrollo
- Ajustar parámetros iterativamente basado en errores
- Documentar decisiones y razones de cambios

---

## 10. Consideraciones para Edge (Jetson)

### 10.1 Optimizaciones Futuras

- **Reducir buffers**: Menos frames en memoria
- **Simplificar asociación**: Algoritmos más ligeros
- **Cuantización**: Reducir precisión de cálculos si es necesario
- **Paralelización**: Procesar frames en batches si es posible

### 10.2 Monitoreo de Recursos

- Medir uso de CPU/GPU por frame
- Monitorear uso de memoria
- Identificar cuellos de botella
- Optimizar módulos más costosos

---

**Fin del Plan**

