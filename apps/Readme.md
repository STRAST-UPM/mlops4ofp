# Aplicaciones de visualización de datos
## Índice
* [Aplicación Temporal](#aplicación-temporal)
  * [1. Modo temporal](#1-modo-temporal)
  * [2. Modo salto de evento](#2-modo-salto-de-evento)
* [Aplicación analizador de ventanas](#aplicación-analizador-de-ventanas)

---
## Aplicación Temporal
### 1. Modo temporal
>http://localhost:8050

Para arrancar la aplicación utilizando el dataset por defecto `v001`, ejecuta:
```bash
make run_temporal_app
```
Si quieres utilizar otro dataset por defecto, puedes indicarlo mediante el siguiente comando. En este caso, `v002` hace referencia a un dataset procesado en el directorio `executions/01_explore`:
```bash
make run_temporal_app df=v002
```
> [!WARNING]
> Si el dataset configurado por defecto no existe, la aplicación no funcionará y se producirán errores al no poder encontrarlo.

Para detener la aplicación, basta con ejecutar:
```bash
make stop_temporal_app
```
---
### 2. Modo salto de evento
Para arrancar la aplicación en modo **salto de evento**, es necesario iniciarla de la siguiente manera:
```bash
make run_temporal_app df=v002 em=true
```
Una vez iniciada, en la esquina superior derecha se podrá cambiar el dataset. Existen dos tipos de datasets disponibles:

1. **MDS-COMPLETE-vXXX**
   * Datasets procesados en el directorio `executions/01_explore`.

2. **MDS-COMPLETE-TvXXX-EvYYY**
   * Datasets compuestos a partir de `executions/01_explore` y `executions/02_prepareeventsds`.
   * `EvYYY` hace referencia al dataset contenido en `02_prepareeventsds`.
   * `TvXXX` hace referencia al dataset **parent** del mismo.

La primera vez que se selecciona un dataset del tipo 2 (*MDS-COMPLETE-TvXXX-EvYYY*), será necesario esperar un tiempo hasta que sea procesado por la aplicación. Durante este proceso, se mostrará el mensaje **Updating...** en la parte superior de la pestaña.

Una vez procesado, el archivo será almacenado en el directorio:
```
apps/temporal_app/epoch_processed
```

De esta forma, cuando se vuelva a cargar el mismo dataset, no será necesario reprocesarlo.

> [!NOTE]
> Para que la visualización funcione correctamente, es necesario seleccionar tanto las medidas del evento del componente `from_to` (salto del evento) como las del componente al que hace referencia, para que el cambio de evento pueda mostrarse correctamente.

---
## Aplicación analizador de ventanas
> http://localhost:8060

Para arrancar la aplicación es necesario seleccionar el dataset de ventanas a analizar, ubicado en el directorio `executions/03_preparewindowsds`. En este ejemplo, se utiliza el dataset **v001**:
```bash 
make run_windows_app ws=v001
```
Para detener la aplicación, basta con ejecutar:
```bash 
make stop_windows_app
```
Todas las busquedas realizadas se pueden consultar en el directorio `apps/windows_app/files_output`


---

## Debug
1. Aplicación Temporal 
```bash 
docker logs mds_temporal -f
```
2. Aplicación analizador de ventanas
```bash 
docker logs mds_windows -f
```
