#!/usr/bin/env python3
import sys
import json
import shutil
from pathlib import Path

import yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


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
import mlops4ofp.tools.html_reports.html01Old as explore_report

execution_dir = detect_execution_dir()
PROJECT_ROOT = detect_project_root(execution_dir)
PHASE = "01_explore"

# ============================================================
# LÓGICA ESPECÍFICA FASE 01
# ============================================================

def prepare_time_axis(df: pd.DataFrame):
    time_col = None
    if "Timestamp" in df.columns:
        time_col = "Timestamp"
    else:
        candidates = [
            c for c in df.columns
            if any(k in c.lower() for k in ["time", "timestamp", "fecha", "date"])
        ]
        if candidates:
            time_col = candidates[0]

    if time_col:
        ts = pd.to_datetime(df[time_col])
        df["segs"] = (ts - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
        df = df.set_index("segs").sort_index()
    elif "segs" in df.columns:
        df = df.set_index("segs").sort_index()
    else:
        raise RuntimeError(
            "No existe columna temporal ('Timestamp' o 'segs'). "
            "Fase 01 requiere una de ellas."
        )

    df["segs_diff"] = df.index.to_series().diff()
    Tu_value = float(df["segs_diff"].median())
    return df, Tu_value


def apply_cleaning(df: pd.DataFrame, params: dict):
    strategy = params.get("cleaning_strategy", "none")
    nan_values = params.get("nan_values", [])
    error_values_by_column = params.get("error_values_by_column", {})

    df_clean = df.copy()
    nan_repl = 0

    if strategy == "none":
        return df_clean, nan_repl

    if nan_values:
        before = df_clean.isna().sum().sum()
        df_clean.replace(nan_values, np.nan, inplace=True)
        after = df_clean.isna().sum().sum()
        nan_repl += int(after - before)

    if strategy == "full":
        for col, vals in error_values_by_column.items():
            if col in df_clean.columns:
                before = df_clean[col].isna().sum()
                df_clean[col].replace(vals, np.nan, inplace=True)
                after = df_clean[col].isna().sum()
                nan_repl += int(after - before)
        df_clean.dropna(axis=0, how="all", inplace=True)

    return df_clean, nan_repl


# ============================================================
# MAIN
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True)
    args = parser.parse_args()

    variant = args.variant
    print(f"\n===== INICIO FASE {PHASE} / {variant} =====")

    execution_dir = detect_execution_dir()
    project_root = detect_project_root(execution_dir)

    pm = ParamsManager(PHASE, project_root)
    pm.set_current(variant)
    variant_root = pm.current_variant_dir()

    ctx = assemble_run_context(
        execution_dir=execution_dir,
        project_root=project_root,
        phase=PHASE,
        variant=variant,
        variant_root=variant_root,
    )

    pm = ParamsManager(PHASE, project_root)
    pm.set_current(variant)

    params_path = ctx["variant_root"] / "params.yaml"
    with open(params_path, "r", encoding="utf-8") as f:
        params = yaml.safe_load(f) or {}

    validate_params(PHASE, params, project_root)
    ctx["variant_params"] = params


    # RAW (ruta en params.yaml relativa a project_root)
    raw_input = (project_root / params["raw_dataset_path"]).expanduser().resolve()
    raw_dir = project_root / "data" / "01-raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_copy = raw_dir / f"{PHASE}_raw_{raw_input.name}"
    if not raw_copy.exists():
        shutil.copy2(raw_input, raw_copy)

    if raw_copy.suffix.lower() == ".csv":
        df = pd.read_csv(raw_copy)
    else:
        df = pd.read_parquet(raw_copy)

    max_lines = params.get("max_lines")
    first_line = params.get("first_line")
    if max_lines is not None or first_line is not None:
        start_idx = max(int(first_line or 1) - 1, 0)
        end_idx = start_idx + int(max_lines) if max_lines is not None else None
        df = df.iloc[start_idx:end_idx].reset_index(drop=True)

    df, Tu_value = prepare_time_axis(df)
    df_clean, nan_repl_value = apply_cleaning(df, params)

    outputs = build_phase_outputs(ctx["variant_root"], PHASE)
    ctx["outputs"] = outputs  # para que generate_figures_and_report use ctx["outputs"]["report"]

    numeric_cols, df_out = save_numeric_dataset(
        df=df_clean,
        output_path=outputs["dataset"],
        index_name="segs",
        drop_columns=["Timestamp", "segs_diff", "segs_dt"],
    )

    gen_params = {
        "Tu": float(Tu_value),
        "n_rows": int(len(df_out)),
        "n_cols": int(df_out.shape[1]),
        "numeric_cols": numeric_cols,
        "nan_replacements_total": int(nan_repl_value),
    }

    metadata_extra = {
        "dataset_explored": str(outputs["dataset"]),
        "Tu": float(Tu_value),
        "nan_replacements_total": int(nan_repl_value),
        "n_rows": int(len(df_out)),
        "n_cols": int(df_out.shape[1]),
        "cleaning_strategy": params.get("cleaning_strategy"),
        "nan_values": params.get("nan_values"),
        "error_values_by_column": params.get("error_values_by_column"),
    }

    save_params_and_metadata(
        phase=PHASE,
        variant=variant,
        variant_root=ctx["variant_root"],
        raw_path=raw_copy,
        gen_params=gen_params,
        metadata_extra=metadata_extra,
        pm=pm,
        git_commit=get_git_hash(),
    )

    explore_report.generate_figures_and_report(
        variant=variant,
        ctx=ctx,
        df_out=df_out,
        numeric_cols=[c for c in numeric_cols if c != "segs"],
        Tu_value=Tu_value,
    )

    print(f"\n===== FASE {PHASE} COMPLETADA =====")


if __name__ == "__main__":
    main()
