#!/usr/bin/env python3
"""
Fase 04 — Target Engineering

Convierte el dataset de ventanas (F03) en un dataset etiquetado
según un objetivo de predicción definido en la variante.

Salida:
- Dataset parquet con columnas:
    * OW_events : list[int]
    * label     : int {0,1}
- Metadata con estadísticas de balance
"""

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
    print_run_context,
    build_phase_outputs,
)
from mlops4ofp.tools.params_manager import ParamsManager
from mlops4ofp.tools.traceability import write_metadata


# ============================================================
# Lógica principal
# ============================================================

def main(variant: str):

    PHASE = "04_targetengineering"

    # --------------------------------------------------
    # Contexto de ejecución
    # --------------------------------------------------
    execution_dir = detect_execution_dir()
    project_root = detect_project_root(execution_dir)

    print(f"[INFO] execution_dir = {execution_dir}")
    print(f"[INFO] project_root  = {project_root}")

    # --------------------------------------------------
    # Cargar parámetros de la variante F04
    # --------------------------------------------------
    pm = ParamsManager(PHASE, project_root)
    pm.set_current(variant)

    variant_root = pm.current_variant_dir()

    with open(variant_root / "params.yaml", "r", encoding="utf-8") as f:
        params = yaml.safe_load(f)

    prediction_name = params.get("prediction_name")
    prediction_objective = params.get("prediction_objective")
    parent_variant_f03 = params.get("parent_variant")

    if not prediction_name:
        raise ValueError("prediction_name must be defined in F04 params.")

    if not prediction_objective:
        raise ValueError("prediction_objective no definido en params.yaml")

    if not parent_variant_f03:
        raise ValueError("parent_variant (F03) no definido en params.yaml")

    # --------------------------------------------------
    # Mostrar contexto
    # --------------------------------------------------
    ctx = assemble_run_context(
        execution_dir=execution_dir,
        project_root=project_root,
        phase=PHASE,
        variant=variant,
        variant_root=variant_root,
    )
    print_run_context(ctx)

    # --------------------------------------------------
    # Resolver linaje: F04 -> F03 -> F02
    # --------------------------------------------------
    f03_params_path = (
        project_root
        / "executions"
        / "03_preparewindowsds"
        / parent_variant_f03
        / "params.yaml"
    )

    if not f03_params_path.exists():
        raise FileNotFoundError(f"No existe params.yaml de F03: {f03_params_path}")

    with open(f03_params_path, "r", encoding="utf-8") as f:
        f03_params = yaml.safe_load(f)

    parent_variant_f02 = f03_params.get("parent_variant")

    if not parent_variant_f02:
        raise ValueError("No se encontró parent_variant (F02) en params.yaml de F03")

    print(f"[INFO] Variante F03: {parent_variant_f03}")
    print(f"[INFO] Variante F02: {parent_variant_f02}")

    # --------------------------------------------------
    # Cargar dataset de ventanas (F03)
    # --------------------------------------------------
    input_dataset_path = (
        project_root
        / "executions"
        / "03_preparewindowsds"
        / parent_variant_f03
        / "03_preparewindowsds_dataset.parquet"
    )

    if not input_dataset_path.exists():
        raise FileNotFoundError(f"No existe dataset F03: {input_dataset_path}")

    table = pq.read_table(input_dataset_path)
    df = table.to_pandas()

    print(f"[INFO] Nº ventanas F03: {len(df)}")

    if "OW_events" not in df.columns or "PW_events" not in df.columns:
        raise RuntimeError("El dataset F03 debe contener columnas OW_events y PW_events")

    # --------------------------------------------------
    # Resolver objetivo de predicción
    # --------------------------------------------------
    operator = prediction_objective.get("operator")
    event_names = prediction_objective.get("events")

    if operator != "OR":
        raise NotImplementedError(f"Operador no soportado: {operator}")

    if not event_names or not isinstance(event_names, list):
        raise ValueError("prediction_objective.events debe ser una lista no vacía")

    print("[INFO] Objetivo de predicción:")
    print(f"  operator = {operator}")
    print(f"  events   = {event_names}")

    # --------------------------------------------------
    # Cargar event_catalog correcto (F02)
    # --------------------------------------------------
    event_catalog_path = (
        project_root
        / "executions"
        / "02_prepareeventsds"
        / parent_variant_f02
        / "02_prepareeventsds_event_catalog.json"
    )

    if not event_catalog_path.exists():
        raise FileNotFoundError(f"No existe event_catalog de F02: {event_catalog_path}")

    with open(event_catalog_path, "r", encoding="utf-8") as f:
        event_catalog = json.load(f)

    # name -> code
    name_to_code = {
        name: int(code)
        for name, code in event_catalog.items()
    }

    # --------------------------------------------------
    # Resolver códigos de eventos objetivo
    # --------------------------------------------------
    target_event_codes = []

    for name in event_names:
        if name not in name_to_code:
            raise ValueError(f"Evento '{name}' no existe en event_catalog")
        target_event_codes.append(name_to_code[name])

    print("[INFO] Códigos de eventos objetivo:", target_event_codes)

    # --------------------------------------------------
    # Etiquetado
    # --------------------------------------------------
    def label_window(pw_events, target_codes):
        return int(any(ev in target_codes for ev in pw_events))

    df["label"] = df["PW_events"].apply(
        lambda pw: label_window(pw, target_event_codes)
    )

    # Dataset final F04
    df_out = df[["OW_events", "label"]].copy()

    # --------------------------------------------------
    # Estadísticas
    # --------------------------------------------------
    total = len(df_out)
    positives = int(df_out["label"].sum())
    negatives = total - positives
    ratio = positives / total if total else 0.0

    stats = {
        "total_windows": total,
        "positive_windows": positives,
        "negative_windows": negatives,
        "positive_ratio": ratio,
        "prediction_objective": prediction_objective,
    }

    print("[INFO] Estadísticas:")
    print(json.dumps(stats, indent=2))

