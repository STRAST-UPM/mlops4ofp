#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

import pyarrow.parquet as pq
import numpy as np

def main(parquet_path, strategy):
    parquet_path = Path(parquet_path)
    assert parquet_path.exists(), parquet_path

    print(f"[CHECK] leyendo {parquet_path}")
    table = pq.read_table(parquet_path)

    ow = table.column("OW_events").to_pylist()
    pw = table.column("PW_events").to_pylist()

    n = len(ow)
    print(f"[CHECK] ventanas totales: {n:,}")

    ow_lens = np.fromiter((len(x) for x in ow), dtype=np.int64)
    pw_lens = np.fromiter((len(x) for x in pw), dtype=np.int64)

    # ------------------------------------------------------------
    # Invariante 1: no pares totalmente vacíos
    # ------------------------------------------------------------
    empty_both = np.sum((ow_lens == 0) & (pw_lens == 0))
    print(f"[CHECK] pares OW=PW=∅ : {empty_both}")

    if empty_both != 0:
        print("❌ ERROR: hay pares con ambas ventanas vacías")
    else:
        print("✔ OK: no hay pares completamente vacíos")

    # ------------------------------------------------------------
    # Invariante 2: asynOW ⇒ OW no vacía
    # ------------------------------------------------------------
    if strategy == "asynOW":
        empty_ow = np.sum(ow_lens == 0)
        print(f"[CHECK] OW vacías (asynOW): {empty_ow}")

        if empty_ow != 0:
            print("❌ ERROR: asynOW tiene ventanas de observación vacías")
        else:
            print("✔ OK: todas las OW tienen al menos un evento")

    if strategy == "withinPW":
        empty_pw = np.sum(pw_lens == 0)
        print(f"[CHECK] PW vacías (withinPW): {empty_pw}")

    if strategy == "asynPW":
        empty_pw = np.sum(pw_lens == 0)
        print(f"[CHECK] PW vacías (asynPW): {empty_pw}")    
        
    # ------------------------------------------------------------
    # Estadísticas descriptivas (para comparar synchro vs asynOW)
    # ------------------------------------------------------------
    print("\n[STATS]")
    print(f"  OW  min / mean / max : {ow_lens.min()} / {ow_lens.mean():.1f} / {ow_lens.max()}")
    print(f"  PW  min / mean / max : {pw_lens.min()} / {pw_lens.mean():.1f} / {pw_lens.max()}")

    print("\n✔ CHECK FINALIZADO")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("uso: check_windows_dataset.py <dataset.parquet> <synchro|asynOW>")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
