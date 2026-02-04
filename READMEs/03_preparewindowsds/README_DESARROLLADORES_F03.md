# README — Desarrolladores
Fase 03 · PrepareWindowsDS

## Visión general

La Fase 03 del pipeline **PrepareWindowsDS** genera el **dataset final de ventanas temporales**
a partir del dataset de eventos producido en la Fase 02.

A partir de este punto:
- no existen índices temporales intermedios,
- no se exponen offsets ni rangos,
- el dataset es directamente consumible por modelos de ML y notebooks docentes.

Cada fila del dataset representa **una ventana temporal completa**,
dividida en:
- ventana de observación (OW),
- ventana de predicción (PW).

---

## Entrada

La Fase 03 consume exclusivamente artefactos de la Fase 02:

- Dataset Parquet con columnas:
  - `segs` (timestamp en segundos, ordenado),
  - `events` (lista de códigos de eventos ocurridos en ese instante).
- Catálogo de eventos:
  - `02_prepareeventsds_event_catalog.json`
- Metadata F02:
  - usada para heredar el parámetro temporal `Tu`.

No se admiten otras fuentes de datos.

---

## Salida

En el directorio:

```
params/03_preparewindowsds/<variant>/
```

se generan los siguientes artefactos:

- `03_preparewindowsds_dataset.parquet`  
  **Dataset final de ventanas (artefacto principal).**
- `03_preparewindowsds_metadata.json`  
  Metadata resumida de la fase.
- `03_preparewindowsds_stats.json`  
  Estadísticos agregados del dataset.
- `03_preparewindowsds_report.html`  
  Informe HTML auto‑generado.

---

## Esquema del dataset F03

El dataset contiene **exactamente dos columnas**:

| Columna   | Tipo        | Descripción |
|-----------|-------------|-------------|
| OW_events | list[int32] | Eventos observados en la ventana de observación |
| PW_events | list[int32] | Eventos observados en la ventana de predicción |

Características:
- Longitud variable por fila.
- Sin columnas temporales.
- Sin índices ni contadores.

---

## Semántica temporal

Cada ventana está definida por los parámetros:

- `OW` (Observation Window)
- `LT` (Latency Time)
- `PW` (Prediction Window)
- `Tu` (unidad temporal base)

Todos los parámetros se expresan como múltiplos de `Tu`.

---

## Gestión de valores NaN

- Los eventos derivados de valores NaN se identifican mediante el catálogo F02.
- Estrategia soportada:
  - `nan_strategy = discard`  
    (las ventanas que contienen eventos NaN se descartan por completo).

---

## Decisiones de diseño

- F03 **produce el dataset final**, no un dataset intermedio.
- La materialización temprana de eventos evita errores semánticos posteriores.
- El formato es estable y desacoplado del resto del pipeline.

Cualquier cambio en el esquema:
- invalida F04,
- requiere actualización de documentación,
- requiere regenerar datasets.

---

## Estado

Fase cerrada y estable.
Preparada para Fase 04 (ModelTraining).
