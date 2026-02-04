# Fase 03 — PrepareWindowsDS

Este documento explica cómo trabajar con la Fase 03 (`03_preparewindowsds`), la fase final del pipeline: objetivos `make`, parámetros relevantes, entradas y salidas esperadas, y un resumen de los pasos principales. El notebook y la script de esta fase realizan tareas equivalentes.

## Propósito de la fase
- Generar el dataset FINAL de **ventanas temporales** a partir del dataset de eventos (Fase 02).
- Cada fila contiene una ventana de observación (OW) y una ventana de predicción (PW) con sus eventos materializados.
- Soportar múltiples estrategias de alineación de ventanas (sincronia, asincronia, etc.).
- Generar un dataset parquet listo para modelos predictivos junto con metadatos y reportes.

## Ubicaciones clave
- Scripts/notebook: `notebooks/03_preparewindowsds.ipynb`, `scripts/03_preparewindowsds.py`
- Parámetros base: `executions/03_preparewindowsds/base_params.yaml`
- Variantes y artefactos: `executions/03_preparewindowsds/<VARIANT>/`
- Exportación (opcional): `exports/03_preparewindowsds/<VARIANT>/` (via `make export3`).

## Entradas requeridas
Para ejecutar la Fase 03, necesitas:
- Una variante de la **Fase 02** (padre) que ya haya generado sus artefactos (incluyendo el catálogo de eventos).
- Tu variante de la Fase 03 debe tener un `parent_variant` que apunte a una variante existente de F02.

## Artefactos generados (salidas típicas)
En `executions/03_preparewindowsds/<VARIANT>/` normalmente encontrarás:
- `03_preparewindowsds_dataset.parquet` — dataset de ventanas (principal salida, listo para ML)
- `03_preparewindowsds_metadata.json` — metadatos (conteos, rangos, estrategia)
- `03_preparewindowsds_stats.json` — estadísticas detalladas del dataset
- `03_preparewindowsds_params.json` o `params.yaml` — parámetros aplicados a la variante
- `03_preparewindowsds_report.html` — informe final con tablas y figuras
- `figures/` — figuras generadas

## Parámetros y objetivos `make` de la fase

Resumen de los objetivos más usados:

- `make variant3 VARIANT=vNNN PARENT=vMMM OW=<int> LT=<int> PW=<int> WS=<strategy> NAN=<strategy>`
  - `VARIANT`: identificador `vNNN` (obligatorio). Ej.: `v111`.
  - `PARENT`: variante padre de Fase 02 (obligatorio). Ej.: `v011`.
  - `OW`: tamaño de la ventana de observación en segundos (ej.: `600`).
  - `LT`: lag temporal (delay) entre ventana de observación y predicción en segundos (ej.: `300`).
  - `PW`: tamaño de la ventana de predicción en segundos (ej.: `600`).
  - `WS`: estrategia de alineación (`synchro`, `asynOW`, `withinPW`, `asynPW`, etc.).
  - `NAN`: manejo de NaN (`preserve` o `discard`).

- `make nb3-run VARIANT=vNNN`
  - Ejecuta `notebooks/03_preparewindowsds.ipynb` in-place con `ACTIVE_VARIANT=VARIANT`.
  - Útil para inspección del dataset de ventanas y validación de parámetros.

- `make script3-run VARIANT=vNNN`
  - Ejecuta `scripts/03_preparewindowsds.py --variant vNNN`.
  - Preferible para ejecuciones automatizadas y reproducibles.

- `make script3-check-results VARIANT=vNNN`
  - Verifica la existencia de los artefactos principales en `executions/03_preparewindowsds/$(VARIANT)`.

- `make script3-check-dvc`
  - Ejecuta comprobaciones DVC locales/remotas.

- `make export3 VARIANT=vNNN PARENT=vMMM`
  - Exporta el dataset final, metadatos y catálogo de eventos a `exports/03_preparewindowsds/$(VARIANT)/`.
  - Útil para compartir o integrar con otros sistemas.

- `make publish3 VARIANT=vNNN` (se dejará para cuando publiques)
  - Valida la variante con `mlops4ofp/tools/traceability.py` y registra artefactos en DVC/git.

- `make remove3 VARIANT=vNNN`
  - Elimina la carpeta de la variante (solo si no tiene hijos).

- `make clean3-all`
  - Elimina todas las variantes de la Fase 03 y su `variants.yaml`.

## Flujo de trabajo recomendado (pasos principales)
1. Crear la variante (parámetros):
   - `make variant3 VARIANT=v111 PARENT=v011 OW=600 LT=300 PW=600 WS=synchro NAN=preserve`
   - Esto registra la variante (crea `executions/03_preparewindowsds/v111/params.yaml`).
2. Ejecutar el notebook para exploración (opcional):
   - `make nb3-run VARIANT=v111` — inspecciona ventanas, conteos y distribuciones.
3. Ejecutar la script para producción:
   - `make script3-run VARIANT=v111` — generará el parquet y los artefactos finales.
4. Verificar resultados:
   - `make script3-check-results VARIANT=v111` — asegurarse que los archivos esperados están presentes.
5. Exportar (opcional, si necesitas compartir):
   - `make export3 VARIANT=v111 PARENT=v011` — copia el dataset final a `exports/03_preparewindowsds/v111/`.

## Recomendaciones y notas prácticas
- **Dependencia de Fase 02**: la variante padre (ej.: `v011`) debe haber completado `script2-run` antes de ejecutar `script3-run`.
- Experimenta con diferentes valores de `OW`, `LT`, `PW` y `WS` para ajustar la estructura de ventanas.
- Los parámetros `OW`, `LT`, `PW` suelen ser múltiplos de `Tu` (paso temporal de F01).
- El dataset generado en esta fase es el dataset FINAL listo para entrenar modelos predictivos.
- `export3` es útil si necesitas compartir el dataset con otros equipos o sistemas sin acceso directo al repositorio.

## Ejemplo rápido
```bash
make variant3 VARIANT=v111 PARENT=v011 OW=600 LT=300 PW=600 WS=synchro NAN=preserve
make nb3-run VARIANT=v111      # inspeccionar en notebook
make script3-run VARIANT=v111  # ejecución reproducible
make script3-check-results VARIANT=v111
make export3 VARIANT=v111 PARENT=v011  # exportar si lo necesitas
```

---

Felicidades: al completar la Fase 03, tienes el dataset final listo para modelado predictivo. Los artefactos están en `executions/03_preparewindowsds/v111/` y, opcionalmente, en `exports/03_preparewindowsds/v111/`.
