# Fase 04 — TargetEngineering

Este documento explica cómo trabajar con la **Fase 04 (`04_targetengineering`)**, dedicada a la *ingeniería del objetivo de predicción*. En esta fase se define formalmente **qué significa un positivo (y un negativo)** a partir de las ventanas generadas en la Fase 03.

El notebook y la script de esta fase realizan tareas conceptualmente equivalentes.

---

## Propósito de la fase
- Definir el **objetivo de predicción** de forma declarativa y reproducible.
- Transformar el dataset de ventanas (F03) en un dataset **etiquetado** (labelled).
- Mantener la trazabilidad explícita entre:
  - ventanas (F03),
  - definición del objetivo,
  - y dataset final listo para modelado.
- Preparar la entrada canónica para la **Fase 05 (Modeling)**.

---

## Ubicaciones clave
- Scripts / notebook:
  - `notebooks/04_targetengineering.ipynb`
  - `scripts/04_targetengineering.py`
- Parámetros base:
  - `executions/04_targetengineering/base_params.yaml`
- Variantes y artefactos:
  - `executions/04_targetengineering/<VARIANT>/`

---

## Entradas requeridas
Para ejecutar la Fase 04 necesitas:
- Una variante válida de la **Fase 03** (dataset de ventanas).
- La variante de F04 debe declarar explícitamente:
  - `parent_variant` → variante de F03.
  - `prediction_objective` → definición del objetivo.

---

## Definición del objetivo de predicción

El objetivo se define en el parámetro `prediction_objective`, con la siguiente estructura lógica:

```yaml
prediction_objective:
  operator: OR | AND
  events:
    - EVENT_NAME_1
    - EVENT_NAME_2
    - ...
```

### Semántica
- **OR**: la ventana de predicción (PW) se etiqueta como positiva (`1`)
  si *al menos uno* de los eventos aparece en la PW.
- **AND**: la ventana se etiqueta como positiva solo si *todos* los eventos
  aparecen al menos una vez en la PW.

Los eventos se especifican por **nombre**, y la traducción nombre → código
se obtiene del **catálogo de eventos de la Fase 02**, heredado vía F03.

---

## Ejemplo de `base_params.yaml`

```yaml
prediction_objective:
  operator: OR
  events:
    - Battery_Active_Power_0_5-to-95_100
    - Battery_Active_Power_5_15-to-95_100
    - Battery_Active_Power_15_25-to-95_100
    - Battery_Active_Power_25_35-to-95_100
    - Battery_Active_Power_35_65-to-95_100
    - Battery_Active_Power_65_75-to-95_100
    - Battery_Active_Power_75_85-to-95_100
    - Battery_Active_Power_85_95-to-95_100
```

---

## Artefactos generados (salidas típicas)

En `executions/04_targetengineering/<VARIANT>/` normalmente encontrarás:

- `04_targetengineering_dataset.parquet`
  - Dataset de ventanas **etiquetadas** (features + label).
- `04_targetengineering_metadata.json`
  - Metadatos del proceso (objetivo, conteos, balance de clases).
- `04_targetengineering_params.json` o `params.yaml`
  - Parámetros efectivos usados por la variante.
- `04_targetengineering_report.html`
  - Informe con resumen del objetivo y estadísticas.
- `figures/`
  - Figuras generadas (distribución de clases, etc.).

---

## Parámetros y objetivos `make` de la fase

### Crear variante
```bash
make variant4 VARIANT=v201 PARENT=v111 \
  PREDICTION_NAME=name \
  OBJECTIVE="{operator: OR, events: [GRID_OVERVOLTAGE, INVERTER_FAULT]}"
```

Parámetros:
- `VARIANT`: identificador `vNNN` (obligatorio).
- `PARENT`: variante padre de Fase 03 (obligatorio).
- `PREDICTION_NAME`: nombre legible del predictor. Debe ser estable y único en el proyecto.
- `OBJECTIVE`: definición inline del objetivo (YAML/JSON compacto).

---

### Ejecutar notebook
```bash
make nb4-run VARIANT=v201
```
- Ejecuta `04_targetengineering.ipynb` con `ACTIVE_VARIANT`.
- Recomendado para inspección conceptual del objetivo y balance de clases.

---

### Ejecutar script
```bash
make script4-run VARIANT=v201
```
- Ejecución reproducible y automatizable.
- Genera todos los artefactos finales de la fase.

---

### Chequeos
```bash
make script4-check-results VARIANT=v201
make script4-check-dvc
```

---

### Publicar variante
```bash
make publish4 VARIANT=v201
```
- Valida la variante mediante trazabilidad.
- Registra artefactos en DVC y git.

---

### Eliminar / limpiar
```bash
make remove4 VARIANT=v201
make clean4-all
```

- `remove4`: elimina una variante (solo si no tiene hijos).
- `clean4-all`: limpieza administrativa de la fase (no respeta trazabilidad).

---

## Flujo de trabajo recomendado
1. Crear variante:
   ```bash
   make variant4 VARIANT=v201 PARENT=v111 \
     PREDICTION_NAME=NOMBRE \
     OBJECTIVE="{operator: OR, events: [...]}"
   ```
2. Ejecutar notebook (opcional):
   ```bash
   make nb4-run VARIANT=v201
   ```
3. Ejecutar script:
   ```bash
   make script4-run VARIANT=v201
   ```
4. Verificar resultados:
   ```bash
   make script4-check-results VARIANT=v201
   ```
5. Publicar (cuando proceda):
   ```bash
   make publish4 VARIANT=v201
   ```

---

## Recomendaciones y notas prácticas
- El **objetivo define el problema de ML**: cambiarlo implica un problema distinto.
- Vigila el **balance de clases** (positivos vs negativos); esta fase es crítica.
- Un mismo dataset de ventanas (F03) puede generar múltiples variantes F04
  con objetivos diferentes.
- Las decisiones tomadas aquí condicionan directamente la viabilidad de F05
  y la calidad de los modelos resultantes.

---

Al completar la Fase 04, dispones de un dataset etiquetado, trazable y listo
para entrenamiento de modelos en la **Fase 05 (Modeling)**.
