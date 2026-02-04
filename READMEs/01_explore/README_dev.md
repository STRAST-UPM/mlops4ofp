# README – Fase 01 (Equipo de Desarrollo)

## 1. Flujo de trabajo
### Crear variante
```bash
make variant1 VARIANT=v001 RAW=data/raw.csv CLEANING_STRATEGY=basic NAN_VALUES="[-999999]" 
```

### Ejecutar notebook
```bash
make nb1-run VARIANT=v001
```

### Ejecutar script
```bash
make script1-run VARIANT=v001
```

### Publicar variante
```bash
make publish1 VARIANT=v001
```
