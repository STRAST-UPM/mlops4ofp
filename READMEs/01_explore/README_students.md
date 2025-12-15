# README – Fase 01 (Estudiantes)

## 1. Preparación básica del entorno
1. Instalar Python 3.10+  
2. Crear entorno virtual:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Abrir el proyecto en VSCode (muy importante: **Open Folder**).

## 2. Crear una variante
```bash
make variant1 VARIANT=v001 RAW=data/raw.csv
```

## 3. Ejecutar notebook
```bash
make nb1-run VARIANT=v001
```
El notebook:
- Carga el dataset
- Diagnostica calidad
- Aplica limpieza
- Genera informe HTML

## 4. Qué entregar
- Informe HTML generado (*params/01_explore/v001/01_explore_report.html*)
- Comentarios breves sobre anomalías detectadas
