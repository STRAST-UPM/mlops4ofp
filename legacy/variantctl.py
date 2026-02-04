#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Simple CLI para gestionar variantes de la Fase 02 (prepareEventsDS).
#
# Uso:
#   python scripts/variantctl.py list
#   python scripts/variantctl.py info VAR_ID

import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=REPO_ROOT, text=True)


def cmd_list() -> None:
    print("==> Variantes por commit (grep 'variant: prepareeventsds')")
    run(["git", "log", "--oneline", "--grep", "variant: prepareeventsds"])
    print("\n==> Variantes con carpetas dedicadas (outputs/reports/variants/*)")
    var_dir = REPO_ROOT / "outputs" / "reports" / "variants"
    if var_dir.is_dir():
        for p in sorted(var_dir.iterdir()):
            if p.is_dir():
                print(" -", p.name)
    else:
        print("(no hay carpetas de variantes)")


def cmd_info(var_id: str) -> None:
    print(f"==> Información de la variante: {var_id}\n")
    print("Últimos commits relacionados:")
    run(["git", "log", "--oneline", "--grep", f"VAR={var_id}"])
    print("\nArtifacts de la variante (si existen):")
    base_paths = [
        REPO_ROOT / "data" / "02-interim" / "variants" / var_id,
        REPO_ROOT / "outputs" / "interim" / "variants" / var_id,
        REPO_ROOT / "outputs" / "metadata" / "variants" / var_id,
        REPO_ROOT / "outputs" / "reports" / "variants" / var_id,
        REPO_ROOT / "outputs" / "figures" / "variants" / var_id,
    ]
    for p in base_paths:
        if p.exists():
            print(" -", p)
        else:
            print(" -", p, "(no existe)")


def main(argv: list[str]) -> None:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print("Uso:")
        print("  python scripts/variantctl.py list")
        print("  python scripts/variantctl.py info VAR_ID")
        sys.exit(0)

    cmd = argv[1]
    if cmd == "list":
        cmd_list()
    elif cmd == "info":
        if len(argv) < 3:
            print("ERROR: falta VAR_ID")
            sys.exit(1)
        cmd_info(argv[2])
    else:
        print("Comando desconocido:", cmd)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
