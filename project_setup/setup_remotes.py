#!/usr/bin/env python3
import subprocess
from pathlib import Path

# Ruta raíz del proyecto
ROOT = Path(__file__).resolve().parents[1]


def run(cmd):
    """Ejecuta un comando mostrando la traza."""
    print("[CMD]", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def dvc_remote_exists(name):
    """Devuelve True si el remoto DVC existe."""
    try:
        out = subprocess.check_output(["dvc", "remote", "list"], cwd=ROOT).decode()
        return name in out
    except subprocess.CalledProcessError:
        return False


def main():
    print("=== CONFIGURACIÓN DE REMOTOS ===")

    # ---------------------------------------------------------------------
    # 1. Configurar remoto Git
    # ---------------------------------------------------------------------
    git_url = input("URL remoto Git (ENTER para omitir): ").strip()
    if git_url:
        subprocess.call(["git", "remote", "remove", "origin"], cwd=ROOT)
        run(["git", "remote", "add", "origin", git_url])

    # ---------------------------------------------------------------------
    # 2. Configurar remoto DVC
    # ---------------------------------------------------------------------
    print("[SETUP_REMOTES] Recuerda: si vais a trabajar en LOCAL, usa switch_to_local_remote.py")
    dvc_url = input("URL remoto DVC (ENTER para omitir): ").strip()
    if dvc_url:

        # Borrar remoto antiguo solo si existe
        if dvc_remote_exists("storage"):
            run(["dvc", "remote", "remove", "storage"])
        else:
            print("[INFO] No existía el remoto DVC 'storage' → se creará nuevo")

        # Añadir el remoto
        run(["dvc", "remote", "add", "-f", "storage", dvc_url])

        # Establecer como predeterminado
        run(["dvc", "remote", "default", "storage"])

    print("Para cambiar modos: local / private / public → ver scripts en project_setup/")
    print("[SETUP_REMOTES] Listo.")


if __name__ == "__main__":
    main()
