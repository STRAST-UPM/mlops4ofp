# README — Estudiantes
Fase 03 · PrepareWindowsDS

## Objetivo
En esta fase se transforma el dataset de eventos (F02) en un dataset de ventanas temporales (F03),
que servirá como entrada para el entrenamiento de modelos.

Cada fila representa una ventana OW / LT / PW expresada como índices sobre el dataset F02.

## Requisitos previos
- Fase 01 y Fase 02 completadas
- Python 3.10+
- Entorno virtual activado
- Proyecto clonado e instalado

## Flujo de trabajo

### 1. Crear variante
```bash
make variant3 VARIANT=v001
```

Editar:
params/03_preparewindowsds/v001/params.yaml

### 2. Ejecutar script
```bash
make script3-run VARIANT=v001
```

## Resultados esperados
En:
params/03_preparewindowsds/v001/

- 03_preparewindowsds_dataset.parquet
- 03_preparewindowsds_metadata.json
- 03_preparewindowsds_stats.json
- 03_preparewindowsds_report.html
- figures/

## Qué no hacer
- No modificar el script
- No cambiar el schema
- No cargar el dataset completo en memoria

## Evaluación
Se evaluará la correcta ejecución, coherencia de parámetros y reproducibilidad.
