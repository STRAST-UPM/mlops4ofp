#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fase 03 — prepareWindowsDS (script)

Reproduce exactamente la lógica del notebook F03.
Se asume que la variante ya ha sido creada con `make variant3`.
"""

# =====================================================================
# 1. IMPORTS
# =====================================================================
import sys
from pathlib import Path
import argparse
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from bisect import bisect_left
import json 
from datetime import datetime, timezone
import pyarrow.parquet as pq
from collections import Counter
import matplotlib.pyplot as plt
from html import escape
from datetime import datetime

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


# ============================================================
# IMPORTS DEL PROYECTO (ya con sys.path correcto)
# ============================================================

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
from mlops4ofp.tools.figures import save_figure
from mlops4ofp.tools.traceability import write_metadata

execution_dir = detect_execution_dir()
PROJECT_ROOT = detect_project_root(execution_dir)

PHASE = "03_preparewindowsds"

# =====================================================================
# 4. CLI
# =====================================================================
def parse_args():
    parser = argparse.ArgumentParser(
        description="F03 - Prepare Windows Dataset"
    )
    parser.add_argument("--variant", required=True)
    parser.add_argument("--execution-dir", type=Path, default=None)
    return parser.parse_args()

# =====================================================================
# 5. MAIN
# =====================================================================
def main():
    args = parse_args()

    variant_root = (
        PROJECT_ROOT
        / "params"
        / "03_preparewindowsds"
        / args.variant
    )


    ctx = assemble_run_context(
        project_root=PROJECT_ROOT,
        phase="03_preparewindowsds",
        variant_root=variant_root,
        variant=args.variant,
        execution_dir=args.execution_dir,
    )

    print("✔ F03 context OK")
    print(f"  Variante: {args.variant}")

    # =====================================================================
    # CARGA MÍNIMA DE PARÁMETROS F03
    # =====================================================================

    params_path = ctx["variant_root"] / "params.yaml"

    with open(params_path, "r", encoding="utf-8") as f:
        params_f03 = yaml.safe_load(f) or {}

    parent_variant = params_f03.get("parent_variant")


    # =====================================================================
    # 6. LOCALIZACIÓN DEL DATASET DE ENTRADA (F02)
    # =====================================================================

    parent_phase = "02_prepareeventsds"

    input_dataset_path = (
        ctx["project_root"]
        / "params"
        / parent_phase
        / parent_variant
        / f"{parent_phase}_dataset.parquet"
    )

    print(f"✔ Dataset de entrada (F02): {input_dataset_path}")
    
    # =====================================================================
    # 7. CARGA EFICIENTE DEL DATASET BASE (FASE 02)
    # =====================================================================

   

    # Lectura eficiente con PyArrow
    table = pq.read_table(input_dataset_path)

    # Conversión controlada a pandas
    df = table.to_pandas(
        split_blocks=True,     # menos fragmentación de memoria
        self_destruct=True     # libera buffers Arrow tras la conversión
    )

    print(f"✔ Dataset cargado: {df.shape[0]:,} filas × {df.shape[1]} columnas")

    # ---------------------------------------------------------------------
    # Comprobaciones mínimas y preparación
    # ---------------------------------------------------------------------

    # 1) Columna temporal obligatoria
    if "segs" not in df.columns:
        raise ValueError("El dataset no contiene la columna temporal obligatoria 'segs'")

    # 2) Orden temporal (barato y estable)
    if not df["segs"].is_monotonic_increasing:
        df = df.sort_values("segs", kind="mergesort").reset_index(drop=True)
        print("ℹ Dataset ordenado por 'segs'")

    # 3) Conversión a numpy para acceso rápido
    time_array = df["segs"].to_numpy(dtype=np.int64, copy=False)

    # =====================================================================
    # PARÁMETROS EFECTIVOS F03 (OW, LT, PW, Tu)
    # =====================================================================

    OW = int(params_f03["OW"])
    LT = int(params_f03["LT"])
    PW = int(params_f03["PW"])

    nan_strategy = params_f03.get("nan_strategy", "discard")
    window_strategy = params_f03.get("window_strategy", "synchro")
    parent_phase = params_f03.get("parent_phase", "02_prepareeventsds")
    parent_variant = params_f03.get("parent_variant")
    variant_id = params_f03.get("variant_id", args.variant)

    # --- Cargar metadata de F02 (padre) para herencia de Tu ---
    parent_metadata_path = (
        ctx["project_root"]
        / "params"
        / parent_phase
        / parent_variant
        / f"{parent_phase}_metadata.json"
    )

    with open(parent_metadata_path, "r", encoding="utf-8") as f:
        parent_params_f02 = json.load(f)

    def resolve_Tu(params_f03, parent_params_f02):
        if params_f03.get("Tu") is not None:
            Tu = float(params_f03["Tu"])
            print(f"✔ Tu tomado de variante F03: {Tu}")
            return Tu

        Tu_f02 = parent_params_f02.get("Tu")
        if Tu_f02 is not None:
            Tu = float(Tu_f02)
            print(f"✔ Tu heredado de metadata F02: {Tu}")
            return Tu

        raise RuntimeError("❌ No se pudo determinar Tu (ni en F03 ni en F02).")

    Tu = resolve_Tu(params_f03, parent_params_f02)

    print("────────── VARIANT PARAMETERS (F03) ──────────")
    print(f"variant_id      = {variant_id}")
    print(f"parent_phase    = {parent_phase}")
    print(f"parent_variant  = {parent_variant}")
    print(f"OW              = {OW}")
    print(f"LT              = {LT}")
    print(f"PW              = {PW}")
    print(f"nan_strategy    = {nan_strategy}")
    print(f"Tu              = {Tu}")
    print("──────────────────────────────────────────────")



    # =====================================================================
    # 8. PRECOMPUTACIÓN DE DESPLAZAMIENTOS TEMPORALES (en unidades Tu)
    # =====================================================================

    OW_end = OW
    LT_start = OW
    PW_start = OW + LT
    PW_end = OW + LT + PW

    WINDOW_SIZE = PW_end  # ventana total máxima (en unidades Tu)

    print(f"Ventana total usada = 0 → {WINDOW_SIZE * Tu} segundos")
    print(f"OW, LT, PW son múltiplos de Tu = {Tu} segundos")

    # =====================================================================
    # 9. PREPARACIÓN DE ESTRUCTURAS EFICIENTES
    # =====================================================================

    # Conversión de tiempo a numpy (ya ordenado)
    times = df["segs"].to_numpy(dtype=np.int64, copy=False)
    N = len(times)

    # ---------------------------------------------------------------------
    # Carga del catálogo de eventos de F02
    # ---------------------------------------------------------------------
    parent_event_catalog_path = (
        ctx["project_root"]
        / "params"
        / parent_phase
        / parent_variant
        / f"{parent_phase}_event_catalog.json"
    )

    with open(parent_event_catalog_path, "r", encoding="utf-8") as f:
        parent_event_catalog_f02 = json.load(f)

    nan_event_codes = {
        code
        for name, code in parent_event_catalog_f02.items()
        if name.strip().endswith("_NaN_NaN")
    }

    nan_event_codes = set(nan_event_codes)

    # ---------------------------------------------------------------------
    # Detección de filas con eventos NaN
    # ---------------------------------------------------------------------
    has_nan = np.array(
        [
            any(ev in nan_event_codes for ev in ev_list)
            if ev_list is not None else False
            for ev_list in df["events"]
        ],
        dtype=bool,
    )

    print(f"Dataset preparado: {N:,} timestamps")

    def window_start_iterator():
        """
        Genera tiempos t0 (inicio de ventana) según la estrategia.
        Todos los tiempos están en segundos.
        """

        t_min = times[0]
        t_max = times[-1]
        total_window_sec = PW_end * Tu

        if window_strategy == "synchro":
            # Ventanas alineadas a Tu en toda la escala temporal
            t = t_min
            while t + total_window_sec <= t_max:
                yield t
                t += Tu

        elif window_strategy == "asynOW":
            # Cada evento inicia una OW
            for t in times:
                if t + total_window_sec <= t_max:
                    yield t

        elif window_strategy == "withinPW":
            # Ventana cuyo PW termina en un evento
            for t in times:
                t0 = t - (OW + LT) * Tu
                if t0 >= t_min and t0 + total_window_sec <= t_max:
                    yield t0

        elif window_strategy == "asynPW":
            # PW empieza exactamente en un evento
            for t in times:
                t0 = t - PW_start * Tu
                if t0 >= t_min and t0 + total_window_sec <= t_max:
                    yield t0

        else:
            raise ValueError(
                f"Estrategia de enventanado no soportada: {window_strategy}"
            )

    WINDOW_COUNT = 0
    WRITTEN_COUNT = 0

    def get_index_range(t0, t1):
        i0 = bisect_left(times, t0)
        i1 = bisect_left(times, t1)
        return i0, i1

        print("Generando ventanas (sin acumular en memoria)...")

    for t0 in window_start_iterator():

        t_OW_0 = t0
        t_OW_1 = t0 + OW * Tu

        t_PW_0 = t0 + PW_start * Tu
        t_PW_1 = t0 + PW_end * Tu

        i_ow_0, i_ow_1 = get_index_range(t_OW_0, t_OW_1)
        i_pw_0, i_pw_1 = get_index_range(t_PW_0, t_PW_1)

        WINDOW_COUNT += 1
        if i_ow_0 == i_ow_1 or i_pw_0 == i_pw_1:
            continue

        if nan_strategy == "discard":
            if has_nan[i_ow_0:i_ow_1].any():
                continue
            if has_nan[i_pw_0:i_pw_1].any():
                continue

        WRITTEN_COUNT += 1

    print(f"✔ Total ventanas válidas generadas: {WRITTEN_COUNT:,}")

    # =====================================================================
    # 12. PREPARACIÓN DE ESCRITURA INCREMENTAL (PARQUET)
    # =====================================================================


    OUTPUT_DATASET_PATH = (
        ctx["variant_root"]
        / f"{ctx['phase']}_dataset.parquet"
    )

    OUTPUT_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Schema explícito (importante para estabilidad y velocidad)
    schema = pa.schema([
        ("t0", pa.int64()),
        ("i_ow_0", pa.int32()),
        ("i_ow_1", pa.int32()),
        ("i_pw_0", pa.int32()),
        ("i_pw_1", pa.int32()),
    ])

    writer = pq.ParquetWriter(
        OUTPUT_DATASET_PATH,
        schema=schema,
        compression="snappy"
    )

    print(f"✔ Writer Parquet preparado: {OUTPUT_DATASET_PATH}")

    # =====================================================================
    # 13. GENERACIÓN Y ESCRITURA DE VENTANAS (POR LOTES)
    # =====================================================================

    BATCH_SIZE = 20_000   # ajustable según RAM / I/O

    rows = []
    DISK_WINDOW_COUNT = 0
    DISK_WRITTEN_COUNT = 0

    for t0 in window_start_iterator():

        # -------------------------------------------------
        # Definición de ventanas OW / PW (en tiempo)
        # -------------------------------------------------
        t_OW_0 = t0
        t_OW_1 = t0 + OW * Tu

        t_PW_0 = t0 + PW_start * Tu
        t_PW_1 = t0 + PW_end * Tu

        # -------------------------------------------------
        # Conversión a índices
        # -------------------------------------------------
        i_ow_0, i_ow_1 = get_index_range(t_OW_0, t_OW_1)
        i_pw_0, i_pw_1 = get_index_range(t_PW_0, t_PW_1)

        # -------------------------------------------------
        # Ventanas sin rango temporal válido
        # -------------------------------------------------
        if i_ow_0 == i_ow_1 or i_pw_0 == i_pw_1:
            continue

        # -------------------------------------------------
        # Descarte por eventos NaN explícitos
        # -------------------------------------------------
        if nan_strategy == "discard":
            if has_nan[i_ow_0:i_ow_1].any():
                continue
            if has_nan[i_pw_0:i_pw_1].any():
                continue

        # -------------------------------------------------
        # Fila válida
        # -------------------------------------------------
        rows.append({
            "t0": int(t0),
            "i_ow_0": int(i_ow_0),
            "i_ow_1": int(i_ow_1),
            "i_pw_0": int(i_pw_0),
            "i_pw_1": int(i_pw_1),
        })

        DISK_WINDOW_COUNT += 1

        # -------------------------------------------------
        # Escritura por lotes
        # -------------------------------------------------
        if len(rows) >= BATCH_SIZE:
            table = pa.Table.from_pylist(rows, schema=schema)
            writer.write_table(table)
            DISK_WRITTEN_COUNT += len(rows)
            rows.clear()

    # -----------------------------------------------------
    # Flush final
    # -----------------------------------------------------
    if rows:
        table = pa.Table.from_pylist(rows, schema=schema)
        writer.write_table(table)
        DISK_WRITTEN_COUNT += len(rows)
        rows.clear()

    writer.close()

    print(f"✔ Ventanas válidas generadas : {DISK_WINDOW_COUNT:,}")
    print(f"✔ Filas escritas en Parquet  : {DISK_WRITTEN_COUNT:,}")

    # =====================================================================
    # 14. SANITY CHECKS DEL DATASET F03
    # =====================================================================

    pq_file = pq.ParquetFile(OUTPUT_DATASET_PATH)

    num_rows = pq_file.metadata.num_rows
    num_row_groups = pq_file.metadata.num_row_groups
    schema_read = pq_file.schema_arrow

    print("✔ Dataset F03 accesible")
    print(f"  Filas totales        : {num_rows:,}")
    print(f"  Row groups           : {num_row_groups}")
    print(f"  Schema               : {schema_read}")


    metadata_f03 = {
        "phase": ctx["phase"],
        "variant_id": ctx["variant"],
        "parent_phase": parent_phase,
        "parent_variant": parent_variant,

        "Tu_seconds": Tu,
        "OW_units": OW,
        "LT_units": LT,
        "PW_units": PW,
        "OW_seconds": OW * Tu,
        "LT_seconds": LT * Tu,
        "PW_seconds": PW * Tu,
        "total_window_seconds": (OW + LT + PW) * Tu,

        "window_strategy": window_strategy,
        "nan_strategy": nan_strategy,

        "dataset_path": str(OUTPUT_DATASET_PATH),
        "num_windows": int(num_rows),
        "num_row_groups": int(num_row_groups),

        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "03_preparewindowsds.py",

        "windows_candidates": int(WINDOW_COUNT),
        "windows_written": int(DISK_WRITTEN_COUNT),
    }

    metadata_path = (
        ctx["variant_root"]
        / f"{ctx['phase']}_metadata.json"
    )

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata_f03, f, indent=2, ensure_ascii=False)

    print(f"✔ Metadata F03 generada: {metadata_path}")


    STATS_PATH = ctx["variant_root"] / "03_preparewindowsds_stats.json"

    pq_file = pq.ParquetFile(OUTPUT_DATASET_PATH)

    n_windows = pq_file.metadata.num_rows
    n_row_groups = pq_file.metadata.num_row_groups

    # Estadísticos básicos
    t0_min = None
    t0_max = None

    # Para percentiles (muestreo controlado)
    SAMPLE_MAX = 300_000
    sample_ow = []
    sample_pw = []
    sample_step = []

    last_t0 = None
    rng = np.random.default_rng(123)

    for rg in range(n_row_groups):
        df_rg = pq_file.read_row_group(
            rg,
            columns=["t0", "i_ow_0", "i_ow_1", "i_pw_0", "i_pw_1"]
        ).to_pandas(split_blocks=True)

        if df_rg.empty:
            continue

        # Min / Max temporal
        rg_min = int(df_rg["t0"].min())
        rg_max = int(df_rg["t0"].max())
        t0_min = rg_min if t0_min is None else min(t0_min, rg_min)
        t0_max = rg_max if t0_max is None else max(t0_max, rg_max)

        # Longitudes OW / PW (en nº de timestamps)
        ow_len = (df_rg["i_ow_1"] - df_rg["i_ow_0"]).to_numpy()
        pw_len = (df_rg["i_pw_1"] - df_rg["i_pw_0"]).to_numpy()

        remaining = SAMPLE_MAX - len(sample_ow)
        if remaining > 0:
            take = min(remaining, len(df_rg))
            if len(df_rg) > take:
                idx = rng.choice(len(df_rg), size=take, replace=False)
                sample_ow.extend(ow_len[idx].tolist())
                sample_pw.extend(pw_len[idx].tolist())
            else:
                sample_ow.extend(ow_len.tolist())
                sample_pw.extend(pw_len.tolist())

        # Pasos temporales (Δt0)
        t0_arr = df_rg["t0"].to_numpy(dtype=np.int64, copy=False)
        if last_t0 is not None:
            sample_step.append(int(t0_arr[0] - last_t0))
        if len(t0_arr) > 1:
            diffs = np.diff(t0_arr)
            k = min(2000, len(diffs))
            if len(diffs) > k:
                idx2 = rng.choice(len(diffs), size=k, replace=False)
                sample_step.extend(diffs[idx2].tolist())
            else:
                sample_step.extend(diffs.tolist())
        last_t0 = int(t0_arr[-1])


    def percentiles(arr, ps=(0, 5, 25, 50, 75, 95, 100)):
        if not arr:
            return None
        arr = np.asarray(arr)
        return {f"p{p}": float(np.percentile(arr, p)) for p in ps}

    stats = {
        "phase": ctx["phase"],
        "variant_id": ctx["variant"],
        "dataset_path": str(OUTPUT_DATASET_PATH),

        "num_windows": int(n_windows),
        "row_groups": int(n_row_groups),

        "t0_min": int(t0_min) if t0_min is not None else None,
        "t0_max": int(t0_max) if t0_max is not None else None,

        "ow_len_idx_percentiles": percentiles(sample_ow),
        "pw_len_idx_percentiles": percentiles(sample_pw),
        "t0_step_seconds_percentiles": percentiles(sample_step),

        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "windows_candidates": int(WINDOW_COUNT),
        "windows_discarded_nan": int(WINDOW_COUNT) - int(WRITTEN_COUNT),
        "windows_kept": int(WINDOW_COUNT),
        "discard_nan_ratio": (
            (int(WINDOW_COUNT) - int(WRITTEN_COUNT)) / float(WINDOW_COUNT)
            if WINDOW_COUNT > 0 else None
        ),

    }

    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    print(f"✔ Estadísticas F03 generadas en: {STATS_PATH}")
    print(f"✔ Ventanas totales: {n_windows:,}")


    FIG_DIR = ctx["figures_dir"]
    REPORT_DIR = ctx["variant_root"]

    FIG_DIR.mkdir(parents=True, exist_ok=True)


    pq_file = pq.ParquetFile(OUTPUT_DATASET_PATH)

    cols = ["t0", "i_ow_0", "i_ow_1", "i_pw_0", "i_pw_1"]

    # ---------------------------------------------------------------------
    # Contenedores de salida (los usará la celda de gráficas)
    # ---------------------------------------------------------------------
    SAMPLE_MAX = 300_000

    sample_ow = []
    sample_pw = []
    sample_step = []

    windows_per_hour = Counter()

    last_t0 = None
    rng = np.random.default_rng(123)

    # ---------------------------------------------------------------------
    # Lectura streaming por row-groups
    # ---------------------------------------------------------------------
    for rg in range(pq_file.metadata.num_row_groups):
        df_rg = pq_file.read_row_group(rg, columns=cols).to_pandas(split_blocks=True)

        if df_rg.empty:
            continue

        # Longitudes OW / PW (en nº de timestamps)
        ow_len = (df_rg["i_ow_1"].to_numpy() - df_rg["i_ow_0"].to_numpy())
        pw_len = (df_rg["i_pw_1"].to_numpy() - df_rg["i_pw_0"].to_numpy())

        # Muestreo controlado
        remaining = SAMPLE_MAX - len(sample_ow)
        if remaining > 0:
            take = min(remaining, len(df_rg))
            if len(df_rg) > take:
                idx = rng.choice(len(df_rg), size=take, replace=False)
                sample_ow.extend(ow_len[idx].astype(np.int32, copy=False).tolist())
                sample_pw.extend(pw_len[idx].astype(np.int32, copy=False).tolist())
            else:
                sample_ow.extend(ow_len.astype(np.int32, copy=False).tolist())
                sample_pw.extend(pw_len.astype(np.int32, copy=False).tolist())

        # Pasos temporales (Δt0)
        t0_arr = df_rg["t0"].to_numpy(dtype=np.int64, copy=False)
        if last_t0 is not None:
            sample_step.append(int(t0_arr[0] - last_t0))
        if len(t0_arr) > 1:
            diffs = np.diff(t0_arr)
            # Muestreamos diffs para no explotar memoria
            k = min(2000, len(diffs))
            if len(diffs) > k:
                idx2 = rng.choice(len(diffs), size=k, replace=False)
                sample_step.extend(diffs[idx2].astype(np.int64, copy=False).tolist())
            else:
                sample_step.extend(diffs.astype(np.int64, copy=False).tolist())
        last_t0 = int(t0_arr[-1])

        # Ventanas por hora (agregado)
        hours = pd.to_datetime(df_rg["t0"], unit="s", utc=True).dt.floor("H")
        counts = hours.value_counts()
        for k, v in counts.items():
            windows_per_hour[str(k)] += int(v)

    # Convertimos a numpy para las gráficas
    sample_ow = np.asarray(sample_ow, dtype=np.int32)
    sample_pw = np.asarray(sample_pw, dtype=np.int32)
    sample_step = np.asarray(sample_step, dtype=np.int64)

    print("✔ Muestras preparadas para gráficas:")
    print(f"  sample_ow size   : {len(sample_ow):,}")
    print(f"  sample_pw size   : {len(sample_pw):,}")
    print(f"  sample_step size : {len(sample_step):,}")
    print(f"  windows_per_hour : {len(windows_per_hour)} buckets")


    # ---------------------------------------------------------------------
    # 1) Histograma de longitudes OW (span de índices)
    # ---------------------------------------------------------------------
    def plot_hist_ow_len():
        plt.hist(sample_ow, bins=60)
        plt.title("OW length (index span) distribution")
        plt.xlabel("i_ow_1 - i_ow_0 (num timestamps)")
        plt.ylabel("count (sample)")

    save_figure(
        FIG_DIR / "hist_ow_len_idx.png",
        plot_hist_ow_len
    )

    # ---------------------------------------------------------------------
    # 2) Histograma de longitudes PW (span de índices)
    # ---------------------------------------------------------------------
    def plot_hist_pw_len():

        plt.hist(sample_pw, bins=60)
        plt.title("PW length (index span) distribution")
        plt.xlabel("i_pw_1 - i_pw_0 (num timestamps)")
        plt.ylabel("count (sample)")

    save_figure(
        FIG_DIR / "hist_pw_len_idx.png",
        plot_hist_pw_len
    )

    # ---------------------------------------------------------------------
    # 3) Histograma del paso temporal entre ventanas (Δt0)
    # ---------------------------------------------------------------------
    def plot_hist_t0_step():
        plt.hist(sample_step, bins=60)
        plt.title("t0 step distribution (seconds)")
        plt.xlabel("Δt0 (seconds)")
        plt.ylabel("count (sample)")

    save_figure(
        FIG_DIR / "hist_t0_step_seconds.png",
        plot_hist_t0_step
    )

    # ---------------------------------------------------------------------
    # 4) Ventanas por hora (agregado)
    # ---------------------------------------------------------------------
    if windows_per_hour:

        def plot_windows_per_hour():

            series = pd.Series(windows_per_hour).sort_index()
            x = pd.to_datetime(series.index, utc=True)
            y = series.values

            plt.plot(x, y)
            plt.title("Windows per hour (UTC)")
            plt.xlabel("hour")
            plt.ylabel("windows")

        save_figure(
            FIG_DIR / "windows_per_hour.png",
            plot_windows_per_hour,
            figsize=(10, 4)
        )

    print("✔ Figuras F03 generadas correctamente en:", FIG_DIR)


 
    # ---------------------------------------------------------------------
    # Rutas
    # ---------------------------------------------------------------------
    STATS_PATH = ctx["variant_root"] / "03_preparewindowsds_stats.json"
    HTML_PATH = ctx["variant_root"] / "03_preparewindowsds_report.html"
    print("Buscando stats en:", STATS_PATH)
    print("Existe:", STATS_PATH.exists())



    if not STATS_PATH.exists():
        raise FileNotFoundError(f"No se encontró el fichero de estadísticas: {STATS_PATH}")

    with open(STATS_PATH, "r", encoding="utf-8") as f:
        stats = json.load(f)

    # ---------------------------------------------------------------------
    # Figuras a enlazar (orden y títulos)
    # ---------------------------------------------------------------------
    figs = [
        ("OW length distribution (index span)", "hist_ow_len_idx.png"),
        ("PW length distribution (index span)", "hist_pw_len_idx.png"),
        ("t0 step distribution (seconds)", "hist_t0_step_seconds.png"),
        ("Windows per hour (UTC)", "windows_per_hour.png"),
    ]

    # ---------------------------------------------------------------------
    # Utilidades HTML
    # ---------------------------------------------------------------------
    def html_table_from_dict(d):
        if not d:
            return "<em>n/a</em>"
        rows = "".join(
            f"<tr><td>{escape(str(k))}</td><td>{escape(str(v))}</td></tr>"
            for k, v in d.items()
        )
        return f"<table><tbody>{rows}</tbody></table>"

    # ---------------------------------------------------------------------
    # Construcción del HTML
    # ---------------------------------------------------------------------
    html = f"""<!doctype html>
    <html lang="es">
    <head>
    <meta charset="utf-8"/>
    <title>F03 Report — {escape(str(ctx["variant_root"]))}</title>
    <style>
        body {{
        font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
        margin: 24px;
        max-width: 1100px;
        }}
        h1, h2, h3 {{ margin-bottom: 0.3rem; }}
        .meta {{ color: #555; margin-top: 0; }}
        .card {{
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 16px;
        margin: 16px 0;
        }}
        img {{
        max-width: 100%;
        height: auto;
        border: 1px solid #eee;
        border-radius: 10px;
        }}
        table {{ border-collapse: collapse; }}
        td {{
        border: 1px solid #ddd;
        padding: 6px 10px;
        }}
        ul {{ padding-left: 18px; }}
        a {{ text-decoration: none; }}
        .small {{ color: #777; font-size: 0.9em; }}
    </style>
    </head>
    <body>

    <h1>F03 — PrepareWindowsDS</h1>
    <p class="meta">
        Variante: <b>{escape(str(ctx["variant_root"]))}</b><br/>
        Phase: <b>{escape(str(ctx["phase"]))}</b><br/>
        Dataset: <code>{escape(str(OUTPUT_DATASET_PATH))}</code><br/>
        Generado: {escape(stats.get("generated_at_utc", str(datetime.utcnow())))}
    </p>

    <div class="card">
        <h2>Resumen</h2>
        <ul>
        <li>Ventanas totales: <b>{stats.get("num_windows", 0):,}</b></li>
        <li>Row groups: <b>{stats.get("row_groups", 0)}</b></li>
        <li>t0_min: <code>{escape(str(stats.get("t0_min")))}</code></li>
        <li>t0_max: <code>{escape(str(stats.get("t0_max")))}</code></li>
        <li>Ventanas candidatas: <b>{stats.get("windows_candidates", 0):,}</b></li>
        <li>Descartadas por NaN: <b>{stats.get("windows_discarded_nan", 0):,}</b></li>
        <li>Ratio discard NaN: <b>{stats.get("discard_nan_ratio", 0):.3f}</b></li>
        </ul>
    </div>

    <div class="card">
        <h2>Percentiles</h2>

        <h3>OW length (index span)</h3>
        {html_table_from_dict(stats.get("ow_len_idx_percentiles"))}

        <h3>PW length (index span)</h3>
        {html_table_from_dict(stats.get("pw_len_idx_percentiles"))}

        <h3>Δt0 (seconds)</h3>
        {html_table_from_dict(stats.get("t0_step_seconds_percentiles"))}
    </div>

    <div class="card">
        <h2>Figuras</h2>
        <ul>
        {''.join(
            f'<li><a href="figures/{escape(fn)}">{escape(title)}</a></li>'
            for title, fn in figs
        )}
        </ul>

        {''.join(
        f'''
        <h3>{escape(title)}</h3>
        <a href="figures/{escape(fn)}">
            <img src="figures/{escape(fn)}" alt="{escape(title)}"/>
        </a>
        '''
        for title, fn in figs
        )}
    </div>

    <div class="card">
        <h2>Artefactos</h2>
        <ul>
        <li><a href="{escape(STATS_PATH.name)}">f03_stats.json</a></li>
        <li class="small">Parquet: {escape(str(OUTPUT_DATASET_PATH.name))}</li>
        </ul>
    </div>

    </body>
    </html>
    """

    # ---------------------------------------------------------------------
    # Escritura del fichero
    # ---------------------------------------------------------------------
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✔ Informe HTML generado: {HTML_PATH}")


    # -----------------------------------------------------------------
    # -----------------------------------------------------------------

if __name__ == "__main__":
    main()
