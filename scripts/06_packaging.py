#!/usr/bin/env python3
"""
Fase 06 — PACKAGING / System Composition

Construye un paquete de sistema autocontenido que incluye:
- selección explícita de modelos (desde F05)
- objetivos formales (desde F04_targetengineering)
- catálogo de eventos (desde F02_prepareeventsds)
- replay de eventos reproducible
- metadata y trazabilidad completas

NO ejecuta inferencia.
NO calcula métricas.
NO asume ningún runtime.
"""

import sys
from pathlib import Path
import argparse
import json
from datetime import datetime, timezone
from time import perf_counter
import shutil

import yaml
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

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
)
from mlops4ofp.tools.params_manager import ParamsManager
from mlops4ofp.tools.traceability import write_metadata
from mlops4ofp.tools.artifacts import get_git_hash


# ============================================================
# Lógica principal
# ============================================================

def main(variant: str):

    PHASE = "06_packaging"
    t_start = perf_counter()

    # --------------------------------------------------
    # Contexto de ejecución
    # --------------------------------------------------
    execution_dir = detect_execution_dir()
    project_root = detect_project_root(execution_dir)

    print(f"[INFO] execution_dir = {execution_dir}")
    print(f"[INFO] project_root  = {project_root}")

    # --------------------------------------------------
    # Cargar parámetros F06
    # --------------------------------------------------
    pm = ParamsManager(PHASE, project_root)
    pm.set_current(variant)
    variant_root = pm.current_variant_dir()

    with open(variant_root / "params.yaml", "r", encoding="utf-8") as f:
        params = yaml.safe_load(f)

    parent_variants_f05 = params["parent_variants_f05"]
    temporal = params["temporal"]
    models_cfg = params["models"]
    replay_cfg = params["replay"]

    if not isinstance(models_cfg, list) or not models_cfg:
        raise ValueError("models debe ser una lista no vacía")

    # --------------------------------------------------
    # Contexto
    # --------------------------------------------------
    ctx = assemble_run_context(
        execution_dir=execution_dir,
        project_root=project_root,
        phase=PHASE,
        variant=variant,
        variant_root=variant_root,
    )
    print_run_context(ctx)

    print("[INFO] Parámetros F06:")
    print(json.dumps(params, indent=2))

    # --------------------------------------------------
    # Resolver linaje completo
    # --------------------------------------------------
    lineage = {
        "f05": set(parent_variants_f05),
        "f04": set(),
        "f03": set(),
        "f02": set(),
    }

    f05_to_f04 = {}
    f04_to_f03 = {}
    f03_to_f02 = {}

    for v05 in parent_variants_f05:
        p = project_root / "executions" / "05_modeling" / v05 / "params.yaml"
        f05_params = yaml.safe_load(p.read_text())
        v04 = f05_params["parent_variant"]
        lineage["f04"].add(v04)
        f05_to_f04[v05] = v04

    for v04 in lineage["f04"]:
        p = project_root / "executions" / "04_targetengineering" / v04 / "params.yaml"
        f04_params = yaml.safe_load(p.read_text())
        v03 = f04_params["parent_variant"]
        lineage["f03"].add(v03)
        f04_to_f03[v04] = v03

    for v03 in lineage["f03"]:
        p = project_root / "executions" / "03_preparewindowsds" / v03 / "params.yaml"
        f03_params = yaml.safe_load(p.read_text())
        v02 = f03_params["parent_variant"]
        lineage["f02"].add(v02)
        f03_to_f02[v03] = v02

    if len(lineage["f02"]) != 1:
        raise RuntimeError(f"F06 requiere un único F02 común: {lineage['f02']}")

    parent_f02 = list(lineage["f02"])[0]

    print("[INFO] Linaje resuelto:")
    print(json.dumps({k: sorted(v) for k, v in lineage.items()}, indent=2))

    # --------------------------------------------------
    # Materializar objetivos (F04)
    # --------------------------------------------------
    objectives = {}

    for v04 in lineage["f04"]:
        p = project_root / "executions" / "04_targetengineering" / v04 / "params.yaml"
        f04_params = yaml.safe_load(p.read_text())
        objectives[v04] = {
            "expression": f04_params.get("target_expression"),
            "params": f04_params,
        }

    objectives_path = variant_root / "objectives.json"
    objectives_path.write_text(json.dumps(objectives, indent=2), encoding="utf-8")
    print(f"[OK] Objetivos materializados: {objectives_path}")

    # --------------------------------------------------
    # Materializar catálogo de eventos (F02)
    # --------------------------------------------------
    p = project_root / "executions" / "02_prepareeventsds" / parent_f02 / "params.yaml"
    f02_params = yaml.safe_load(p.read_text())

    events_catalog = f02_params.get("event_catalog")
    if not events_catalog:
        raise RuntimeError("No se encontró event_catalog en F02")

    events_path = variant_root / "events_catalog.json"
    events_path.write_text(json.dumps(events_catalog, indent=2), encoding="utf-8")
    print(f"[OK] Catálogo de eventos materializado: {events_path}")

    # --------------------------------------------------
    # Validar y copiar modelos
    # --------------------------------------------------
    models_dir = variant_root / "models"
    models_dir.mkdir(exist_ok=True)

    selected_models = []

    for m in models_cfg:
        f04_id = m["f04_id"]
        model_id = m["model_id"]
        source_f05 = m["source_f05"]

        if source_f05 not in parent_variants_f05:
            raise ValueError(f"Modelo {model_id} usa F05 no declarado: {source_f05}")

        src = (
            project_root
            / "executions"
            / "05_modeling"
            / source_f05
            / "models"
            / model_id
        )

        if not src.exists():
            raise FileNotFoundError(f"No existe modelo: {src}")

        dst = models_dir / f"{f04_id}__{model_id}"
        if dst.exists():
            shutil.rmtree(dst)

        shutil.copytree(src, dst)

        selected_models.append({
            "f04_id": f04_id,
            "model_id": model_id,
            "source_f05": source_f05,
        })

    print(f"[OK] {len(selected_models)} modelos copiados")

    # --------------------------------------------------
    # Materializar replay
    # --------------------------------------------------
    replay_dir = variant_root / "replay"
    replay_dir.mkdir(exist_ok=True)

    replay_input = (
        project_root
        / "executions"
        / "02_prepareeventsds"
        / parent_f02
        / "02_prepareeventsds_dataset.parquet"
    )

    table = pq.read_table(replay_input)
    pq.write_table(table, replay_dir / "replay_events.parquet")

    print(f"[OK] Replay materializado")

    # --------------------------------------------------
    # Metadata propia de F06
    # --------------------------------------------------
    metadata = {
        "phase": PHASE,
        "variant": variant,
        "git_commit": get_git_hash(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "temporal": temporal,
        "lineage": {k: sorted(v) for k, v in lineage.items()},
        "models": selected_models,
        "objectives": list(objectives.keys()),
        "events_catalog": list(events_catalog.keys()),
    }

    metadata_path = variant_root / f"{PHASE}_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # --------------------------------------------------
    # Trazabilidad global
    # --------------------------------------------------
    write_metadata(
        stage=PHASE,
        variant=variant,
        parent_variant=None,
        parent_variants=parent_variants_f05,
        inputs=[str(replay_input)],
        outputs=[
            str(models_dir),
            str(replay_dir),
            str(objectives_path),
            str(events_path),
        ],
        params=params,
        metadata_path=metadata_path,
    )

    print("[OK] Metadata de trazabilidad guardada")
    print(f"[DONE] F06 completada en {perf_counter() - t_start:.1f}s")


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fase 06 — Packaging")
    parser.add_argument("--variant", required=True, help="Variante F06 (vNNN)")
    args = parser.parse_args()
    main(args.variant)
