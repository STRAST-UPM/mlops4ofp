# Guía — Equipo de desarrollo

Pipeline phase/variant para generación reproducible de datasets OFP.

## Instalación
Leer instrucciones de creación de cuentas en setup/remote.yaml

```bash
git clone <URL_DEL_REPOSITORIO>
cd mlops4ofp
make setup SETUP_CFG=setup/remote.yaml
```

## Dataset de entrada

Dataset base local en:

```
data/
```

## Ejecución reproducible

```bash
make variant1 VARIANT=v001 RAW=./data/raw.csv CLEANING=basic NANVALUES='[-999999.0]'
make script1-run VARIANT=v001

make variant2 VARIANT=v011 PARENT=v001 BANDS="5 15 25 40 60 75 85 95" STRATEGY=transitions NAN=keep
make script2-run VARIANT=v011

make variant3 VARIANT=v111 PARENT=v011 OW=10 LT=1 PW=2 WS=synchro NAN=discard
make script3-run VARIANT=v111
```

## Export de datasets

```bash
make export-f03 VARIANT=vXXX PARENT_VARIANT=vYYY
```
