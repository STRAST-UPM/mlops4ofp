#!/usr/bin/env python3
"""
Fase 06 — PACKAGING / System Composition

Construye un paquete de sistema autocontenido que incluye:

- modelo oficial de cada variante F05
- dataset etiquetado de cada F04 asociado
- objetivos formales
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
    temporal = params.get("temporal", {})

    if not parent_variants_f05:
        raise ValueError("parent_variants_f05 no puede estar vacío")

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
    # Resolver linaje
    # --------------------------------------------------
    lineage = {
        "f05": set(parent_variants_f05),
        "f04": set(),
        "f03": set(),
    }

    f05_to_f04 = {}
    f04_to_f03 = {}

    # F05 → F04
    for v05 in parent_variants_f05:
        p = project_root / "executions" / "05_modeling" / v05 / "params.yaml"
        if not p.exists():
            raise FileNotFoundError(f"No existe F05: {v05}")

        f05_params = yaml.safe_load(p.read_text())
        v04 = f05_params["parent_variant"]

        lineage["f04"].add(v04)
        f05_to_f04[v05] = v04

    # F04 → F03
    for v04 in lineage["f04"]:
        p = project_root / "executions" / "04_targetengineering" / v04 / "params.yaml"
        f04_params = yaml.safe_load(p.read_text())
        v03 = f04_params["parent_variant"]

        lineage["f03"].add(v03)
        f04_to_f03[v04] = v03

    # Validación fuerte: mismo régimen temporal
    regimes = set()

    for v03 in lineage["f03"]:
        p = project_root / "executions" / "03_preparewindowsds" / v03 / "params.yaml"
        f03_params = yaml.safe_load(p.read_text())

        regime = (
            f03_params["temporal"]["Tu"],
            f03_params["temporal"]["OW"],
            f03_params["temporal"]["PW"],
        )
        regimes.add(regime)

    if len(regimes) != 1:
        raise RuntimeError(
            f"Las variantes F05 no comparten el mismo régimen temporal: {regimes}"
        )

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
        }

    objectives_path = variant_root / "objectives.json"
    objectives_path.write_text(json.dumps(objectives, indent=2), encoding="utf-8")
    print(f"[OK] Objetivos materializados")

    # --------------------------------------------------
    # Copiar datasets F04 (in/out ya preparados)
    # --------------------------------------------------
    datasets_dir = variant_root / "datasets"
    datasets_dir.mkdir(exist_ok=True)

    dataset_paths = []

    for v04 in lineage["f04"]:
        src = (
            project_root
            / "executions"
            / "04_targetengineering"
            / v04
            / "04_targetengineering_dataset.parquet"
        )

        if not src.exists():
            raise FileNotFoundError(f"No existe dataset F04: {src}")

        dst = datasets_dir / f"{v04}__dataset.parquet"
        shutil.copyfile(src, dst)

        dataset_paths.append(str(dst))

    print(f"[OK] {len(dataset_paths)} datasets F04 copiados")

    # --------------------------------------------------
    # Copiar modelos oficiales de cada F05
    # --------------------------------------------------
    models_dir = variant_root / "models"
    models_dir.mkdir(exist_ok=True)

    selected_models = []

    for v05 in parent_variants_f05:

        # Se asume: cada F05 deja exactamente un modelo oficial en models/
        model_root = project_root / "executions" / "05_modeling" / v05 / "models"

        model_dirs = [d for d in model_root.iterdir() if d.is_dir()]

        if len(model_dirs) == 0:
            raise RuntimeError(f"F05 {v05} no contiene modelo oficial")

        if len(model_dirs) > 1:
            raise RuntimeError(
                f"F05 {v05} contiene múltiples modelos; F06 espera exactamente uno"
            )

        src = model_dirs[0]
        dst = models_dir / f"{v05}__{src.name}"

        if dst.exists():
            shutil.rmtree(dst)

        shutil.copytree(src, dst)

        selected_models.append({
            "source_f05": v05,
            "model_id": src.name,
        })

    print(f"[OK] {len(selected_models)} modelos copiados")

    # --------------------------------------------------
    # Metadata F06
    # --------------------------------------------------
    metadata = {
        "phase": PHASE,
        "variant": variant,
        "git_commit": get_git_hash(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "temporal": regimes.pop(),
        "lineage": {k: sorted(v) for k, v in lineage.items()},
        "models": selected_models,
        "objectives": list(objectives.keys()),
        "datasets": dataset_paths,
    }

    metadata_path = variant_root / f"{PHASE}_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # --------------------------------------------------
    # Trazabilidad
    # --------------------------------------------------
    write_metadata(
        stage=PHASE,
        variant=variant,
        parent_variant=None,
        parent_variants=parent_variants_f05,
        inputs=dataset_paths,
        outputs=[str(models_dir), str(datasets_dir), str(objectives_path)],
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
