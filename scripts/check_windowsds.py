#!/usr/bin/env python3

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------
# 0. Leer argumento
# ---------------------------------------------------------------------
if len(sys.argv) != 2:
    print("Uso:")
    print("  python check_windowsds.py <dataset.parquet>")
    sys.exit(1)

DATASET_PATH = Path(sys.argv[1])

if not DATASET_PATH.exists():
    print(f"❌ El fichero no existe: {DATASET_PATH}")
    sys.exit(1)

# ---------------------------------------------------------------------
# 1. Cargar dataset
# ---------------------------------------------------------------------
print(f"📂 Cargando dataset: {DATASET_PATH}")
df = pd.read_parquet(DATASET_PATH)

print("✔ Dataset cargado")
print(f"  Shape     : {df.shape}")
print(f"  Columnas  : {list(df.columns)}")
print()

# ---------------------------------------------------------------------
# 2. Comprobaciones estructurales
# ---------------------------------------------------------------------

# Debe tener filas
if len(df) == 0:
    raise AssertionError("❌ El dataset no tiene filas")

# Debe tener exactamente 2 columnas
if df.shape[1] != 2:
    raise AssertionError(
        f"❌ El dataset tiene {df.shape[1]} columnas, se esperaban exactamente 2"
    )

col_obs, col_pred = df.columns

print(f"Columna observación : {col_obs}")
print(f"Columna predicción  : {col_pred}")
print()

# ---------------------------------------------------------------------
# 3. Comprobación de contenido
# ---------------------------------------------------------------------
def check_event_column(series, name):
    for i, v in enumerate(series.head(50)):  # solo primeras filas
        if not isinstance(v, (list, tuple, np.ndarray)):
            raise AssertionError(
                f"❌ Columna '{name}', fila {i}: no es una lista ({type(v)})"
            )
        for ev in v:
            if not isinstance(ev, (int, np.integer)):
                raise AssertionError(
                    f"❌ Columna '{name}', fila {i}: evento no entero "
                    f"({ev}, {type(ev)})"
                )

check_event_column(df[col_obs], col_obs)
check_event_column(df[col_pred], col_pred)

# ---------------------------------------------------------------------
# 4. Resumen rápido
# ---------------------------------------------------------------------
lens_obs = df[col_obs].apply(len)
lens_pred = df[col_pred].apply(len)

print("✔ Dataset válido según el contrato esperado")
print()
print("Resumen:")
print(f"  Filas totales               : {len(df):,}")
print(f"  Media eventos observación   : {lens_obs.mean():.2f}")
print(f"  Media eventos predicción    : {lens_pred.mean():.2f}")
print(f"  Filas OW vacías             : {(lens_obs == 0).sum()}")
print(f"  Filas PW vacías             : {(lens_pred == 0).sum()}")
