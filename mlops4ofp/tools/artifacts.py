# mlops4ofp/tools/artifacts.py
import subprocess

def get_git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"
    
from pathlib import Path
import numpy as np
import pandas as pd

def save_numeric_dataset(
    df: pd.DataFrame,
    output_path: Path,
    index_name: str = "segs",
    drop_columns: list | None = None,
) -> list[str]:
    """
    Guarda un dataset parquet con solo columnas numéricas (+ index si aplica).
    Devuelve la lista final de columnas.
    """
    df_out = df.copy()

    if df_out.index.name == index_name:
        df_out = df_out.reset_index()

    if drop_columns:
        df_out = df_out.drop(columns=drop_columns, errors="ignore")

    numeric_cols = df_out.select_dtypes(include=[np.number]).columns.tolist()

    if index_name not in numeric_cols and index_name in df_out.columns:
        numeric_cols = [index_name] + [c for c in numeric_cols if c != index_name]

    df_out = df_out[numeric_cols]
    df_out.to_parquet(output_path)

    return numeric_cols, df_out


import json
from datetime import datetime
from pathlib import Path

def save_params_and_metadata(
    *,
    phase: str,
    variant: str,
    variant_root: Path,
    raw_path: Path | None = None,
    gen_params: dict,
    metadata_extra: dict,
    pm=None,
    git_commit: str = "unknown",
):
    """
    Guarda:
    - <phase>_params.json
    - <phase>_metadata.json
    """
    params_path = variant_root / f"{phase}_params.json"
    metadata_path = variant_root / f"{phase}_metadata.json"

    with open(params_path, "w", encoding="utf-8") as f:
        json.dump(gen_params, f, indent=2)

    if pm is not None:
        pm.save_generated_params(gen_params)

    metadata = {
        "phase": phase,
        "variant": variant,
        "git_commit": git_commit,
        "generated_at": datetime.now().astimezone().isoformat(),
        **metadata_extra,
    }

    if raw_path is not None:
        metadata["raw_file"] = str(raw_path)

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    if pm is not None:
        pm.save_metadata(metadata)

    return params_path, metadata_path




