#!/usr/bin/env python3
import subprocess
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(cmd):
    return subprocess.check_output(cmd, cwd=ROOT, stderr=subprocess.STDOUT).decode()

def safe(cmd):
    try:
        return True, run(cmd)
    except Exception as e:
        return False, str(e)

def main():
    print("=== CHECK REMOTOS DVC ===")

    # ---------------------------
    # Git
    # ---------------------------
    print("\n--- Git ---")
    if not (ROOT / ".git").exists():
        print("ERROR: Git NO está inicializado.")
    else:
        print("OK: Git inicializado.")
        ok, out = safe(["git", "remote", "-v"])
        if ok and out.strip():
            print("OK: Remotos Git configurados:")
            print(out)
        else:
            print("WARNING: No existe remoto Git 'origin'.")

    # ---------------------------
    # DVC
    # ---------------------------
    print("\n--- DVC ---")
    if not (ROOT / ".dvc").exists():
        print("ERROR: DVC no está inicializado.")
        return
    else:
        print("OK: DVC inicializado.")

    ok, out = safe(["dvc", "remote", "list"])
    if not ok:
        print("ERROR: No se pueden listar remotos DVC:", out)
        return

    print("DVC Remotes:")
    print(out)

    if "storage" not in out:
        print("ERROR: Falta remoto 'storage'.")
        return

    # Detectar modo actual
    if "local_dvc_store" in out:
        mode = "local"
        print("→ MODO DETECTADO: LOCAL")
    elif "dagshub.com" in out:
        mode = "dagshub"
        print("→ MODO DETECTADO: DAGSHUB")
    else:
        print("WARNING: remoto desconocido.")
        mode = "unknown"

    # ---------------------------
    # Dagshub: accesibilidad
    # ---------------------------
    if mode == "dagshub":
        print("\n--- Acceso a DAGsHub ---")

        try:
            r = requests.get("https://dagshub.com", timeout=3)
            print("OK: Dagshub accesible (HTTP {}).".format(r.status_code))
        except:
            print("ERROR: No se puede contactar con dagshub.com (network issue).")
            return

        # Probar push dry-run
        ok, out = safe(["dvc", "push", "--dry-run"])
        if ok:
            print("OK: Acceso al remoto DVC comprobado.")
        else:
            print("ERROR: Fallo de acceso al remoto DVC.")
            print(out)
            print("\nPosibles causas:")
            print("  - Token incorrecto")
            print("  - Token no configurado")
            print("  - Repo privado sin credenciales")
            print("  - URL de remoto incorrecta")
            return

    print("\n[CHECK] Remotos configurados correctamente.")

if __name__ == "__main__":
    main()
