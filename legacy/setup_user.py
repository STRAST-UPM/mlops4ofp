#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

# Ruta raíz del proyecto
ROOT = Path(__file__).resolve().parents[1]


def main():
    print("[SETUP_USER] Instalando dependencias…")

    req = ROOT / "requirements.txt"
    if req.exists():
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req)])
    else:
        print("[SETUP_USER] WARNING: requirements.txt no encontrado")

    print("[SETUP_USER] Listo.")


if __name__ == "__main__":
    main()
