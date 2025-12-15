# Dataset — Fase 03 (PrepareWindowsDS)

Este dataset es la salida final del pipeline de preparación de datos
para entrenamiento de modelos de Online Failure Prediction (OFP).

Cada fila representa una **ventana temporal** definida por:
- una ventana de observación (OW)
- una ventana de predicción (PW)

Los valores de OW y PW están fijados por la variante utilizada.

---

## Estructura de una fila

| Columna | Descripción |
|------|------------|
| t0 | Instante temporal (en segundos) correspondiente al inicio de la ventana |
| i_ow_* | Contadores de eventos ocurridos en la ventana de observación (OW) |
| i_pw_* | Contadores de eventos ocurridos en la ventana de predicción (PW) |

Cada columna `i_ow_k` o `i_pw_k` corresponde a un **evento identificado por su índice `k`**.

---

## Semántica de eventos

Los eventos representan transiciones discretizadas de señales físicas
(p. ej. cambios de banda, aparición/desaparición de valores NaN, etc.).

El mapeo entre:
- índice de evento (`k`)
- significado semántico

se encuentra en: params/03_preparewindowsds/<variante>/metadata/

(en ficheros como `event_to_id.json`, `id_to_event.json` o equivalentes).

---

## Uso para entrenamiento de modelos

- El dataset está listo para su uso directo en modelos de ML.
- No depende de ningún código del proyecto.
- Se recomienda:
  - normalizar o escalar los contadores si el modelo lo requiere
  - tratar los eventos de PW como **objetivo** y los de OW como **entrada**

La definición exacta de entrada/salida depende del modelo y del problema
de predicción abordado.



