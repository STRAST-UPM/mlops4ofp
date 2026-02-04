#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fase 03 — prepareWindowsDS

Genera el dataset FINAL de ventanas:
- OW_events: lista de códigos de eventos en la ventana de observación
- PW_events: lista de códigos de eventos en la ventana de predicción
"""

# =====================================================================
# IMPORTS
# =====================================================================
import sys
from pathlib import Path
import argparse
import json
from bisect import bisect_left
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

# =====================================================================
# BOOTSTRAP
# =====================================================================
SCRIPT_PATH = Path(__file__).resolve()
ROOT = SCRIPT_PATH
for _ in range(10):
    if (ROOT / "mlops4ofp").exists():
        break
    ROOT = ROOT.parent
else:
    raise RuntimeError("No se pudo localizar project root")

sys.path.insert(0, str(ROOT))

# =====================================================================
# IMPORTS PROYECTO
# =====================================================================
from mlops4ofp.tools.run_context import (
    detect_execution_dir,
    detect_project_root,
    assemble_run_context,
)

# =====================================================================
# CONSTANTES
# =====================================================================
PHASE = "03_preparewindowsds"

# =====================================================================
# CLI
# =====================================================================
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--variant", required=True)
    p.add_argument("--execution-dir", type=Path, default=None)
    return p.parse_args()

# =====================================================================
# MAIN
# =====================================================================
def main():
    args = parse_args()

    execution_dir = detect_execution_dir()
    project_root = detect_project_root(execution_dir)

    variant_root = (
        project_root
        / "executions"
        / PHASE
        / args.variant
    )

    ctx = assemble_run_context(
        project_root=project_root,
        phase=PHASE,
        variant=args.variant,
        variant_root=variant_root,
        execution_dir=args.execution_dir,
    )

    # -----------------------------------------------------------------
    # Cargar parámetros F03
    # -----------------------------------------------------------------
    with open(variant_root / "params.yaml", "r", encoding="utf-8") as f:
        params = yaml.safe_load(f)

    OW = int(params["OW"])
    LT = int(params["LT"])
    PW = int(params["PW"])
    nan_strategy = params.get("nan_strategy", "discard")
    window_strategy = params.get("window_strategy", "synchro")
    parent_variant = params["parent_variant"]
    parent_phase = params.get("parent_phase", "02_prepareeventsds")

    # -----------------------------------------------------------------
    # Cargar metadata F02 para Tu
    # -----------------------------------------------------------------
    with open(
        project_root
        / "executions"
        / parent_phase
        / parent_variant
        / f"{parent_phase}_metadata.json",
        "r",
        encoding="utf-8",
    ) as f:
        meta_f02 = json.load(f)

    Tu_raw = params.get("Tu", None)
    if Tu_raw is not None:
        Tu = float(Tu_raw)
    else:
        Tu_f02 = meta_f02.get("Tu", None)
        if Tu_f02 is None:
            raise RuntimeError(
                "No se pudo determinar Tu: es None en F03 params y en F02 metadata"
            )
        Tu = float(Tu_f02)


    # -----------------------------------------------------------------
    # Cargar dataset F02
    # -----------------------------------------------------------------
    input_dataset = (
        project_root
        / "executions"
        / parent_phase
        / parent_variant
        / f"{parent_phase}_dataset.parquet"
    )

    df = pq.read_table(input_dataset).to_pandas(
        split_blocks=True,
        self_destruct=True,
    )

    if not df["segs"].is_monotonic_increasing:
        df = df.sort_values("segs", kind="mergesort").reset_index(drop=True)

    times = df["segs"].to_numpy(dtype=np.int64, copy=False)
    events = df["events"].to_numpy()

    # -----------------------------------------------------------------
    # Cargar catálogo NaN
    # -----------------------------------------------------------------
    with open(
        project_root
        / "executions"
        / parent_phase
        / parent_variant
        / f"{parent_phase}_event_catalog.json",
        "r",
        encoding="utf-8",
    ) as f:
        catalog = json.load(f)

    nan_codes = {
        code for name, code in catalog.items()
        if name.endswith("_NaN_NaN")
    }

    has_nan = np.array(
        [
            any(ev in nan_codes for ev in evs)
            for evs in events
        ],
        dtype=bool,
    )

    # -----------------------------------------------------------------
    # Ventanas
    # -----------------------------------------------------------------
    OW_end = OW
    PW_start = OW + LT
    PW_end = OW + LT + PW

    def window_start_iterator():
        t_min = times[0]
        t_max = times[-1]
        total = PW_end * Tu

        if window_strategy == "synchro":
            t = t_min
            while t + total <= t_max:
                yield t
                t += Tu
        else:
            raise ValueError("Estrategia no soportada")

    def idx_range(t0, t1):
        return bisect_left(times, t0), bisect_left(times, t1)

    # -----------------------------------------------------------------
    # Escritura Parquet FINAL
    # -----------------------------------------------------------------
    output_path = variant_root / f"{PHASE}_dataset.parquet"

    schema = pa.schema([
        ("OW_events", pa.list_(pa.int32())),
        ("PW_events", pa.list_(pa.int32())),
    ])

    writer = pq.ParquetWriter(output_path, schema, compression="snappy")

    BATCH = 10_000
    rows = []

    windows_total = 0
    windows_written = 0

    for t0 in window_start_iterator():
        windows_total += 1

        i_ow_0, i_ow_1 = idx_range(t0, t0 + OW * Tu)
        i_pw_0, i_pw_1 = idx_range(
            t0 + PW_start * Tu,
            t0 + PW_end * Tu,
        )

        if i_ow_0 == i_ow_1 or i_pw_0 == i_pw_1:
            continue

        if nan_strategy == "discard":
            if has_nan[i_ow_0:i_ow_1].any():
                continue
            if has_nan[i_pw_0:i_pw_1].any():
                continue

        ow_events = [
            ev for evs in events[i_ow_0:i_ow_1] for ev in evs
        ]
        pw_events = [
            ev for evs in events[i_pw_0:i_pw_1] for ev in evs
        ]

        rows.append({
            "OW_events": ow_events,
            "PW_events": pw_events,
        })

        windows_written += 1

        if len(rows) >= BATCH:
            writer.write_table(pa.Table.from_pylist(rows, schema))
            rows.clear()

    if rows:
        writer.write_table(pa.Table.from_pylist(rows, schema))

    writer.close()

    # -----------------------------------------------------------------
    # Metadata mínima
    # -----------------------------------------------------------------
    metadata = {
        "phase": PHASE,
        "variant": args.variant,
        "parent_variant": parent_variant,
        "Tu": Tu,
        "OW": OW,
        "LT": LT,
        "PW": PW,
        "windows_total": windows_total,
        "windows_written": windows_written,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(variant_root / f"{PHASE}_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print("✔ F03 FINAL generado")
    print(f"  Dataset : {output_path}")
    print(f"  Ventanas: {windows_written:,}")

# =====================================================================
if __name__ == "__main__":
    main()

