# README (Estudiantes) – Fase 02: prepareEventsDS

## 1. Objetivo
Convertir el dataset explorado de Fase 01 en un dataset de eventos.

## 2. Pasos a seguir

### 2.1 Crear variante F02
```
make variant2 VARIANT=v010 BANDS="40 60 90" STRATEGY=both NAN=keep PARENT=v001
```

### 2.2 Ejecutar el notebook
```
make nb2-run VARIANT=v010
```

Esto generará:
- dataset de eventos `.parquet`
- catálogo de eventos
- informe HTML
- figuras opcionales

## 3. Interpretación de resultados
- La columna `events` contiene IDs de eventos ocurridos en cada `segs`.
- El informe HTML resume recuentos y estadísticas.

