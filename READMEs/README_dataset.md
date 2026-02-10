# Dataset F03 — Trabajo Especial (Matrícula)

Este dataset corresponde a la **salida final correcta** de la Fase 03
del pipeline de preparación de datos.

Está diseñado para ser utilizado directamente en el trabajo especial
sin necesidad de conocer el código interno del proyecto.

---

## Qué representa cada fila

Cada fila del dataset representa una ventana temporal y contiene:

- `OW_events`: eventos observados en la ventana de observación.
- `PW_events`: eventos observados en la ventana de predicción.

Ambas columnas contienen **listas de códigos de eventos**.

No hay:
- tiempos,
- índices,
- offsets,
- ni información adicional.

---

## Esquema del dataset

| Columna   | Tipo        | Significado |
|-----------|-------------|-------------|
| OW_events | list[int]   | Eventos pasados |
| PW_events | list[int]   | Eventos futuros |

---

## Semántica de los eventos

Cada entero representa un tipo de evento discreto.

La correspondencia entre:
- código de evento,
- significado físico,

se encuentra en el catálogo generado en F02:

```
params/02_prepareeventsds/<variante>/02_prepareeventsds_event_catalog.json
```

---

## Uso recomendado

- Construir representaciones a partir de `OW_events`.
- Predecir la ocurrencia o distribución de `PW_events`.
- Justificar las decisiones de modelado.

No se requiere modificar el dataset.

---

## Validación

Un dataset correcto debe cumplir:

- Tener exactamente dos columnas.
- Ambas columnas contienen listas de enteros.
- Cada fila es una ventana temporal válida.

Cualquier otra estructura debe considerarse incorrecta.
