
# Fase 06 — Packaging / System Composition

Este documento describe cómo trabajar con la **Fase 06 (`06_packaging`)**, dedicada a la **composición de un sistema de inferencia reproducible** a partir de modelos ya entrenados (Fase 05) y datasets de eventos (Fase 02).

La Fase 06 **no entrena modelos ni ejecuta inferencia**, sino que:

- compone un sistema a partir de variantes F05,
- incorpora automáticamente el modelo oficial de cada F05,
- copia los datasets ya etiquetados de F04,
- valida la coherencia del régimen temporal,
- y genera un paquete de sistema sellado y auditable.

F06 no construye replay ni selecciona modelos manualmente.


---

## Propósito de la fase

- Componer un sistema a partir de variantes F05.
- Incorporar el modelo oficial de cada F05.
- Incorporar los datasets etiquetados de F04.
- Validar coherencia temporal común.
- Generar un paquete sellado y reproducible.

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
- compartir el mismo régimen temporal (Tu, OW, PW).

Cada variante F06 puede combinar **múltiples variantes F05**.

---

## Relación con fases anteriores

- **F04 (`targetengineering`)**  
  Define los objetivos de predicción.

- **F05 (`modeling`)**  
  Entrena y selecciona modelos candidatos por objetivo.


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
  Tu: <int|null>
  OW: <int|null>
  PW: <int|null>
```

- Si no se especifican al crear la variante, se **heredan de F03**
  (vía F05 → F04 → F03).

---


## Artefactos generados (salidas típicas)

En executions/06_packaging/<VARIANT>/:

- models/ (obligatorio)
  Copia física del modelo oficial de cada F05.

- datasets/ (obligatorio)
  Copia del dataset etiquetado de cada F04 asociado.

- objectives.json
  Expresiones formales de los objetivos F04.

- 06_packaging_metadata.json
  Metadata consolidada:
    - linaje
    - régimen temporal
    - modelos incluidos
    - datasets incluidos

- params.yaml
  Parámetros efectivos de la variante.

--

## Objetivos `make` de la fase

### Crear variante
```bash
make variant6 VARIANT=v601 \
  PARENTS_F05="v501 v502" 
```

Ejemplo:
```bash
make variant6 VARIANT=v601 \
  PARENTS_F05="v501 v502" 
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
   make variant6 VARIANT=v601 PARENTS_F05="v501 v502"
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
- Cada F05 debe contener exactamente un modelo oficial.
- F06 no selecciona modelos manualmente.
- F06 no construye replay.
- No modifiques modelos ni datasets dentro de F06.
---

Al completar la Fase 06, dispones de un **paquete de despliegue sellado, trazable y reproducible**, listo para validación en ejecución y despliegue controlado.
