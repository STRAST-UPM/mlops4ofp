# Fase 05 — Modeling

Este documento describe cómo trabajar con la **Fase 05 (`05_modeling`)**, dedicada al **entrenamiento, evaluación y selección de modelos predictivos** a partir de un dataset ya etiquetado (Fase 04).  
Es la fase donde se materializa el aprendizaje automático propiamente dicho, manteniendo **reproducibilidad, trazabilidad y compatibilidad con despliegue en edge (TensorFlow Lite / TFLite Micro)**.

El notebook y la script de esta fase realizan tareas conceptualmente equivalentes; la script está orientada a ejecuciones reproducibles y automatizadas.

---

## Propósito de la fase
- Entrenar modelos predictivos a partir del dataset etiquetado (F04).
- Explorar automáticamente un **espacio de búsqueda acotado (AutoML ligero)** por variante.
- Evaluar modelos con métricas alineadas con el problema (recall prioritario).
- Seleccionar **uno o varios candidatos válidos** por variante.
- Registrar artefactos, métricas y decisiones para trazabilidad completa.
- Preparar modelos **edge‑ready** para fases posteriores (exportación / inferencia).

---

## Ubicaciones clave
- Scripts / notebook:
  - `notebooks/05_modeling.ipynb`
  - `scripts/05_modeling.py`
- Parámetros base:
  - `executions/05_modeling/base_params.yaml`
- Variantes y artefactos:
  - `executions/05_modeling/<VARIANT>/`
- Candidatos entrenados:
  - `executions/05_modeling/<VARIANT>/candidates/`

---

## Entradas requeridas
Para ejecutar la Fase 05 necesitas:
- Una variante válida de la **Fase 04** (dataset etiquetado).
- La variante de F05 debe definir obligatoriamente:
  - `parent_variant` → variante de F04.
  - `model_family` → familia de modelos a explorar.

Cada variante F05 explora **una sola familia de modelos**.

---

## Familias de modelos soportadas

Las familias actualmente soportadas son:

- `dense_bow`  
  Modelos densos sobre representaciones tipo bag‑of‑words / conteos agregados.

- `sequence_embedding`  
  Modelos secuenciales con embedding aprendible (orientados a eventos ordenados).

- `cnn1d`  
  Redes convolucionales 1D sobre secuencias discretizadas.

La familia seleccionada determina qué sección del `search_space` es utilizada.

---

## Parámetros principales (`base_params.yaml`)

### Linaje (obligatorio)
```yaml
parent_variant: vNNN
model_family: dense_bow | sequence_embedding | cnn1d
```

---

### AutoML ligero
```yaml
automl:
  max_trials: 3
  seed: 42
```

- Número acotado de experimentos por variante.
- Reproducible por diseño (seed fija).

---

### Entrenamiento
```yaml
training:
  epochs: 3
  batch_size: [32, 64]
  learning_rate: [0.001, 0.0005]
  max_samples: 100000
```

- Algunos parámetros actúan como **espacio de búsqueda**.
- `max_samples` limita tamaño para experimentación rápida.

---

### Manejo del desbalanceo
```yaml
imbalance:
  strategy: auto | none
  metric_focus: recall
```

- Por defecto se prioriza **recall**, coherente con detección de eventos críticos.

---

### Evaluación
```yaml
evaluation:
  split:
    train: 0.7
    val: 0.15
    test: 0.15
```

- Particionado fijo y documentado para trazabilidad.

---

### Métricas
```yaml
metrics:
  primary: recall
  secondary:
    - precision
    - f1
    - confusion_matrix
```

- La métrica primaria gobierna selección de candidatos.

---

### Selección de candidatos
```yaml
candidate_selection:
  threshold: 0.80
  policy: keep_all_above | fallback_best
```

- `keep_all_above`: conserva todos los modelos que superan el umbral.
- `fallback_best`: si ninguno lo supera, conserva el mejor.

---

### Espacios de búsqueda
El bloque `search_space` define los hiperparámetros por familia.  
Es **libre y extensible**, validado por el código (no por el esquema).

Ejemplo:
```yaml
search_space:
  dense_bow:
    n_layers: [1, 2]
    units: [32, 64]
    dropout: [0.0, 0.2]
```

---

## Artefactos generados (salidas típicas)

En `executions/05_modeling/<VARIANT>/`:

- `05_modeling_metadata.json` **(obligatorio)**
  - Resumen de entrenamiento, métricas y selección.
- `05_modeling_params.json` o `params.yaml`
  - Parámetros efectivos usados.
- `candidates/`
  - Un subdirectorio por modelo candidato:
    - pesos (`.h5`, `.keras`, etc.)
    - métricas
    - configuración del modelo
- `05_modeling_report.html`
  - Informe consolidado del proceso.

La presencia de `05_modeling_metadata.json` es **condición necesaria para publicar**.

---

## Objetivos `make` de la fase

### Crear variante
```bash
make variant5 VARIANT=v301 PARENT=v201 MODEL_FAMILY=dense_bow
```

---

### Ejecutar notebook
```bash
make nb5-run VARIANT=v301
```
- Útil para exploración, inspección de métricas y comprensión didáctica.

---

### Ejecutar script
```bash
make script5-run VARIANT=v301
```
- Ejecución reproducible.
- Genera candidatos y artefactos finales.

---

### Chequeos
```bash
make script5-check-results VARIANT=v301
make script5-check-dvc
```

---

### Publicar variante
```bash
make publish5 VARIANT=v301
```
- Valida trazabilidad.
- Registra artefactos en DVC y git.

---

### Eliminar / limpiar
```bash
make remove5 VARIANT=v301
make clean5-all
```

- `remove5`: elimina una variante (solo si no tiene hijos).
- `clean5-all`: limpieza administrativa (no respeta trazabilidad).

---

## Flujo de trabajo recomendado
1. Crear variante:
   ```bash
   make variant5 VARIANT=v301 PARENT=v201 MODEL_FAMILY=sequence_embedding
   ```
2. Ejecutar notebook (opcional):
   ```bash
   make nb5-run VARIANT=v301
   ```
3. Ejecutar script:
   ```bash
   make script5-run VARIANT=v301
   ```
4. Verificar resultados:
   ```bash
   make script5-check-results VARIANT=v301
   ```
5. Publicar variante (cuando proceda):
   ```bash
   make publish5 VARIANT=v301
   ```

---

## Recomendaciones y notas prácticas
- Cada variante F05 representa **una hipótesis de modelado**.
- Mantén bajo `max_trials` para ciclos rápidos de experimentación.
- Priorizar recall es coherente con OFP y eventos raros.
- Los modelos generados deben ser compatibles con **TensorFlow Lite / TFLite Micro**.
- Esta fase puede repetirse muchas veces sin modificar fases anteriores.

---

Al completar la Fase 05, dispones de **modelos entrenados, evaluados y trazables**, listos para selección final, cuantización o despliegue en sistemas edge.
