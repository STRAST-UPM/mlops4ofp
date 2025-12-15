#!/usr/bin/env python3
import shutil
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "01-raw"

def main():
    if len(sys.argv) != 2:
        print("Uso: add_raw_dataset.py <ruta_dataset.csv>")
        sys.exit(1)
    src = Path(sys.argv[1]).resolve()
    if not src.exists():
        print(f"[ERROR] No existe el fichero: {src}")
        sys.exit(1)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dst = RAW_DIR / src.name
    shutil.copy2(src, dst)
    print(f"[ADD_RAW] Copiado dataset a {dst}")

    try:
        subprocess.check_call(["dvc", "add", str(dst)], cwd=ROOT)
        print("[ADD_RAW] Dataset registrado en DVC.")
    except subprocess.CalledProcessError:
        print("[ADD_RAW] WARNING: no se pudo registrar el dataset en DVC (¿DVC inicializado?).")

if __name__ == "__main__":
    main()
