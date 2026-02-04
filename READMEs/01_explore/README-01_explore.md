# Fase 01 — Explore

Este documento explica cómo trabajar con la Fase 01 (`01_explore`) del pipeline: objetivos `make`, parámetros relevantes, entradas y salidas esperadas, y un resumen de los pasos principales. El `notebook` y la `script` de esta fase realizan tareas equivalentes; usa el `notebook` para entender el flujo y la `script` para ejecuciones reproducibles en batch.

## Propósito de la fase
- Explorar el dataset RAW, aplicar limpieza y transformaciones iniciales.
- Generar un dataset intermedio (parquet) listo para la fase 02.
- Generar metadatos, parámetros usados y un informe (HTML/JSON) con estadísticas y figuras.

## Ubicaciones clave
- Scripts/notebook: `notebooks/01_explore.ipynb`, `scripts/01_explore.py`
- Parámetros base: `executions/01_explore/base_params.yaml` (y plantillas en `params/01_explore/` si existen)
- Variantes y artefactos: `executions/01_explore/<VARIANT>/`

## Artefactos generados (salidas típicas)
En `executions/01_explore/<VARIANT>/` normalmente encontrarás:
- `01_explore_dataset.parquet` — dataset procesado (principal salida)
- `01_explore_metadata.json` — metadatos del procesamiento (fechas, conteos)
- `01_explore_params.json` o `params.yaml` — parámetros aplicados a la variante
- `01_explore_report.html` — informe de exploración (figuras, tablas)
- `figures/` — figuras generadas (si procede)

> Nota: los nombres concretos pueden variar ligeramente según la versión del script; los targets `make` de comprobación esperan los nombres listados en `Makefile`.

## Parámetros y objetivos `make` de la fase

Resumen de los objetivos más usados (ejemplos de uso más abajo):

- `make variant1 VARIANT=vNNN RAW=/ruta/dataset [CLEANING_STRATEGY=...] [NAN_VALUES='[...]'] [ERROR_VALUES='...']`
  - `VARIANT`: identificador `vNNN` (obligatorio). Ej.: `v001`.
  - `RAW`: ruta al dataset RAW (obligatorio para crear la variante).
  - `CLEANING_STRATEGY`: estrategia de limpieza (ej.: `basic`) — controla limpiezas por defecto.
  - `NAN_VALUES`: lista de valores que se tratarán como NaN (ej.: `'[-999999]'`).
  - `ERROR_VALUES`: json string por columna con valores inválidos a tratar (ej.: '{"col1":[-1]}').

- `make nb1-run VARIANT=vNNN`
  - Ejecuta `notebooks/01_explore.ipynb` in-place con `ACTIVE_VARIANT=VARIANT`.
  - Útil para inspección interactiva y generación de figuras paso a paso.

- `make script1-run VARIANT=vNNN`
  - Ejecuta `scripts/01_explore.py --variant vNNN` vía el intérprete definido por el Makefile.
  - Preferible para ejecuciones automatizadas y reproducibles.

- `make script1-check-results VARIANT=vNNN`
  - Verifica la existencia de los artefactos principales en `executions/01_explore/$(VARIANT)`.

- `make script1-check-dvc`
  - Ejecuta comprobaciones DVC locales/remotas (si usas DVC).

- `make publish1 VARIANT=vNNN` (se dejará para cuando publiques)
  - Valida la variante con `mlops4ofp/tools/traceability.py` y registra artefactos en DVC/git.

- `make remove1 VARIANT=vNNN`
  - Elimina la carpeta de la variante y actualiza el registro de variantes (solo si no tiene hijos).

- `make clean1-all`
  - Elimina todas las variantes de la Fase 01 y su `variants.yaml` (limpieza local).

## Flujo de trabajo recomendado (pasos principales)
1. Crear la variante (parámetros):
   - `make variant1 VARIANT=v001 RAW=./data/raw.csv CLEANING_STRATEGY=basic NAN_VALUES='[-999999]'
`
   - Esto registra la variante (crea `executions/01_explore/v001/params.yaml`).
2. Ejecutar el `notebook` para exploración interactiva (opcional):
   - `make nb1-run VARIANT=v001` — abre/ejecuta el notebook in-place y escribe figuras/informes.
   - El notebook respeta la variable de entorno `ACTIVE_VARIANT` para cargar parámetros.
3. Ejecutar la `script` para producción/reproducción:
   - `make script1-run VARIANT=v001` — generará el parquet y los artefactos en `executions/01_explore/v001/`.
4. Verificar resultados:
   - `make script1-check-results VARIANT=v001` — asegurarse que los archivos esperados están presentes.
   - `make script1-check-dvc` — opcional, verificar estado DVC.
5. Si procede, publicar los artefactos con DVC/git (pendiente en este repo):
   - `make publish1 VARIANT=v001` — solo una vez que quieras añadir los artefactos al control remoto.

## Recomendaciones y notas prácticas
- Usa el `notebook` para entender salidas, inspeccionar estadísticas y ajustar parámetros. Una vez definidos, usa la `script` para ejecutar en batch.
- Las variantes deben nombrarse `vNNN` (ej.: `v001`) para mantener trazabilidad.
- Si no vas a usar DVC inmediatamente, la publicación puede posponerse; en este repo `dvc.yaml` ha sido movido a `legacy/` para evitar confusión.
- Si quieres reproducir exactamente el entorno, activa el virtualenv del proyecto: `source .venv/bin/activate`.

## Ejemplo rápido
1. Crear variante y ejecutar todo (interactivo + reproducible):
```bash
make variant1 VARIANT=v001 RAW=./data/raw.csv CLEANING_STRATEGY=basic NAN_VALUES='[-999999]'
make nb1-run VARIANT=v001      # inspeccionar/ajustar en notebook
make script1-run VARIANT=v001  # ejecución reproducible
make script1-check-results VARIANT=v001
```

---

Si quieres, puedo agregar ejemplos más detallados de valores para `CLEANING_STRATEGY` y `ERROR_VALUES`, o generar una plantilla `params/01_explore/example_params.yaml` para acelerar la creación de variantes.
