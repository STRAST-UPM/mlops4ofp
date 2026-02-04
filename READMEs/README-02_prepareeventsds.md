# Fase 02 — PrepareEventsDS

Este documento explica cómo trabajar con la Fase 02 (`02_prepareeventsds`) del pipeline: objetivos `make`, parámetros relevantes, entradas y salidas esperadas, y un resumen de los pasos principales. El notebook y la script de esta fase realizan tareas equivalentes.

## Propósito de la fase
- Generar el dataset de **eventos** a partir del dataset explorado de la Fase 01.
- Detectar eventos mediante estrategias de niveles, transiciones o ambas.
- Generar un catálogo de eventos (nombre → ID), estadísticas min/max y un informe.
- Producir un dataset intermedio de eventos listo para la Fase 03.

## Ubicaciones clave
- Scripts/notebook: `notebooks/02_prepareeventsds.ipynb`, `scripts/02_prepareeventsds.py`
- Parámetros base: `executions/02_prepareeventsds/base_params.yaml`
- Variantes y artefactos: `executions/02_prepareeventsds/<VARIANT>/`

## Entradas requeridas
Para ejecutar la Fase 02, necesitas:
- Una variante de la **Fase 01** (padre) que ya haya generado sus artefactos.
- Tu variante de la Fase 02 debe tener un `parent_variant` que apunte a una variante existente de F01.

## Artefactos generados (salidas típicas)
En `executions/02_prepareeventsds/<VARIANT>/` normalmente encontrarás:
- `02_prepareeventsds_dataset.parquet` — dataset de eventos (principal salida)
- `02_prepareeventsds_bands.json` — bandas de detección de eventos
- `02_prepareeventsds_event_catalog.json` — catálogo de eventos (nombre → ID)
- `02_prepareeventsds_metadata.json` — metadatos del procesamiento
- `02_prepareeventsds_params.json` o `params.yaml` — parámetros aplicados a la variante
- `02_prepareeventsds_report.html` — informe de exploración (figuras, tablas)
- `figures/` — figuras generadas (conteos de eventos, inter-llegadas, etc.)

## Parámetros y objetivos `make` de la fase

Resumen de los objetivos más usados:

- `make variant2 VARIANT=vNNN PARENT=vMMM BANDS="40 60 90" STRATEGY=both NAN=keep [Tu=<opcional>]`
  - `VARIANT`: identificador `vNNN` (obligatorio). Ej.: `v011`.
  - `PARENT`: variante padre de Fase 01 (obligatorio). Ej.: `v001`.
  - `BANDS`: lista de porcentajes de corte para bandas de detección (ej.: `"40 60 90"`).
  - `STRATEGY`: estrategia de eventos (`levels`, `transitions`, o `both`).
  - `NAN`: manejo de NaN (`keep` o `discard`).
  - `Tu`: opcional, paso temporal característico (ej.: `3600` segundos). Si no se especifica, se obtiene de la metadata de F01.

- `make nb2-run VARIANT=vNNN`
  - Ejecuta `notebooks/02_prepareeventsds.ipynb` in-place con `ACTIVE_VARIANT=VARIANT`.
  - Útil para inspección interactiva del dataset de eventos y figuras.

- `make script2-run VARIANT=vNNN`
  - Ejecuta `scripts/02_prepareeventsds.py --variant vNNN`.
  - Preferible para ejecuciones automatizadas y reproducibles.

- `make script2-check-results VARIANT=vNNN`
  - Verifica la existencia de los artefactos principales en `executions/02_prepareeventsds/$(VARIANT)`.

- `make script2-check-dvc`
  - Ejecuta comprobaciones DVC locales/remotas.

- `make publish2 VARIANT=vNNN` (se dejará para cuando publiques)
  - Valida la variante con `mlops4ofp/tools/traceability.py` y registra artefactos en DVC/git.

- `make remove2 VARIANT=vNNN`
  - Elimina la carpeta de la variante (solo si no tiene hijos).

- `make clean2-all`
  - Elimina todas las variantes de la Fase 02 y su `variants.yaml`.

## Flujo de trabajo recomendado (pasos principales)
1. Crear la variante (parámetros):
   - `make variant2 VARIANT=v011 PARENT=v001 BANDS="40 60 90" STRATEGY=both NAN=keep`
   - Esto registra la variante (crea `executions/02_prepareeventsds/v011/params.yaml`).
2. Ejecutar el notebook para exploración interactiva (opcional):
   - `make nb2-run VARIANT=v011` — inspecciona estadísticas de eventos y figuras.
3. Ejecutar la script para producción:
   - `make script2-run VARIANT=v011` — generará el parquet y los artefactos.
4. Verificar resultados:
   - `make script2-check-results VARIANT=v011` — asegurarse que los archivos esperados están presentes.
5. Proceder a la Fase 03 usando `v011` como padre:
   - `make variant3 VARIANT=v111 PARENT=v011 OW=600 LT=300 PW=600 WS=synchro NAN=preserve`

## Recomendaciones y notas prácticas
- **Dependencia de Fase 01**: la variante padre (ej.: `v001`) debe haber completado `script1-run` antes de ejecutar `script2-run`.
- Experimenta con diferentes valores de `BANDS` y `STRATEGY` para ajustar la detección de eventos.
- `Tu` (paso temporal) normalmente se obtiene automáticamente de la metadata de F01; úsalo solo si necesitas override.
- Las variantes deben nombrarse `vNNN` manteniendo la convención: F01 → v001..v0NN, F02 → v01N..v0NM, F03 → v1NN..v1NM.

## Ejemplo rápido
```bash
make variant2 VARIANT=v011 PARENT=v001 BANDS="40 60 90" STRATEGY=both NAN=keep
make nb2-run VARIANT=v011      # inspeccionar en notebook
make script2-run VARIANT=v011  # ejecución reproducible
make script2-check-results VARIANT=v011
```

---

Una vez completada la Fase 02 con éxito, procede a crear variantes de la Fase 03 usando `v011` (u otra variante de F02) como padre.
