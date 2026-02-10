import json
import subprocess
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any
import yaml


# ============================================================
# Utilidades git (sin cambios)
# ============================================================

def current_git_hash() -> str:
    """
    Devuelve el commit hash actual de git, o 'unknown' si falla.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"

def _run_git(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception:
        return None


def _git_info() -> Dict[str, Any]:
    status = _run_git(["git", "status", "--porcelain"])
    return {
        "commit": _run_git(["git", "rev-parse", "HEAD"]),
        "branch": _run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "status_clean": (status == ""),
    }


# ============================================================
# CARGA UNIFICADA DE VARIANTES POR FASE
# ============================================================

def load_variants_for_phase(phase: str) -> Dict[str, Any]:
    """Carga executions/<phase>/variants.yaml."""
    reg = Path(f"executions/{phase}/variants.yaml")
    if not reg.exists():
        return {"variants": {}}
    with reg.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"variants": {}}


def load_all_variants() -> Dict[str, Dict[str, Any]]:
    """
    Devuelve:
      {
        "01_explore": { "v001": {...}, "v002": {...} },
        "02_eventsDS": { ... },
        ...
      }
    """
    phases = []
    pdir = Path("executions")
    if not pdir.exists():
        return {}

    for ph in pdir.iterdir():
        if ph.is_dir() and (ph / "variants.yaml").exists():
            phases.append(ph.name)

    result = {}
    for ph in phases:
        result[ph] = load_variants_for_phase(ph)["variants"]

    return result


# ============================================================
# VALIDAR QUE UNA VARIANTE EXISTE (para publish1)
# ============================================================

def validate_variant_exists(phase: str, variant: str):
    reg = load_variants_for_phase(phase)
    if variant not in reg["variants"]:
        raise ValueError(
            f"La variante {variant} no existe en la fase {phase}.\n"
            f"Archivo: executions/{phase}/variants.yaml"
        )
    return True


# ============================================================
# BUSCAR HIJOS DE UNA VARIANTE (para remove1)
# ============================================================

def find_children(phase: str, variant: str) -> List[str]:
    """
    Devuelve lista de strings del tipo "02_eventsDS:v005" que dependen
    de (phase, variant).
    """
    allv = load_all_variants()
    children = []

    for ph, variants in allv.items():
        for vname, meta in variants.items():
            if (
                meta.get("parent_phase") == phase
                and meta.get("parent_variant") == variant
            ):
                children.append(f"{ph}:{vname}")
            parent_list = meta.get("parent_variants_f05")
            if ph == "06_packaging" and isinstance(parent_list, list):
                if isinstance(parent_list, list) and phase == "05_modeling":
                    if variant in parent_list:
                        children.append(f"{ph}:{vname}")
                    
    return children


def can_delete_variant(phase: str, variant: str):
    """
    Comprueba si la variante no tiene hijos.
    """
    validate_variant_exists(phase, variant)
    children = find_children(phase, variant)

    if children:
        msg = (
            f"[FAIL] La variante {phase}:{variant} tiene variantes hijas y NO puede borrarse.\n"
            f"Hijos:\n" + "\n".join(f"  - {c}" for c in children)
        )
        raise RuntimeError(msg)

    print(f"[OK] La variante {phase}:{variant} no tiene hijos y puede borrarse.")


# ============================================================
# MOSTRAR LINAJE COMPLETO (para depuración y docencia)
# ============================================================

def show_lineage(phase: str, variant: str):
    """
    Muestra recursivamente la cadena parent_phase → parent_variant.
    """
    allv = load_all_variants()

    if phase not in allv:
        raise ValueError(f"No existe la fase {phase}")

    if variant not in allv[phase]:
        raise ValueError(f"No existe la variante {variant} en la fase {phase}")

    chain = []
    ph = phase
    va = variant

    while True:
        chain.append((ph, va))
        meta = allv[ph][va]

        parent_ph = meta.get("parent_phase")
        parent_va = meta.get("parent_variant")

        if parent_ph is None or parent_va is None:
            break

        if parent_ph not in allv or parent_va not in allv[parent_ph]:
            break

        ph, va = parent_ph, parent_va

    print("=== LINEAGE ===")
    for ph, va in chain:
        print(f"{ph}:{va}")
    print("================")

    return chain


# ============================================================
# MOSTRAR LINAJE COMPLETO COMO DAG (F06+)
# ============================================================

def show_lineage_dag(phase: str, variant: str):
    """
    Muestra el linaje completo de una variante como un DAG,
    soportando múltiples padres (F06).
    """

    allv = load_all_variants()

    if phase not in allv:
        raise ValueError(f"No existe la fase {phase}")
    if variant not in allv[phase]:
        raise ValueError(f"No existe la variante {variant} en la fase {phase}")

    visited = set()

    def _print_node(ph: str, va: str, prefix: str, is_last: bool):
        node_id = f"{ph}:{va}"
        connector = "└─ " if is_last else "├─ "
        print(prefix + connector + node_id)

        if node_id in visited:
            print(prefix + ("   " if is_last else "│  ") + "[...]")
            return
        visited.add(node_id)

        meta = allv[ph][va]
        parents = []

        # Caso clásico (F01–F05)
        pph = meta.get("parent_phase")
        pva = meta.get("parent_variant")
        if pph and pva:
            parents.append((pph, pva))

        # Caso F06 (linaje múltiple)
        parent_list = meta.get("parent_variants_f05")
        if isinstance(parent_list, list):
            for pv in parent_list:
                parents.append(("05_modeling", pv))

        # Normalizar: eliminar duplicados
        parents = list(dict.fromkeys(parents))

        if not parents:
            return

        new_prefix = prefix + ("   " if is_last else "│  ")
        for i, (pph, pva) in enumerate(parents):
            last = (i == len(parents) - 1)
            _print_node(pph, pva, new_prefix, last)

    print("=== LINEAGE DAG ===")
    print(f"{phase}:{variant}")
    _print_node(phase, variant, "", True)
    print("===================")



# ============================================================
# VALIDACIÓN DE METADATA
# ============================================================

def write_metadata(
    stage: str,
    variant: str,
    parent_variant: str | None,
    inputs: List[str],
    outputs: List[str],
    params: Dict[str, Any],
    metadata_path: str,
    parent_variants: List[str] | None = None,
) -> None:
    metadata_path = Path(metadata_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "stage": stage,
        "variant" : variant,
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "inputs": inputs,
        "outputs": outputs,
        "params": params,
        "git": {"commit": current_git_hash()}
    }
    if parent_variant is not None:
        data["parent_variant"] = parent_variant

    if parent_variants is not None:
        data["parent_variants"] = parent_variants

    metadata_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_schema(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_metadata(metadata: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    errors = []

    fields = schema.get("fields", {})

    for field_name, rules in fields.items():
        if rules.get("required", False) and field_name not in metadata:
            errors.append(f"Falta el campo obligatorio '{field_name}'.")

    for field_name, rules in fields.items():
        if field_name not in metadata:
            continue
        expected = rules.get("type")
        val = metadata[field_name]

        if expected == "string" and not isinstance(val, str):
            errors.append(f"'{field_name}' debe ser string.")
        if expected == "list" and not isinstance(val, list):
            errors.append(f"'{field_name}' debe ser una lista.")
        if expected == "dict" and not isinstance(val, dict):
            errors.append(f"'{field_name}' debe ser un diccionario.")

    stage = metadata.get("stage")
    phase_rules = schema.get("phase_rules", {})
    if stage in phase_rules:
        rules = phase_rules[stage]
        req_inputs = rules.get("required_inputs", [])
        req_outputs = rules.get("required_outputs", [])

        for req in req_inputs:
            if not any(req in p for p in metadata.get("inputs", [])):
                errors.append(f"Falta un input requerido en stage {stage}: '{req}'.")

        for req in req_outputs:
            if not any(req in p for p in metadata.get("outputs", [])):
                errors.append(f"Falta un output requerido en stage {stage}: '{req}'.")

    return errors


def validate_metadata_file(metadata_path: str, schema_path: str) -> List[str]:
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    schema = load_schema(schema_path)
    return validate_metadata(metadata, schema)


# ============================================================
# CLI (ARGPARSE)
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Herramientas de trazabilidad para MLOps4OFP"
    )
    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # Subcomando: can-delete
    can_delete_parser = subparsers.add_parser(
        "can-delete",
        help="Verifica si una variante puede ser eliminada (sin hijos)"
    )
    can_delete_parser.add_argument("--phase", required=True, help="Fase (ej: 01_explore)")
    can_delete_parser.add_argument("--variant", required=True, help="Variante (ej: v001)")

    # Subcomando: validate-variant
    validate_parser = subparsers.add_parser(
        "validate-variant",
        help="Valida que una variante existe"
    )
    validate_parser.add_argument("--phase", required=True, help="Fase (ej: 01_explore)")
    validate_parser.add_argument("--variant", required=True, help="Variante (ej: v001)")

    # Subcomando: show-lineage
    lineage_parser = subparsers.add_parser(
        "show-lineage",
        help="Muestra la cadena de ancestros de una variante"
    )
    lineage_parser.add_argument("--phase", required=True, help="Fase (ej: 02_prepareeventsds)")
    lineage_parser.add_argument("--variant", required=True, help="Variante (ej: v002)")

    # Subcomando: show-lineage-dag
    lineage_dag_parser = subparsers.add_parser(
        "show-lineage-dag",
        help="Muestra el linaje completo como DAG (soporta F06)"
    )
    lineage_dag_parser.add_argument("--phase", required=True, help="Fase")
    lineage_dag_parser.add_argument("--variant", required=True, help="Variante")



    args = parser.parse_args()

    try:
        if args.command == "can-delete":
            can_delete_variant(args.phase, args.variant)
            sys.exit(0)
        elif args.command == "validate-variant":
            validate_variant_exists(args.phase, args.variant)
            print(f"[OK] La variante {args.phase}:{args.variant} existe.")
            sys.exit(0)
        elif args.command == "show-lineage":
            show_lineage(args.phase, args.variant)
            sys.exit(0)
        elif args.command == "show-lineage-dag":
            show_lineage_dag(args.phase, args.variant)
            sys.exit(0)
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

