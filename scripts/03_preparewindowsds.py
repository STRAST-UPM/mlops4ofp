#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fase 03 — prepareWindowsDS (OPTIMIZADA)

Genera el dataset FINAL de ventanas:
- OW_events: lista de códigos de eventos en la ventana de observación
- PW_events: lista de códigos de eventos en la ventana de predicción

Optimizada para datasets grandes:
- Lectura selectiva de columnas
- Aplanado + NaN en una sola pasada
- Escritura Parquet por batches grandes
- Fast-path O(N+W) para estrategia synchro (sin bisect por ventana)
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
    with open(variant_root / "params.yaml", "r", encoding="utf-8") as f:
        params = yaml.safe_load(f)

    OW = int(params["OW"])
    LT = int(params["LT"])
    PW = int(params["PW"])
    Tu_raw = params.get("Tu", None)
    Tu = float(Tu_raw) if Tu_raw is not None else 0.0
    nan_strategy = params.get("nan_strategy", "discard")
    window_strategy = params.get("window_strategy", "synchro")
    parent_variant = params["parent_variant"]
    parent_phase = params.get("parent_phase", "02_prepareeventsds")
    BATCH = int(params.get("batch_size", 10_000))  # OPT

    # -----------------------------------------------------------------
    # Resolver Tu desde metadata F02 si no viene fijado
    # -----------------------------------------------------------------
    if Tu_raw is None or Tu == 0:
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

        Tu_f02 = meta_f02.get("Tu", None)
        if Tu_f02 is None:
            raise RuntimeError(
                "No se pudo determinar Tu: es None en F03 params y en F02 metadata"
            )
        Tu = float(Tu_f02)

    print(f"[F03] Tu = {Tu}", flush=True)

    # -----------------------------------------------------------------
    # Cargar dataset F02 (OPT: solo columnas necesarias)
    # -----------------------------------------------------------------
    input_dataset = (
        project_root
        / "executions"
        / parent_phase
        / parent_variant
        / f"{parent_phase}_dataset.parquet"
    )

    print(f"[F03] leyendo dataset F02: {input_dataset}", flush=True)
    t_read = perf_counter()
    table = pq.read_table(input_dataset, columns=["segs", "events"])
    df = table.to_pandas(split_blocks=True, self_destruct=True)
    print(f"[F03] dataset cargado en {perf_counter() - t_read:,.1f}s", flush=True)

    # -----------------------------------------------------------------
    # Asegurar orden temporal
    # -----------------------------------------------------------------
    if not df["segs"].is_monotonic_increasing:
        t_sort = perf_counter()
        df = df.sort_values("segs", kind="mergesort").reset_index(drop=True)
        print(f"[F03] ordenado en {perf_counter() - t_sort:,.1f}s", flush=True)

    # -----------------------------------------------------------------
    # Leer catálogo NaN (antes de aplanar)
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

    # -----------------------------------------------------------------
    # Preparar arrays (OPT: una sola pasada Python)
    # -----------------------------------------------------------------
    print("[F03] preparando arrays...", flush=True)
    t_arr = perf_counter()

    times = df["segs"].to_numpy(dtype=np.int64, copy=False)
    events = df["events"].to_numpy()

    lengths = np.fromiter((len(evs) for evs in events), dtype=np.int64, count=len(events))
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

    if nan_strategy == "discard":
        nan_prefix = np.cumsum(has_nan, dtype=np.int64)
    else:
        nan_prefix = None

    print(
        f"[F03] arrays listos en {perf_counter() - t_arr:,.1f}s | "
        f"eventos totales: {total_events:,}",
        flush=True,
    )

    # -----------------------------------------------------------------
    # Ventanas
    # -----------------------------------------------------------------
    OW_span = OW * Tu
    PW_start = (OW + LT) * Tu
    PW_span = PW * Tu
    total_span = PW_start + PW_span

    output_path = variant_root / f"{PHASE}_dataset.parquet"
    schema = pa.schema([
        ("OW_events", pa.list_(pa.int32())),
        ("PW_events", pa.list_(pa.int32())),
    ])
    writer = pq.ParquetWriter(output_path, schema, compression="snappy")

    rows = []
    rows_append = rows.append
    offsets_l = offsets
    events_flat_l = events_flat

    windows_total = 0
    windows_written = 0

    t_loop = perf_counter()

    # =================================================================
    # FAST PATH: SYNCHRO (OPT: sin bisect por ventana)
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
                        (i_ow_0 < i_ow_1 and
                         nan_prefix[i_ow_1 - 1] - (nan_prefix[i_ow_0 - 1] if i_ow_0 else 0) > 0)
                        or
                        (i_pw_0 < i_pw_1 and
                         nan_prefix[i_pw_1 - 1] - (nan_prefix[i_pw_0 - 1] if i_pw_0 else 0) > 0)
                    ):
                        pass
                    else:
                        ow_events = events_flat_l[offsets_l[i_ow_0]:offsets_l[i_ow_1]]
                        pw_events = events_flat_l[offsets_l[i_pw_0]:offsets_l[i_pw_1]]
                        rows_append({"OW_events": ow_events, "PW_events": pw_events})
                        windows_written += 1
                else:
                    ow_events = events_flat_l[offsets_l[i_ow_0]:offsets_l[i_ow_1]]
                    pw_events = events_flat_l[offsets_l[i_pw_0]:offsets_l[i_pw_1]]
                    rows_append({"OW_events": ow_events, "PW_events": pw_events})
                    windows_written += 1

            if len(rows) >= BATCH:
                writer.write_table(pa.Table.from_pylist(rows, schema))
                rows.clear()

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
    # FALLBACK: otras estrategias (mantiene bisect)
    # =================================================================
    else:
        def idx_range(t0, t1):
            return bisect_left(times, t0), bisect_left(times, t1)

        t0 = times[0]
        while t0 + total_span <= times[-1]:
            windows_total += 1

            i_ow_0, i_ow_1 = idx_range(t0, t0 + OW_span)
            i_pw_0, i_pw_1 = idx_range(t0 + PW_start, t0 + PW_start + PW_span)

            if i_ow_0 != i_ow_1 or i_pw_0 != i_pw_1:
                if nan_strategy == "discard":
                    if (
                        (i_ow_0 < i_ow_1 and
                         nan_prefix[i_ow_1 - 1] - (nan_prefix[i_ow_0 - 1] if i_ow_0 else 0) > 0)
                        or
                        (i_pw_0 < i_pw_1 and
                         nan_prefix[i_pw_1 - 1] - (nan_prefix[i_pw_0 - 1] if i_pw_0 else 0) > 0)
                    ):
                        pass
                    else:
                        ow_events = events_flat_l[offsets_l[i_ow_0]:offsets_l[i_ow_1]]
                        pw_events = events_flat_l[offsets_l[i_pw_0]:offsets_l[i_pw_1]]
                        rows_append({"OW_events": ow_events, "PW_events": pw_events})
                        windows_written += 1
                else:
                    ow_events = events_flat_l[offsets_l[i_ow_0]:offsets_l[i_ow_1]]
                    pw_events = events_flat_l[offsets_l[i_pw_0]:offsets_l[i_pw_1]]
                    rows_append({"OW_events": ow_events, "PW_events": pw_events})
                    windows_written += 1

            if len(rows) >= BATCH:
                writer.write_table(pa.Table.from_pylist(rows, schema))
                rows.clear()

            t0 += Tu

    if rows:
        writer.write_table(pa.Table.from_pylist(rows, schema))
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


# =====================================================================
if __name__ == "__main__":
    main()