# --------------------------------------------------
# Construir summary.json
# --------------------------------------------------

    lengths = df_out["OW_events"].apply(len)

    avg_len = float(lengths.mean())
    min_len = int(lengths.min())
    max_len = int(lengths.max())
    p95_len = float(lengths.quantile(0.95))

    vocab_size = len(set(ev for seq in df_out["OW_events"] for ev in seq))

    summary = {
        "phase": PHASE,
        "variant": variant,

        "problem": {
            "type": "binary_classification",
            "sequence_based": True,
            "target_definition": prediction_objective,
        },

        "dataset": {
            "num_samples": total,
            "num_positive": positives,
            "num_negative": negatives,
            "positive_ratio": ratio,
        },

        "sequence_statistics": {
            "avg_sequence_length": avg_len,
            "min_sequence_length": min_len,
            "max_sequence_length": max_len,
            "p95_sequence_length": p95_len,
        },

        "vocabulary": {
            "num_unique_events": vocab_size,
        },

        "constraints": {
            "framework": "tensorflow",
            "deployment": ["tflite", "tflite-micro"],
            "target_device": "esp32-class-mcu",
        },
    }


    # --------------------------------------------------
    # Guardar artefactos
    # --------------------------------------------------
    outputs = build_phase_outputs(variant_root, PHASE)

    schema = pa.schema([
        ("OW_events", pa.list_(pa.int32())),
        ("label", pa.int8()),
    ])

    table_out = pa.Table.from_pandas(
        df_out,
        schema=schema,
        preserve_index=False
    )
    pq.write_table(table_out, outputs["dataset"])

    print(f"[OK] Dataset guardado: {outputs['dataset']}")

    pm.save_generated_params(params)
    pm.save_metadata(stats)

    write_metadata(
        stage=PHASE,
        variant=variant,
        parent_variant=parent_variant_f03,
        inputs=[str(input_dataset_path), str(event_catalog_path)],
        outputs=[str(outputs["dataset"])],
        params=params,
        metadata_path=outputs["metadata"],
    )

    print("[OK] Metadata y params guardados")

    summary_path = variant_root / f"{PHASE}_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[OK] Summary guardado: {summary_path}")

    print("[DONE] Fase 04 completada correctamente")


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fase 04 — Target Engineering")
    parser.add_argument("--variant", required=True, help="Variante F04 (vNNN)")
    args = parser.parse_args()

    main(args.variant)
