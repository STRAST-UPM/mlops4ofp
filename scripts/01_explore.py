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
from mlops4ofp.tools.figures import save_figure

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


def generate_figures_and_report(
    *,
    variant: str,
    ctx: dict,
    df_out: pd.DataFrame,
    numeric_cols: list[str],
    Tu_value: float,
    raw_path: Path,
):
    figures_dir = ctx["figures_dir"]
    figures_dir.mkdir(parents=True, exist_ok=True)
    fig_paths = []

    # --- Nulos ---
    na_pct = df_out.isna().mean() * 100
    fig1 = figures_dir / "01_nulls_pct.png"
    save_figure(
        fig1,
        plot_fn=lambda: (
            na_pct.sort_values(ascending=False).plot(kind="bar"),
            plt.title("Porcentaje de nulos por columna"),
            plt.ylabel("% nulos"),
        ),
        figsize=(12, 4),
    )
    fig_paths.append(("Nulos por columna", fig1))

    # --- Medias ---
    desc = df_out.describe().T
    fig2 = figures_dir / "02_mean_per_variable.png"
    save_figure(
        fig2,
        plot_fn=lambda: (
            desc["mean"].plot(),
            plt.title("Media por variable numérica"),
        ),
        figsize=(12, 4),
    )
    fig_paths.append(("Media por variable", fig2))

    # --- Histogramas ---
    for col in numeric_cols:
        data = df_out[col].dropna()
        if data.empty:
            continue
        bins = max(30, min(100, int(np.sqrt(len(data)))))
        out = figures_dir / f"hist_{col}.png"
        save_figure(
            out,
            plot_fn=lambda d=data, b=bins, c=col: (
                plt.hist(d, bins=b, edgecolor="black", alpha=0.7),
                plt.title(f"Histograma — {c}"),
            ),
            figsize=(8, 4),
        )
        fig_paths.append((f"Histograma {col}", out))

    # --- Series temporales ---
    if "segs" in df_out.columns:
        for col in numeric_cols:
            if col == "segs":
                continue
            out = figures_dir / f"time_{col}.png"
            save_figure(
                out,
                plot_fn=lambda c=col: (
                    plt.plot(df_out["segs"], df_out[c]),
                    plt.title(f"Evolución temporal — {c}"),
                    plt.xlabel("segs"),
                ),
                figsize=(12, 4),
            )
            fig_paths.append((f"Evolución temporal {col}", out))

    # --- Correlación ---
    if len(numeric_cols) >= 2:
        corr = df_out[numeric_cols].corr()
        figc = figures_dir / "correlation_matrix.png"
        save_figure(
            figc,
            plot_fn=lambda: (
                plt.imshow(corr, cmap="coolwarm", interpolation="nearest"),
                plt.colorbar(),
                plt.title("Matriz de correlación"),
                plt.xticks(range(len(numeric_cols)), numeric_cols, rotation=90),
                plt.yticks(range(len(numeric_cols)), numeric_cols),
            ),
            figsize=(10, 8),
        )
        fig_paths.append(("Matriz de correlación", figc))

    # --- HTML ---
    report_path = ctx["outputs"]["report"]
    sections = [
        f"<h1>Exploration Report — Variante {variant}</h1>",
        f"<p><b>Archivo RAW:</b> {raw_path}</p>",
        f"<p><b>Filas:</b> {len(df_out):,}</p>",
        f"<p><b>Columnas numéricas:</b> {df_out.shape[1]}</p>",
        f"<p><b>Tu:</b> {Tu_value}</p>",
        "<hr>",
        "<h2>Nulos por columna (%)</h2>",
        na_pct.to_frame("pct_nulls").to_html(),
        "<h2>Estadísticos básicos</h2>",
        desc.to_html(),
        "<hr>",
        "<h2>Figuras</h2>",
    ]

    for title, path in fig_paths:
        sections.append(f"<h3>{title}</h3><img src='figures/{path.name}' width='900'>")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("<html><body>" + "\n".join(sections) + "</body></html>")


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

    generate_figures_and_report(
        variant=variant,
        ctx=ctx,
        df_out=df_out,
        numeric_cols=[c for c in numeric_cols if c != "segs"],
        Tu_value=Tu_value,
        raw_path=raw_copy,
    )

    print(f"\n===== FASE {PHASE} COMPLETADA =====")


if __name__ == "__main__":
    main()
