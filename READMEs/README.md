# MLOps4OFP — Fases 01–03

Este repositorio implementa las **tres primeras fases** de un workflow MLOps
para **Online Failure Prediction (OFP)**, centradas exclusivamente en la
**preparación de datasets** (sin entrenamiento de modelos).

## Fases incluidas

- **Fase 01 — explore**  
  Exploración inicial y validación del dataset base.

- **Fase 02 — prepareEventsDS**  
  Discretización de señales y generación de un dataset de eventos.

- **Fase 03 — prepareWindowsDS**  
  Generación de ventanas de observación (OW) y predicción (PW), listas para ML.

## Requisitos

- Python ≥ 3.10
- GNU Make
- Git

No se requiere DVC ni MLflow en esta versión.

## Instalación (desde cero)

```bash
git clone <URL_DEL_REPOSITORIO>
cd mlops4ofp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Dataset de entrada

El dataset base debe colocarse en la carpeta:

```
data/
```

Este repositorio **no descarga datos automáticamente**.

## Ejecución completa (01 → 02 → 03)

```bash
make variant1 VARIANT=v001 RAW=./data/raw.csv CLEANING=basic NANVALUES='[-999999.0]'
make nb1-run VARIANT=v001
make script1-run VARIANT=v001

make variant2 VARIANT=v011 PARENT=v001 BANDS="5 15 25 40 60 75 85 95" STRATEGY=transitions NAN=keep
make nb2-run VARIANT=v011
make script2-run VARIANT=v011

make variant3 VARIANT=v111 PARENT=v011 OW=10 LT=1 PW=2 WS=synchro NAN=discard
make nb3-run VARIANT=v111
make script3-run VARIANT=v111
```

Los notebooks y los scripts escriben en la misma ruta:
`params/<fase>/<variante>/`.

## Export de datasets para ML externo

```bash
make export-f03 VARIANT=vXXX PARENT_VARIANT=vYYY
```

Resultado:
`exports/03_preparewindowsds/vXXX/`
