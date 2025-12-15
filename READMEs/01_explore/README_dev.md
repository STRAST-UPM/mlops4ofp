# README – Fase 01 (Equipo de Desarrollo)

## 1. Preparación del entorno
1. Clonar el repositorio.
2. Crear entorno virtual:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Asegurar que `mlops4ofp` es importable (VSCode → Open Folder en raíz del proyecto).

## 2. Flujo de trabajo
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

## 3. Resultados esperados
- `params/01_explore/vXXX/` contiene todos los artefactos.
- `dvc push` sube los artefactos.
