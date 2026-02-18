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
        
        # Buscar el modelo en la carpeta models/ (solo debe haber uno)
        models_dir = project_root / "executions" / "05_modeling" / v05 / "models"
        if not models_dir.exists():
            raise FileNotFoundError(f"No existe carpeta models/ en F05 {v05}")
        
        model_dirs = [d for d in models_dir.iterdir() if d.is_dir()]
        if len(model_dirs) == 0:
            raise RuntimeError(f"F05 {v05} no contiene ningún modelo en models/")
        if len(model_dirs) > 1:
            raise RuntimeError(f"F05 {v05} contiene múltiples modelos (se espera solo uno)")
        
        model_dir = model_dirs[0]
        model_summary_path = model_dir / "model_summary.json"
        if not model_summary_path.exists():
            raise FileNotFoundError(f"No existe model_summary.json en {model_dir}")
        
        model_summary = json.loads(model_summary_path.read_text())
        prediction_name = model_summary.get("prediction_name")
        if not prediction_name:
            raise RuntimeError(f"F05 {v05} no contiene prediction_name en model_summary.json")

        lineage["f04"].add(v04)
        f05_to_f04[v05] = {
            "f04": v04,
            "prediction_name": prediction_name,
        }


    # F04 → F03
    for v04 in lineage["f04"]:
        p = project_root / "executions" / "04_targetengineering" / v04 / "params.yaml"
        f04_params = yaml.safe_load(p.read_text())
        v03 = f04_params["parent_variant"]

        lineage["f03"].add(v03)
        f04_to_f03[v04] = v03

    # Validación fuerte: mismo régimen temporal
    temporal_by_f03 = {}

    f03_registry_path = (
        project_root / "executions" / "03_preparewindowsds" / "variants.yaml"
    )
    f03_registry = {}
    if f03_registry_path.exists():
        f03_registry = yaml.safe_load(f03_registry_path.read_text()) or {}
        f03_registry = f03_registry.get("variants", {}) or {}

    for v03 in lineage["f03"]:
        p = project_root / "executions" / "03_preparewindowsds" / v03 / "params.yaml"
        f03_params = yaml.safe_load(p.read_text())
        f03_metadata_path = (
            project_root
            / "executions"
            / "03_preparewindowsds"
            / v03
            / "03_preparewindowsds_metadata.json"
        )
        tu_value = None
        if f03_metadata_path.exists():
            f03_metadata = json.loads(f03_metadata_path.read_text())
            tu_value = f03_metadata.get("Tu")
        if tu_value is None:
            tu_value = f03_params.get("Tu")

        created_at_raw = (f03_registry.get(v03, {}) or {}).get("created_at")
        created_at_dt = datetime.min.replace(tzinfo=timezone.utc)
        if created_at_raw:
            created_at_dt = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))

        temporal_by_f03[v03] = {
            "Tu": tu_value,
            "OW": f03_params.get("OW"),
            "PW": f03_params.get("PW"),
            "LT": f03_params.get("LT"),
            "created_at": created_at_dt,
        }

    ow_values = {t["OW"] for t in temporal_by_f03.values()}
    pw_values = {t["PW"] for t in temporal_by_f03.values()}
    lt_values = {t["LT"] for t in temporal_by_f03.values()}

    if len(ow_values) != 1 or len(pw_values) != 1 or len(lt_values) != 1:
        raise RuntimeError(
            "Las variantes F05 no comparten el mismo régimen temporal (OW, PW, LT): "
            f"{temporal_by_f03}"
        )

    ordered_f03 = sorted(
        temporal_by_f03.items(),
        key=lambda x: x[1]["created_at"],
        reverse=True,
    )

    tu_value = None
    for _v03, temporal_data in ordered_f03:
        if temporal_data["Tu"] is not None:
            tu_value = temporal_data["Tu"]
            break

    if tu_value is None:
        tu_value = ordered_f03[0][1]["Tu"]

    resolved_temporal = {
        "Tu": tu_value,
        "OW": next(iter(ow_values)),
        "PW": next(iter(pw_values)),
        "LT": next(iter(lt_values)),
    }

    params["temporal"] = resolved_temporal
    with open(variant_root / "params.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(params, f, sort_keys=False)

    print("[INFO] Linaje resuelto:")
    print(json.dumps({k: sorted(v) for k, v in lineage.items()}, indent=2))

    # --------------------------------------------------
    # Materializar objetivos (F04)
    # --------------------------------------------------
    objectives = {}

    for v04 in lineage["f04"]:
        p = project_root / "executions" / "04_targetengineering" / v04 / "params.yaml"
        f04_params = yaml.safe_load(p.read_text())

        prediction_name = f04_params.get("prediction_name")
        if not prediction_name:
            metadata_path = (
                project_root
                / "executions"
                / "04_targetengineering"
                / v04
                / "04_targetengineering_metadata.json"
            )
            if metadata_path.exists():
                f04_metadata = json.loads(metadata_path.read_text())
                prediction_name = f04_metadata.get("params", {}).get("prediction_name")

        if not prediction_name:
            raise RuntimeError(
                f"No se pudo resolver prediction_name para F04 {v04} desde params/metadata"
            )

        objectives[v04] = {
            "prediction_name": prediction_name,
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
        prediction_name = f05_to_f04[v05]["prediction_name"]

        dst = models_dir / f"{prediction_name}__{src.name}"

        if dst.exists():
            shutil.rmtree(dst)

        shutil.copytree(src, dst)

        selected_models.append({
            "source_f05": v05,
            "model_id": src.name,
            "prediction_name": prediction_name,
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
        "temporal": resolved_temporal,
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
