# params/

Este repositorio usa un esquema **phase/variant**.

Todo lo generado por las fases 01–03 se almacena en:

- params/<fase>/<variante>/

Ejemplos:
- params/01_explore/v001/
- params/02_prepareeventsds/v001/
- params/03_preparewindowsds/v001/

Cada carpeta de variante contiene:
- `params.yaml` (parámetros de entrada de la fase)
- `*_params_effective.yaml` o equivalente (parámetros resueltos/efectivos, si aplica)
- `*_dataset.parquet` (dataset generado por la fase, si aplica)
- `metadata/` (resúmenes, mapeos, estadísticas)
- `reports/` (informes en HTML/PDF/MD, si aplica)
- `figures/` (figuras exportadas)

Nota: los notebooks y los scripts escriben en la **misma ruta** para una fase+variante;
si se ejecutan ambos, el último en ejecutarse machaca los artefactos previos.
