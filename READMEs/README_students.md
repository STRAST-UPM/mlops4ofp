# Guía rápida — Estudiantes

Este repositorio se utiliza para entender cómo se preparan datasets
para modelos de Online Failure Prediction (OFP).

## Preparar el entorno

```bash
git clone <URL_DEL_REPOSITORIO>
cd mlops4ofp
make setup SETUP_CFG=setup/local.yaml
```

## Dataset de entrada

Coloca el dataset base en:

```
data/
```

## Ejecución con notebooks

```bash
make variant1 VARIANT=v001 RAW=./data/raw.csv CLEANING=basic NANVALUES='[-999999.0]'
make nb1-run VARIANT=v001

make variant2 VARIANT=v011 PARENT=v001 BANDS="5 15 25 40 60 75 85 95" STRATEGY=transitions NAN=keep
make nb2-run VARIANT=v011

make variant3 VARIANT=v111 PARENT=v011 OW=10 LT=1 PW=2 WS=synchro NAN=discard
make nb3-run VARIANT=v111
```

No es necesario ejecutar los scripts.
