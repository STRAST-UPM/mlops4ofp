#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Convierte un dataset WindowsDS en formato Parquet a CSV.

Entrada:
- Parquet con columnas:
    - OW_events : list[int]
    - PW_events : list[int]

Salida:
- CSV con las mismas columnas,
  serializando las listas como texto.
"""

import sys
from pathlib import Path
import argparse
import pandas as pd

# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(
        description="Convert WindowsDS Parquet to CSV"
    )
    p.add_argument(
        "input_parquet",
        type=Path,
        help="Ruta al fichero windowsds.parquet",
    )
    p.add_argument(
        "output_csv",
        type=Path,
        help="Ruta de salida del CSV",
    )
    return p.parse_args()

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    args = parse_args()

    if not args.input_parquet.exists():
        print(f"❌ No existe el fichero: {args.input_parquet}")
        sys.exit(1)

    print(f"📂 Leyendo Parquet: {args.input_parquet}")
    df = pd.read_parquet(args.input_parquet)

    # Comprobación mínima de contrato
    expected_cols = {"OW_events", "PW_events"}
    if set(df.columns) != expected_cols:
        print("❌ El dataset no tiene el esquema esperado.")
        print("   Columnas encontradas:", list(df.columns))
        print("   Columnas esperadas  :", sorted(expected_cols))
        sys.exit(1)

    # Serialización explícita de listas → texto
    df = df.copy()
    df["OW_events"] = df["OW_events"].apply(lambda x: " ".join(map(str, x)))
    df["PW_events"] = df["PW_events"].apply(lambda x: " ".join(map(str, x)))

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    print(f"💾 Escribiendo CSV: {args.output_csv}")
    df.to_csv(args.output_csv, index=False)

    print("✔ Conversión completada")
    print(f"  Filas : {len(df):,}")
    print(f"  Columnas : {list(df.columns)}")

# ---------------------------------------------------------
if __name__ == "__main__":
    main()
