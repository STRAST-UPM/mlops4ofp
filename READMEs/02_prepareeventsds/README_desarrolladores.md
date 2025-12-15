# README (Desarrolladores) – Fase 02: prepareEventsDS

Este documento explica cómo trabajar en el desarrollo, mantenimiento y prueba de la Fase 02 del pipeline MLOps4OFP.

## 1. Flujo de trabajo para desarrollo
1. Crear variante F02:
```
make variant2 VARIANT=vNNN BANDS="40 60 90" STRATEGY=both NAN=keep PARENT=vXXX
```

2. Ejecutar NB2:
```
make nb2-run VARIANT=vNNN
```

3. Ejecutar script:
```
make script2-run VARIANT=vNNN
```

## 2. Reglas para modificar el notebook
- Toda lógica de negocio debe ser portable a la script.
- No usar rutas absolutas.
- Actualizar parámetros en params_manager si se añaden nuevos.

## 3. Reglas para modificar la script
- Determinismo total.
- Replicar resultados del notebook.
- Mantener eficiencia: evitar iterrows.

## 4. Validación
- Comparar outputs de NB2 y script.
- Verificar catálogo, dataset, metadatos y recuentos.

