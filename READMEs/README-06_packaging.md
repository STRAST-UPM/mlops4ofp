
# Fase 06 — Packaging / System Composition

Este documento describe cómo trabajar con la **Fase 06 (`06_packaging`)**, dedicada a la **composición de un sistema de inferencia reproducible** a partir de modelos ya entrenados (Fase 05) y datasets de eventos (Fase 02).

La Fase 06 **no entrena modelos ni ejecuta inferencia**, sino que:
- selecciona explícitamente qué modelos forman parte del sistema,
- fija un régimen temporal común,
- materializa un *replay* temporal coherente,
- y genera un **paquete de despliegue sellado y auditable**.

El notebook y la script de esta fase realizan tareas conceptualmente equivalentes; la script está orientada a ejecuciones reproducibles y automatizadas, mientras que el notebook permite inspección paso a paso.

---

## Propósito de la fase
- Componer un **sistema de inferencia multi‑modelo** a partir de variantes F05.
- Seleccionar **uno o varios modelos por objetivo F04** de forma manual y explícita.
- Fijar (o heredar) un **régimen temporal común** (`Tu`, `OW`, `PW`).
- Construir un **dataset de replay temporal** único y coherente.
- Sellar un **paquete de despliegue reproducible** para fases posteriores.
- Registrar decisiones y artefactos para **trazabilidad completa**.

---

## Ubicaciones clave
- Scripts / notebook:
  - `notebooks/06_packaging.ipynb`
  - `scripts/06_packaging.py`
- Parámetros base:
  - `executions/06_packaging/base_params.yaml`
- Variantes y artefactos:
  - `executions/06_packaging/<VARIANT>/`
- Paquete resultante:
  - `executions/06_packaging/<VARIANT>/models/`
  - `executions/06_packaging/<VARIANT>/replay/`

---

## Entradas requeridas
Para ejecutar la Fase 06 necesitas:
- **Una o más variantes válidas de la Fase 05** (modelos entrenados).
- Todas las variantes F05 deben:
  - derivar de objetivos F04 compatibles,
  - compartir (directa o indirectamente) un único dataset F02.

Cada variante F06 puede combinar **múltiples variantes F05**.

---

## Relación con fases anteriores

- **F03 (`preparewindowsds`)**  
  Define el régimen temporal (`Tu`, `OW`, `PW`).

- **F04 (`targetengineering`)**  
  Define los objetivos de predicción.

- **F05 (`modeling`)**  
  Entrena y selecciona modelos candidatos por objetivo.

- **F06 (`packaging`)**  
  Selecciona modelos concretos y construye el sistema.

---

## Parámetros principales (`base_params.yaml`)

### Linaje (obligatorio)
```yaml
parent_variants_f05:
  - vNNN
  - vMMM
```

Lista de variantes F05 que se combinan en el sistema.

---

### Régimen temporal
```yaml
temporal:
  Tu: <int>
  OW: <int>
  PW: <int>
```

- Si no se especifican al crear la variante, se **heredan de F03**
  (vía F05 → F04 → F03).
- Si se especifican explícitamente, **prevalece el valor del usuario**.

---

### Selección manual de modelos
```yaml
models:
  f04_v012:
    - model_id: m03
      source_f05: v042
    - model_id: m07
      source_f05: v043
```

- Clave: identificador del objetivo F04.
- Valor: lista de modelos válidos.
- Puede haber **más de un modelo legítimo por objetivo**.
- No existen modelos “primarios” o “secundarios” en esta fase.

---

### Replay temporal
```yaml
replay:
  source:
    dataset_id: vXXX
  time_range:
    start: <opcional>
    end: <opcional>
```

- El dataset de replay debe proceder de **un único F02**.
- El rango temporal es opcional; si no se define, se usa el completo.

---

## Artefactos generados (salidas típicas)

En `executions/06_packaging/<VARIANT>/`:

- `models/` **(obligatorio)**  
  Copia física de los modelos seleccionados, organizada por objetivo.

- `replay/replay_events.parquet` **(obligatorio)**  
  Dataset de eventos para replay temporal.

- `06_packaging_metadata.json` **(obligatorio)**  
  Metadata consolidada:
  - linaje completo,
  - régimen temporal,
  - modelos incluidos,
  - tamaño del replay.

- `params.yaml`  
  Parámetros efectivos de la variante (manifiesto del sistema).

La presencia de `06_packaging_metadata.json` es **condición necesaria para publicar**.

---

## Objetivos `make` de la fase

### Crear variante
```bash
make variant6 VARIANT=v601 \
  PARENTS_F05="v501 v502" \
  MODELS='<yaml>'
```

Ejemplo:
```bash
make variant6 VARIANT=v601 \
  PARENTS_F05="v501 v502" \
  MODELS='{f04_v012:[{model_id:m03,source_f05:v501}]}'
```

---

### Ejecutar notebook
```bash
make nb6-run VARIANT=v601
```
- Ejecución interactiva y visual.
- Recomendada para inspección y docencia.

---

### Ejecutar script
```bash
make script6-run VARIANT=v601
```
- Ejecución reproducible.
- Genera todos los artefactos finales.

---

### Validar variante
```bash
make check6 VARIANT=v601
```

---

### Publicar variante
```bash
make publish6 VARIANT=v601
```
- Versiona artefactos con DVC.
- Registra la variante en git.

---

### Eliminar / limpiar
```bash
make remove6 VARIANT=v601
make clean6
```

---

## Flujo de trabajo recomendado
1. Crear variante:
   ```bash
   make variant6 VARIANT=v601 PARENTS_F05="v501 v502" MODELS='<yaml>'
   ```
2. Ejecutar notebook (opcional):
   ```bash
   make nb6-run VARIANT=v601
   ```
3. Ejecutar script:
   ```bash
   make script6-run VARIANT=v601
   ```
4. Verificar resultados:
   ```bash
   make check6 VARIANT=v601
   ```
5. Publicar variante:
   ```bash
   make publish6 VARIANT=v601
   ```

---

## Recomendaciones y notas prácticas
- F06 **no es exploratoria**: cada variante representa una decisión de sistema.
- Mantén explícita la selección de modelos para auditoría.
- Verifica que todas las variantes F05 apunten al mismo F03/F02.
- No modifiques modelos ni datasets dentro de F06.
- El paquete F06 es la **unidad de entrada** para despliegue (F07).

---

Al completar la Fase 06, dispones de un **paquete de despliegue sellado, trazable y reproducible**, listo para validación en ejecución y despliegue controlado.
