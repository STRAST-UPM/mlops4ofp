# FASE 07 — DEPLOY & RUNTIME VALIDATION

## 1. Objetivo de la fase

La Fase 07 ejecuta y valida en runtime un paquete F06 previamente sellado.

F07:
- No entrena modelos.
- No modifica datasets.
- No redefine objetivos.
- No altera el régimen temporal.
- No recalcula targets.
- No decide modelos.

F07 únicamente:
- Despliega un runtime mínimo (servidor Flask).
- Ejecuta los modelos del paquete F06.
- Reproduce los datasets asociados.
- Genera predicciones.
- Calcula métricas por modelo individual.
- Produce un informe reproducible.

---

## 2. Entrada

Cada variante F07 depende de una variante F06.

Estructura esperada:

```
executions/06_packaging/<vNNN>/
  models/
  datasets/
  06_packaging_metadata.json
```

La variante F07 declara:

```
executions/07_deployrun/<vMMM>/
  params.yaml
```

Contenido mínimo de `params.yaml`:

```yaml
parent_variant_f06: vNNN

runtime:
  host: "127.0.0.1"
  port: 5005
```

---

## 3. Artefactos generados

Tras ejecutar F07:

```
executions/07_deployrun/<vMMM>/
  manifest.json
  logs/
    raw_predictions.parquet
    raw_predictions.csv
  metrics/
    metrics_per_model.csv
  report/
    report.html
    figures/
      confusion_<prediction_name>.png
  07_deployrun_metadata.json
```

---

## 4. Flujo de ejecución

### 4.1 variant7

Prepara la variante y genera `manifest.json`:

```
make variant7 VARIANT=vMMM PARENT=vNNN
```

El manifest contiene:
- Modelos incluidos (prediction_name).
- Ruta al modelo (`model.h5`).
- Metadata de vectorización (`model_summary.json`).
- Dataset asociado.
- Columnas de entrada y etiqueta.

---

### 4.2 script7-run

Ejecuta completamente:

```
make script7-run VARIANT=vMMM
```

Secuencia:

1. Limpieza idempotente de carpetas.
2. Arranque del servidor Flask.
3. Cliente batch (emit exactly as read).
4. Guardado de logs crudos.
5. Cálculo de métricas.
6. Generación de figuras.
7. Generación de report.html.
8. Escritura de metadata de fase.

---

### 4.3 nb7-run

Alternativa notebook:

```
make nb7-run VARIANT=vMMM
```

Comportamiento equivalente a script.

---

### 4.4 publish7

Publica resultados mediante DVC + Git:

```
make publish7 VARIANT=vMMM
```

---

### 4.5 remove7

Elimina la variante (si no tiene hijos):

```
make remove7 VARIANT=vMMM
```

---

## 5. Métricas calculadas

Por cada `prediction_name`:

- TP
- TN
- FP
- FN
- precision
- recall
- f1
- no_ref_pred_1
- no_ref_pred_0
- no_ref_total

Las métricas se calculan únicamente sobre ventanas con referencia en su dataset F04 original.

---

## 6. Propiedades clave

- Idempotente.
- Caja negra cliente-servidor.
- Reproducible.
- Compatible con DVC.
- Sin MLflow.
- Sin dependencias adicionales a TensorFlow + Flask + requests.

---

## 7. Batch inference

F07 utiliza inferencia por lotes (batch) para mejorar el rendimiento.

El tamaño del lote se controla mediante:

```yaml
batch_size: 256
```

Si no se especifica, usa 256 por defecto. 

El servidor expone dos endpoints:
- POST /infer ventana individual (debug)
- POST /infer_batch lote de ventanas

El pipeline usa siempre /infer_batch.

---

## 8. Garantía de equivalencia funcional

La equivalencia runtime se garantiza porque:

- F05 guarda explícitamente el vocabulario y parámetros de vectorización.
- F06 copia el modelo y metadata sin modificar.
- F07 utiliza exactamente esa metadata para reconstruir la entrada al modelo.

---

Generado automáticamente: 2026-02-15T21:43:59.808734 UTC
