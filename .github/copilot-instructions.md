Propósito
-------
Estas instrucciones ayudan a agentes de codificación a entender rápidamente la arquitectura, flujos y convenciones de este repositorio MLOps (mlops4ofp) para ser productivos sin contexto humano adicional.

Visión general (big picture)
----------------------------
- Pipeline en 3 fases: 01_explore → 02_prepareeventsds → 03_preparewindowsds. Cada fase tiene una carpeta `executions/<fase>/vNNN` que contiene artefactos (parquet, json, html/pdf) y un registro `variants.yaml`.
- Flujo de datos: datasets RAW (carpeta `data/` o path externo) → variantes de fase 01 → variantes de fase 02 (referencian `parent` de fase 01) → variantes de fase 03 (referencian `parent` de fase 02).
- Las variantes se gestionan por `mlops4ofp/tools/params_manager.py` y se validan con `mlops4ofp/tools/traceability.py`.

Comandos y flujos críticos (ejemplos reales)
-------------------------------------------
- Crear entorno y setup del proyecto: `make setup SETUP_CFG=setup/example_setup.yaml` o `make setup` (usa `setup/setup.py`).
- Verificar setup: `make check-setup` (ejecuta `setup/check_env.py` y `setup/check_setup.py`).
- Crear variante Fase 01: 
  `make variant1 VARIANT=v001 RAW=./data/raw.csv CLEANING=basic NAN_VALUES='[-999999]'`
- Ejecutar notebook de fase: `make nb1-run VARIANT=v001` (usa `jupyter nbconvert --execute` y exporta resultados a `executions/01_explore/v001`).
- Ejecutar script de fase: `make script1-run VARIANT=v001` (`scripts/01_explore.py --variant v001`).
- Publicar variante (DVC + git): `make publish1 VARIANT=v001` — agrega artefactos con `dvc add`, fuerza `git add -f` de `.dvc`, `git commit` (or `|| true`), `git push`, `dvc push`.
- Reproducir pipeline con DVC: `make script1-repro` → `dvc repro <stage>` y luego `dvc push`.

Convenciones y patrones específicos
---------------------------------
- Nombres de variante: estrictamente `vNNN` (ej.: `v001`). Targets `make` validan el formato con `check-variant-format`.
- Estructura de artefactos: `executions/<phase>/vNNN/` contiene `*_params.json|yaml`, `*_report.html|pdf`, `*.parquet`, y `figures/`.
- Registro de variantes: `executions/<phase>/variants.yaml` es la fuente de verdad para variantes disponibles.
- Notebooks: se ejecutan in-place con `jupyter nbconvert --execute` y usan la variable de entorno `ACTIVE_VARIANT` para comportamientos condicionados dentro del notebook.
- Intérprete Python: Makefile selecciona `.venv/bin/python3` si existe; de lo contrario `python3`. Prefiera ejecutar comandos con `make` para coherencia.

Integraciones externas importantes
---------------------------------
- DVC: operaciones con `dvc add`, `dvc push`, `dvc status -r storage -c`. Remote por defecto usado en Makefile es `storage`.
- Git: las publicaciones aplican `git add -f` para archivos DVC, tags por fase (`stable-fase01`, `stage-ready-fase02`, ...).
- Remotos / Dagshub: scripts en `setup/` para alternar remotes (`setup/switch_remote_*`).
- Posible MLflow / trazabilidad: variables de entorno cargadas desde `.mlops4ofp/env.sh` si existe; Makefile incluye automáticamente este fichero.

Archivos y ubicaciones que revisar primero
---------------------------------------
- `Makefile` — mapa de targets y ejemplos de uso (ej.: `variant1`, `publish1`, `nb*-run`, `script*-run`).
- `mlops4ofp/tools/params_manager.py` — lógica de creación/actualización/eliminación de variantes.
- `mlops4ofp/tools/traceability.py` — validaciones `validate-variant` y `can-delete`.
- `scripts/01_explore.py`, `scripts/02_prepareeventsds.py`, `scripts/03_preparewindowsds.py` — entradas CLI para ejecución programática.
- `executions/` — ejemplo real de variantes ya generadas (estructura y artefactos).

Puntos de precaución para agentes
---------------------------------
- No asumir que `python3` es el del entorno virtual: use `make` targets o `.venv/bin/python3`.
- Los `git commit` en Makefile usan `|| true` (no bloquean), pero al publicar conviene comprobar `git status` antes de tags o pushes (`push2-stable` muestra comprobaciones).
- Los notebooks dependen de `ACTIVE_VARIANT`; si se editan para reproducibilidad, mantener esa convención.

Cómo contribuir cambios automáticos (ejemplo de pasos recomendados)
-----------------------------------------------------------------
1. Usar `make variant<N>` para crear variante de prueba.
2. Ejecutar `make script<N>-run VARIANT=vNNN` o `make nb<N>-run VARIANT=vNNN`.
3. Validar con `make script<N>-check-results VARIANT=vNNN`.
4. Publicar con `make publish<N> VARIANT=vNNN` (esto hará `dvc add` + `git push` + `dvc push`).

Si algo falta o es confuso
-------------------------
Por favor, indica qué sección quieres ampliar (por ejemplo: ejemplos de `params_manager` o cómo funcionan `variants.yaml`) y actualizaré el archivo.
