#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

# Ruta raíz del proyecto (dos niveles por encima de este script)
ROOT = Path(__file__).resolve().parents[1]


def main():
    print("=== SETUP_DEV: Inicialización del entorno de desarrollo ===")

    # ---------------------------------------------------------
    # 1. Instalar dependencias desde requirements.txt
    # ---------------------------------------------------------
    print("[SETUP_DEV] Instalando dependencias…")

    req = ROOT / "requirements.txt"
    if req.exists():
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req)])
    else:
        print("[SETUP_DEV] WARNING: requirements.txt no encontrado")

    # ---------------------------------------------------------
    # 2. Inicialización de Git
    # ---------------------------------------------------------
    if not (ROOT / ".git").exists():
        print("[SETUP_DEV] Inicializando Git…")
        subprocess.check_call(["git", "init"], cwd=ROOT)
    else:
        print("[SETUP_DEV] Git ya estaba inicializado.")

    # ---------------------------------------------------------
    # 3. Inicialización de DVC
    # ---------------------------------------------------------
    if not (ROOT / ".dvc").exists():
        print("[SETUP_DEV] Inicializando DVC…")
        subprocess.check_call(["dvc", "init"], cwd=ROOT)
    else:
        print("[SETUP_DEV] DVC ya estaba inicializado.")

    print("[SETUP_DEV] Entorno preparado correctamente.")


if __name__ == "__main__":
    main()

