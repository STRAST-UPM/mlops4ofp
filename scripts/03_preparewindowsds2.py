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
from time import perf_counter

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

    print(f"[F03] inicio main | phase={PHASE} variant={args.variant}", flush=True)

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
    print(f"[F03] leyendo params: {variant_root / 'params.yaml'}", flush=True)
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
    print(
        f"[F03] leyendo metadata F02: "
        f"{project_root / 'executions' / parent_phase / parent_variant / f'{parent_phase}_metadata.json'}",
        flush=True,
    )
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

    print(
        f"[F03] Tu resuelto = {Tu} (origen: {'params' if Tu_raw is not None else 'F02_metadata'})",
        flush=True,
    )

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

    print(f"[F03] leyendo dataset F02: {input_dataset}", flush=True)
    t_read_start = perf_counter()
    df = pq.read_table(input_dataset).to_pandas(
        split_blocks=True,
        self_destruct=True,
    )
    t_read_elapsed = perf_counter() - t_read_start
    print(f"[F03] dataset F02 cargado en {t_read_elapsed:,.1f}s", flush=True)

    print("[F03] validando orden temporal...", flush=True)
    if not df["segs"].is_monotonic_increasing:
        t_sort_start = perf_counter()
        df = df.sort_values("segs", kind="mergesort").reset_index(drop=True)
        t_sort_elapsed = perf_counter() - t_sort_start
        print(f"[F03] ordenado en {t_sort_elapsed:,.1f}s", flush=True)
    else:
        print("[F03] orden temporal OK", flush=True)

    print("[F03] preparando arrays times/events...", flush=True)
    t_arr_start = perf_counter()
    times = df["segs"].to_numpy(dtype=np.int64, copy=False)
    events = df["events"].to_numpy()
    lengths = np.fromiter((len(evs) for evs in events), dtype=np.int64, count=len(events))
    offsets = np.empty(len(events) + 1, dtype=np.int64)
    offsets[0] = 0
    np.cumsum(lengths, out=offsets[1:])
    events_flat = [ev for evs in events for ev in evs]
    times_flat = [t for t, evs in zip(times, events) for _ in evs]
    has_event = lengths > 0
    t_arr_elapsed = perf_counter() - t_arr_start
    print(
        f"[F03] arrays listos en {t_arr_elapsed:,.1f}s | "
        f"eventos totales: {len(events_flat):,}",
        flush=True,
    )

    # -----------------------------------------------------------------
    # Cargar catálogo NaN
    # -----------------------------------------------------------------
    print(
        f"[F03] leyendo catálogo NaN: "
        f"{project_root / 'executions' / parent_phase / parent_variant / f'{parent_phase}_event_catalog.json'}",
        flush=True,
    )
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

    t_nan_start = perf_counter()
    has_nan = np.array(
        [
            any(ev in nan_codes for ev in evs)
            for evs in events
        ],
        dtype=bool,
    )
    nan_prefix = np.cumsum(has_nan, dtype=np.int64)
    t_nan_elapsed = perf_counter() - t_nan_start
    print(f"[F03] has_nan + prefix en {t_nan_elapsed:,.1f}s", flush=True)

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
        elif window_strategy == "asynOW":
            print("[F03] asynOW: calculando bins con eventos...", flush=True)
            t_bins_start = perf_counter()
            event_bins = np.unique(
                ((times[has_event] - t_min) // Tu).astype(np.int64)
            )
            t_bins_elapsed = perf_counter() - t_bins_start
            print(
                f"[F03] asynOW: bins con eventos = {len(event_bins):,} | "
                f"tiempo: {t_bins_elapsed:,.1f}s",
                flush=True,
            )
            for bin_idx in event_bins:
                t = t_min + bin_idx * Tu
                if t + total <= t_max:
                    yield t
        else:
            raise ValueError("Estrategia no soportada")

    def idx_range(t0, t1):
        return bisect_left(times, t0), bisect_left(times, t1)

    def has_nan_in_range(i0, i1):
        if i0 >= i1:
            return False
        return (nan_prefix[i1 - 1] - (nan_prefix[i0 - 1] if i0 > 0 else 0)) > 0

    # -----------------------------------------------------------------
    # Generación de ventanas (escritura incremental)
    # -----------------------------------------------------------------
    output_path = variant_root / f"{PHASE}_dataset.parquet"

    schema = pa.schema([
        ("OW_events", pa.list_(pa.int32())),
        ("PW_events", pa.list_(pa.int32())),
    ])
    writer = pq.ParquetWriter(output_path, schema, compression="snappy")
    BATCH = 100
    rows = []

    windows_total = 0
    windows_written = 0
    LOG_EVERY = 100_000
    t_start = perf_counter()
    t_loop_start = t_start

    for t0 in window_start_iterator():
        windows_total += 1

        i_ow_0, i_ow_1 = idx_range(t0, t0 + OW * Tu)
        i_pw_0, i_pw_1 = idx_range(
            t0 + PW_start * Tu,
            t0 + PW_end * Tu,
        )

        ow_len = i_ow_1 - i_ow_0
        pw_len = i_pw_1 - i_pw_0

        if ow_len == 0 and pw_len == 0:
            continue

        if nan_strategy == "discard":
            if has_nan_in_range(i_ow_0, i_ow_1):
                continue
            if has_nan_in_range(i_pw_0, i_pw_1):
                continue

        ow_start = offsets[i_ow_0]
        ow_end = offsets[i_ow_1]
        pw_start = offsets[i_pw_0]
        pw_end = offsets[i_pw_1]

        ow_events = events_flat[ow_start:ow_end]
        pw_events = events_flat[pw_start:pw_end]

        rows.append({
            "OW_events": ow_events,
            "PW_events": pw_events,
        })
        windows_written += 1

        if windows_total % LOG_EVERY == 0:
            elapsed = perf_counter() - t_start
            print(
                f"[F03] ventanas: {windows_total:,} | "
                f"escritas: {windows_written:,} | "
                f"tiempo: {elapsed:,.1f}s",
                flush=True,
            )

        if len(rows) >= BATCH:
            writer.write_table(pa.Table.from_pylist(rows, schema))
            rows.clear()

    if rows:
        writer.write_table(pa.Table.from_pylist(rows, schema))

    writer.close()

    elapsed_total = perf_counter() - t_start
    loop_elapsed = perf_counter() - t_loop_start

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
        "elapsed_seconds": round(elapsed_total, 3),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(variant_root / f"{PHASE}_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print("✔ F03 FINAL generado")
    print(f"  Dataset : {output_path}")
    print(f"  Ventanas: {windows_written:,}")
    print(f"  Tiempo  : {elapsed_total:,.1f}s")
    print(f"  Loop    : {loop_elapsed:,.1f}s")

# =====================================================================
if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-

