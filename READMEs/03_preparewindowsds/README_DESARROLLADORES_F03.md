# README — Desarrolladores
Fase 03 · PrepareWindowsDS

## Rol de la fase
Convierte eventos (F02) en ventanas temporales (F03) usando índices,
sin agregaciones, apto para datasets grandes y edge deployment.

## Entradas
- Dataset F02 (parquet)
- Event catalog F02
- Metadata F02

## Salidas
En params/03_preparewindowsds/<variant>/
- dataset.parquet
- metadata.json
- stats.json
- report.html
- figures/

## Schema F03
t0 (int64)
i_ow_0 (int32)
i_ow_1 (int32)
i_pw_0 (int32)
i_pw_1 (int32)

## Diseño
- Escritura incremental Parquet
- pyarrow.ParquetWriter
- Streaming, sin cargar todo en RAM

## Buenas prácticas
- Imports solo al inicio del script
- No lógica defensiva (make variant garantiza estado)
- Script debe ser 1:1 con el notebook

## Estado
Fase estable, CI-ready y preparada para F04.
