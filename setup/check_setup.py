#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path
import os
import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG_FILE = ROOT / ".mlops4ofp" / "setup.yaml"


# --------------------------------------------------
# Utilidades
# --------------------------------------------------

def fail(msg):
    print(f"[ERROR] {msg}")
    sys.exit(1)


def ok(msg):
    print(f"[OK] {msg}")


def is_git_repo():
    return (ROOT / ".git").exists()


def run(cmd, check=True):
    try:
        out = subprocess.check_output(
            cmd, cwd=ROOT, stderr=subprocess.STDOUT
        ).decode().strip()
        return out
    except subprocess.CalledProcessError as e:
        if check:
            fail(f"Comando falló: {' '.join(cmd)}\n{e.output.decode()}")
        return None


# --------------------------------------------------
# Checks
# --------------------------------------------------

def check_git(cfg):
    git_cfg = cfg.get("git", {})
    mode = git_cfg.get("mode", "none")

    if mode == "none":
        ok("Git: no requerido por el setup")
        return

    if not is_git_repo():
        fail("Git requerido por el setup, pero este directorio no es un repo Git")

    expected = git_cfg.get("remote_url")
    if not expected:
        fail("git.remote_url no definido en setup.yaml")

    current = run(["git", "remote", "get-url", "origin"], check=False)
    if current == expected:
        ok("Git: remoto origin correcto")
        return

    # Permitir que el repositorio de desarrollo use otro origin siempre que
    # exista un remote 'publish' (configurado por `make setup`) que apunte
    # a la URL esperada. Esto permite desarrollar contra `mlops4ofp` y
    # publicar a un repo distinto.
    publish_url = run(["git", "remote", "get-url", "publish"], check=False)
    if publish_url == expected:
        ok("Git: remote 'publish' correcto (publicaciones irán ahí)")
        return

    # Ninguno coincide: fallamos mostrando la diferencia
    actual = current if current is not None else '<none>'
    fail(
        "Remoto Git no coincide con setup\n"
        f"  esperado: {expected}\n"
        f"  actual:   {actual}"
    )


def check_dvc(cfg):
    dvc_cfg = cfg.get("dvc", {})
    backend = dvc_cfg.get("backend")

    remotes = run(["dvc", "remote", "list"])
    if "storage" not in remotes:
        fail("No existe remoto DVC 'storage'")

    ok("DVC: remoto 'storage' definido")

    if backend == "local":
        path = dvc_cfg.get("path")
        if not path:
            fail("dvc.path no definido en setup.yaml")

        storage = Path(path)
        if not storage.exists():
            fail(f"DVC local: ruta no existe → {path}")
        if not os.access(storage, os.W_OK):
            fail(f"DVC local: sin permisos de escritura → {path}")

        ok("DVC local: ruta accesible y escribible")

    elif backend == "dagshub":
        if "dagshub.com" not in remotes:
            fail("DVC backend dagshub esperado pero no detectado")
        ok("DVC dagshub: remoto configurado")

    elif backend == "gdrive":
        if "gdrive://" not in remotes:
            fail("DVC backend gdrive esperado pero no detectado")
        ok("DVC gdrive: remoto configurado")

    else:
        fail(f"Backend DVC desconocido: {backend}")


def check_mlflow(cfg):
    ml = cfg.get("mlflow", {})
    if not ml.get("enabled", False):
        ok("MLflow: deshabilitado (según setup)")
        return

    uri = ml.get("tracking_uri")
    if not uri:
        fail("MLflow habilitado pero tracking_uri no definido")

    env = ROOT / ".mlops4ofp" / "env.sh"
    if not env.exists():
        fail("MLflow habilitado pero falta .mlops4ofp/env.sh")

    content = env.read_text()
    if f"MLFLOW_TRACKING_URI={uri}" not in content:
        fail("MLFLOW_TRACKING_URI no exportado correctamente")

    ok("MLflow: configuración válida")


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    print("====================================")
    print(" CHECK-SETUP — MLOps4OFP")
    print("====================================")

    if not CFG_FILE.exists():
        fail("No existe .mlops4ofp/setup.yaml (setup no ejecutado)")

    cfg = yaml.safe_load(CFG_FILE.read_text())
    if not isinstance(cfg, dict):
        fail("setup.yaml inválido")

    check_git(cfg)
    check_dvc(cfg)
    check_mlflow(cfg)

    print("\n✔ Setup verificado correctamente")


if __name__ == "__main__":
    main()
