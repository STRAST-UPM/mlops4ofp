from pathlib import Path
import sys
import yaml

def detect_execution_dir() -> Path:
    """
    Devuelve el directorio del artefacto ejecutado.
    - Notebook / IPython: cwd
    - Script: directorio del fichero
    """
    if "ipykernel" in sys.modules:
        return Path.cwd().resolve()
    else:
        return Path(__file__).resolve().parent

def detect_project_root(execution_dir: Path) -> Path:
    """
    Sube desde execution_dir hasta encontrar la raíz del proyecto.
    Criterio: existencia de carpeta 'mlops4ofp'.
    """
    current = execution_dir.resolve()

    for _ in range(10):
        if (current / "mlops4ofp").exists():
            return current
        if current.parent == current:
            break
        current = current.parent

    raise RuntimeError("No se pudo detectar el PROJECT_ROOT")

def build_run_context(execution_dir: Path, project_root: Path) -> dict:
    """
    Construye el contexto mínimo de ejecución compartido
    entre notebooks y scripts.
    """
    return {
        "execution_dir": execution_dir,
        "project_root": project_root,
    }

def build_variant_paths(variant_root: Path) -> dict:
    """
    Rutas estándar dentro de una VARIANTE.
    Las salidas son ficheros en la raíz de la variante.
    """
    return {
        "variant_root": variant_root,
        "figures_dir": variant_root / "figures",
    }

def ensure_variant_dirs(paths: dict) -> None:
    """
    Crea directorios necesarios de la variante si no existen.
    """
    figures_dir = paths.get("figures_dir")
    if figures_dir:
        figures_dir.mkdir(parents=True, exist_ok=True)

# def resolve_variant_root(project_root: Path, phase: str, variant: str) -> Path:
#     """
#     Devuelve la carpeta de la variante ya creada por Makefile / params_manager.
#     """
#     return project_root / "executions" / phase / variant
# 
# def validate_variant_root(variant_root: Path) -> None:
#     """
#     Verifica que la carpeta de la variante existe.
#     """
#     if not variant_root.exists():
#         raise RuntimeError(f"VARIANT_ROOT no existe: {variant_root}")

def assemble_run_context(
    execution_dir: Path,
    project_root: Path,
    phase: str,
    variant: str,
    variant_root: Path,
) -> dict:
    """
    Ensambla el contexto final de ejecución.
    La ruta de la variante la decide ParamsManager.
    """
    figures_dir = variant_root / "figures"
    figures_dir.mkdir(exist_ok=True)

    return {
        "execution_dir": execution_dir,
        "project_root": project_root,
        "phase": phase,
        "variant": variant,
        "variant_root": variant_root,
        "figures_dir": figures_dir,
    }


def print_run_context(ctx: dict) -> None:
    """
    Imprime el contexto de ejecución de forma controlada.
    """
    for k, v in ctx.items():
        print(f"[CTX] {k}: {v}")

def build_phase_outputs(variant_root: Path, phase: str) -> dict:
    """
    Construye los ficheros de salida estándar de una fase en una variante.
    """
    return {
        "dataset": variant_root / f"{phase}_dataset.parquet",
        "report": variant_root / f"{phase}_report.html",
        "params": variant_root / f"{phase}_params.json",
        "metadata": variant_root / f"{phase}_metadata.json",
    }

