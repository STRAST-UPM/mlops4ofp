#!/usr/bin/env python3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    print("[REPRO] Ejecutando dvc repro explore…")
    subprocess.check_call(["dvc", "repro", "explore"], cwd=ROOT)
