#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fase 03 — prepareWindowsDS (OPTIMIZADA + FACTORIZADA)

Estrategias soportadas:
- synchro   : ventanas en todo Tu (fast-path O(N+W))
- asynOW    : abrir ventana solo si OW tiene ≥1 evento
- withinPW  : abrir ventana solo si PW tiene ≥1 evento
- asynPW    : abrir ventana solo si hay evento al inicio de PW
"""

# =====================================================================
# IMPORTS
# =====================================================================
import argparse
import json
import yaml
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from time import perf_counter
from bisect import bisect_left
import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pyarrow as pa
import pyarrow.parquet as pq

import sys

# ============================================================
# BOOTSTRAP (OBLIGATORIO ANTES DE IMPORTAR mlops4ofp)
# ============================================================

SCRIPT_PATH = Path(__file__).resolve()
BOOTSTRAP_ROOT = SCRIPT_PATH
for _ in range(10):
    if (BOOTSTRAP_ROOT / "mlops4ofp").exists():
        break
    BOOTSTRAP_ROOT = BOOTSTRAP_ROOT.parent
else:
    raise RuntimeError("No se pudo localizar el repo root (mlops4ofp)")

sys.path.insert(0, str(BOOTSTRAP_ROOT))



# =====================================================================
# IMPORTS PROYECTO
# =====================================================================
from mlops4ofp.tools.run_context import (
    detect_execution_dir,
    detect_project_root,
    assemble_run_context,
    build_phase_outputs,
)
from mlops4ofp.tools.params_manager import ParamsManager, validate_params
from mlops4ofp.tools.artifacts import (
    get_git_hash,
    save_numeric_dataset,
    save_params_and_metadata,
)
import mlops4ofp.tools.html_reports.html03 as preparewindows_report03

execution_dir = detect_execution_dir()
PROJECT_ROOT = detect_project_root(execution_dir)

# =====================================================================
PHASE = "03_preparewindowsds"
# =====================================================================


# =====================================================================
# HELPERS
# =====================================================================
def has_nan_in_range(nan_prefix, i0, i1):
    if i0 >= i1:
        return False
    return nan_prefix[i1 - 1] - (nan_prefix[i0 - 1] if i0 else 0) > 0


def flush_rows(writer, rows, schema):
    if rows:
        writer.write_table(pa.Table.from_pylist(rows, schema))
        rows.clear()


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

    variant_root = project_root / "executions" / PHASE / args.variant

    ctx= assemble_run_context(
        project_root=project_root,
        phase=PHASE,
        variant=args.variant,
        variant_root=variant_root,
        execution_dir=args.execution_dir,
    )

    OUTPUTS = build_phase_outputs(
        variant_root=variant_root,
        phase=ctx["phase"],
    )

    ctx["outputs"] = OUTPUTS

    # -----------------------------------------------------------------
    # Params
    # -----------------------------------------------------------------
    with open(variant_root / "params.yaml", "r") as f:
        params = yaml.safe_load(f)

    OW = int(params["OW"])
    LT = int(params["LT"])
    PW = int(params["PW"])
    Tu = float(params.get("Tu") or 0)
    nan_strategy = params.get("nan_strategy", "discard")
    window_strategy = params.get("window_strategy", "synchro")
    parent_variant = params["parent_variant"]
    parent_phase = params.get("parent_phase", "02_prepareeventsds")
    BATCH = int(params.get("batch_size", 10_000))

    if Tu == 0:
        with open(
            project_root / "executions" / parent_phase / parent_variant /
            f"{parent_phase}_metadata.json"
        ) as f:
            Tu = float(json.load(f)["Tu"])

    print(f"[F03] Tu = {Tu}", flush=True)

    ctx['variant_params'] = params
    ctx['variant_params']['Tu'] = Tu

    # -----------------------------------------------------------------
    # Load dataset
    # -----------------------------------------------------------------
    input_dataset = (
        project_root / "executions" / parent_phase / parent_variant /
        f"{parent_phase}_dataset.parquet"
    )

    table = pq.read_table(input_dataset, columns=["segs", "events"])
    df = table.to_pandas(split_blocks=True, self_destruct=True)

    if not df["segs"].is_monotonic_increasing:
        df = df.sort_values("segs", kind="mergesort").reset_index(drop=True)

    # -----------------------------------------------------------------
    # NaN catalog
    # -----------------------------------------------------------------
    with open(
        project_root / "executions" / parent_phase / parent_variant /
        f"{parent_phase}_event_catalog.json"
    ) as f:
        catalog = json.load(f)

    nan_codes = {c for n, c in catalog.items() if n.endswith("_NaN_NaN")}

    # -----------------------------------------------------------------
    # Flatten
    # -----------------------------------------------------------------
    times = df["segs"].to_numpy(dtype=np.int64, copy=False)
    events = df["events"].to_numpy()

    lengths = np.fromiter((len(e) for e in events), dtype=np.int64, count=len(events))
    offsets = np.empty(len(events) + 1, dtype=np.int64)
    offsets[0] = 0
    np.cumsum(lengths, out=offsets[1:])

    total_events = int(offsets[-1])
    events_flat = np.empty(total_events, dtype=np.int32)

    if nan_strategy == "discard":
        has_nan = np.zeros(len(events), dtype=bool)
    else:
        has_nan = None

    pos = 0
    for i, evs in enumerate(events):
        l = len(evs)
        if l:
            events_flat[pos:pos + l] = evs
            if nan_strategy == "discard":
                for ev in evs:
                    if ev in nan_codes:
                        has_nan[i] = True
                        break
            pos += l

    nan_prefix = np.cumsum(has_nan, dtype=np.int64) if nan_strategy == "discard" else None

    # -----------------------------------------------------------------
    # Geometry
    # -----------------------------------------------------------------
    OW_span = OW * Tu
    PW_start = (OW + LT) * Tu
    PW_span = PW * Tu
    total_span = PW_start + PW_span

    # -----------------------------------------------------------------
    # Output
    # -----------------------------------------------------------------
    output_path = variant_root / f"{PHASE}_dataset.parquet"
    schema = pa.schema([
        ("OW_events", pa.list_(pa.int32())),
        ("PW_events", pa.list_(pa.int32())),
    ])
    writer = pq.ParquetWriter(output_path, schema, compression="snappy")

    rows = []
    windows_total = 0
    windows_written = 0

    t_loop = perf_counter()

    # =================================================================
    # FAST PATH: SYNCHRO
    # =================================================================
    if window_strategy == "synchro":
        n = len(times)
        t0 = times[0]

        i_ow_0 = bisect_left(times, t0)
        i_ow_1 = bisect_left(times, t0 + OW_span)
        i_pw_0 = bisect_left(times, t0 + PW_start)
        i_pw_1 = bisect_left(times, t0 + PW_start + PW_span)

        while t0 + total_span <= times[-1]:
            windows_total += 1

            if i_ow_0 != i_ow_1 or i_pw_0 != i_pw_1:
                if nan_strategy == "discard":
                    if (
                        has_nan_in_range(nan_prefix, i_ow_0, i_ow_1)
                        or has_nan_in_range(nan_prefix, i_pw_0, i_pw_1)
                    ):
                        pass
                    else:
                        ow = events_flat[offsets[i_ow_0]:offsets[i_ow_1]]
                        pw = events_flat[offsets[i_pw_0]:offsets[i_pw_1]]
                        if len(ow) or len(pw):
                            rows.append({"OW_events": ow, "PW_events": pw})
                            windows_written += 1
                else:
                    ow = events_flat[offsets[i_ow_0]:offsets[i_ow_1]]
                    pw = events_flat[offsets[i_pw_0]:offsets[i_pw_1]]
                    if len(ow) or len(pw):
                        rows.append({"OW_events": ow, "PW_events": pw})
                        windows_written += 1

            if len(rows) >= BATCH:
                flush_rows(writer, rows, schema)

            t0 += Tu
            ow_start = t0
            ow_end = t0 + OW_span
            pw_start = t0 + PW_start
            pw_end = pw_start + PW_span

            while i_ow_0 < n and times[i_ow_0] < ow_start:
                i_ow_0 += 1
            while i_ow_1 < n and times[i_ow_1] < ow_end:
                i_ow_1 += 1
            while i_pw_0 < n and times[i_pw_0] < pw_start:
                i_pw_0 += 1
            while i_pw_1 < n and times[i_pw_1] < pw_end:
                i_pw_1 += 1

    # =================================================================
    # ASYNOW
    # =================================================================
    elif window_strategy == "asynOW":
        active_bins = np.unique(((times[lengths > 0] - times[0]) // Tu).astype(np.int64))

        for b in active_bins:
            t0 = times[0] + b * Tu
            if t0 + total_span > times[-1]:
                continue

            windows_total += 1

            i_ow_0 = bisect_left(times, t0)
            i_ow_1 = bisect_left(times, t0 + OW_span)
            if i_ow_0 == i_ow_1:
                continue

            i_pw_0 = bisect_left(times, t0 + PW_start)
            i_pw_1 = bisect_left(times, t0 + PW_start + PW_span)

            if nan_strategy == "discard":
                if (
                    has_nan_in_range(nan_prefix, i_ow_0, i_ow_1)
                    or has_nan_in_range(nan_prefix, i_pw_0, i_pw_1)
                ):
                    continue

            ow = events_flat[offsets[i_ow_0]:offsets[i_ow_1]]
            pw = events_flat[offsets[i_pw_0]:offsets[i_pw_1]]
            if len(ow) or len(pw):
                rows.append({"OW_events": ow, "PW_events": pw})
                windows_written += 1

            if len(rows) >= BATCH:
                flush_rows(writer, rows, schema)

    # =================================================================
    # WITHINPW
    # =================================================================
    # =================================================================
    # WITHINPW
    # =================================================================
    elif window_strategy == "withinPW":
        n = len(times)
        t0 = times[0]

        i_ow_0 = bisect_left(times, t0)
        i_ow_1 = bisect_left(times, t0 + OW_span)
        i_pw_0 = bisect_left(times, t0 + PW_start)
        i_pw_1 = bisect_left(times, t0 + PW_start + PW_span)

        while t0 + total_span <= times[-1]:
            windows_total += 1

            # 🔒 criterio withinPW: PW debe tener ≥1 evento REAL
            if i_pw_0 != i_pw_1:
                if nan_strategy == "discard":
                    if (
                        has_nan_in_range(nan_prefix, i_ow_0, i_ow_1)
                        or has_nan_in_range(nan_prefix, i_pw_0, i_pw_1)
                    ):
                        pass
                    else:
                        ow = events_flat[offsets[i_ow_0]:offsets[i_ow_1]]
                        pw = events_flat[offsets[i_pw_0]:offsets[i_pw_1]]
                        if len(pw):
                            rows.append({"OW_events": ow, "PW_events": pw})
                            windows_written += 1
                else:
                    ow = events_flat[offsets[i_ow_0]:offsets[i_ow_1]]
                    pw = events_flat[offsets[i_pw_0]:offsets[i_pw_1]]
                    if len(pw):
                        rows.append({"OW_events": ow, "PW_events": pw})
                        windows_written += 1

            if len(rows) >= BATCH:
                flush_rows(writer, rows, schema)

            t0 += Tu
            ow_start = t0
            ow_end = t0 + OW_span
            pw_start = t0 + PW_start
            pw_end = pw_start + PW_span

            while i_ow_0 < n and times[i_ow_0] < ow_start:
                i_ow_0 += 1
            while i_ow_1 < n and times[i_ow_1] < ow_end:
                i_ow_1 += 1
            while i_pw_0 < n and times[i_pw_0] < pw_start:
                i_pw_0 += 1
            while i_pw_1 < n and times[i_pw_1] < pw_end:
                i_pw_1 += 1

    # =================================================================
    # ASYNPW
    # =================================================================
    elif window_strategy == "asynPW":
        n = len(times)
        t0 = times[0]

        i_ow_0 = bisect_left(times, t0)
        i_ow_1 = bisect_left(times, t0 + OW_span)
        i_pw_0 = bisect_left(times, t0 + PW_start)
        i_pw_1 = bisect_left(times, t0 + PW_start + PW_span)
        i_pw_start1 = bisect_left(times, t0 + PW_start + Tu)

        while t0 + total_span <= times[-1]:
            windows_total += 1

            # 🔒 criterio asynPW: evento al inicio de PW (primer Tu)
            if i_pw_0 != i_pw_start1:
                if nan_strategy == "discard":
                    if (
                        has_nan_in_range(nan_prefix, i_ow_0, i_ow_1)
                        or has_nan_in_range(nan_prefix, i_pw_0, i_pw_1)
                    ):
                        pass
                    else:
                        ow = events_flat[offsets[i_ow_0]:offsets[i_ow_1]]
                        pw = events_flat[offsets[i_pw_0]:offsets[i_pw_1]]
                        if len(ow) or len(pw):
                            rows.append({"OW_events": ow, "PW_events": pw})
                            windows_written += 1
                else:
                    ow = events_flat[offsets[i_ow_0]:offsets[i_ow_1]]
                    pw = events_flat[offsets[i_pw_0]:offsets[i_pw_1]]
                    if len(ow) or len(pw):
                        rows.append({"OW_events": ow, "PW_events": pw})
                        windows_written += 1

            if len(rows) >= BATCH:
                flush_rows(writer, rows, schema)

            t0 += Tu
            ow_start = t0
            ow_end = t0 + OW_span
            pw_start = t0 + PW_start
            pw_end = pw_start + PW_span

            while i_ow_0 < n and times[i_ow_0] < ow_start:
                i_ow_0 += 1
            while i_ow_1 < n and times[i_ow_1] < ow_end:
                i_ow_1 += 1
            while i_pw_0 < n and times[i_pw_0] < pw_start:
                i_pw_0 += 1
            while i_pw_1 < n and times[i_pw_1] < pw_end:
                i_pw_1 += 1
            while i_pw_start1 < n and times[i_pw_start1] < pw_start + Tu:
                i_pw_start1 += 1


    else:
        raise ValueError(f"Estrategia desconocida: {window_strategy}")

    flush_rows(writer, rows, schema)
    writer.close()

    elapsed = perf_counter() - t_loop

    # -----------------------------------------------------------------
    # Metadata
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
        "elapsed_seconds": round(elapsed, 3),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(variant_root / f"{PHASE}_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print("✔ F03 FINAL generado")
    print(f"  Dataset : {output_path}")
    print(f"  Ventanas: {windows_written:,}")
    print(f"  Tiempo  : {elapsed:,.1f}s")

    # ============================================================
    # Tablas, figuras e informe HTML (Fase 03)
    # ============================================================

    df_windows = pd.read_parquet(ctx["outputs"]["dataset"])

    preparewindows_report03.generate_html_report(
        ctx=ctx,
        df_windows=df_windows,
        catalog=catalog,
    )



# =====================================================================
if __name__ == "__main__":
    main()
