#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path
import os
import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG_FILE = ROOT / ".mlops4ofp" / "setup.yaml"
ENV_FILE = ROOT / ".mlops4ofp" / "env.sh"


# --------------------------------------------------
# Utilidades
# --------------------------------------------------

def fail(msg):
    print(f"[ERROR] {msg}")
    sys.exit(1)


def ok(msg):
    print(f"[OK] {msg}")


def check_venv():
    venv = ROOT / ".venv"
    if not venv.exists():
        fail(".venv no existe (setup incompleto)")
    ok("Entorno virtual .venv presente")


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


def is_git_repo():
    return (ROOT / ".git").exists()


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
        fail("Git requerido por el setup, pero este directorio no es un repositorio Git")

    expected = git_cfg.get("remote_url")
    if not expected:
        fail("git.remote_url no definido en setup.yaml")

    origin = run(["git", "remote", "get-url", "origin"], check=False)
    if origin == expected:
        ok("Git: remoto origin correcto")
        return

    publish = run(["git", "remote", "get-url", "publish"], check=False)
    if publish == expected:
        ok("Git: remoto 'publish' correcto (publicaciones irán ahí)")
        return

    actual = origin if origin else "<none>"
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
        cfg_local = run(["dvc", "config", "--local", "--list"], check=False)

        if not cfg_local:
            fail("No se pudo leer configuración local de DVC")

        if (
            "remote.storage.user" not in cfg_local
            or "remote.storage.password" not in cfg_local
        ):
            fail(
                "DVC DAGsHub configurado pero faltan credenciales locales.\n"
                "Ejecuta 'make setup' con DAGSHUB_USER y DAGSHUB_TOKEN definidos."
            )

        ok("DVC DAGsHub: credenciales locales configuradas")
    else:
            fail(f"Backend DVC no soportado: {backend}")


def check_mlflow(cfg):
    ml = cfg.get("mlflow", {})
    if not ml.get("enabled", False):
        ok("MLflow: deshabilitado (según setup)")
        return

    uri = ml.get("tracking_uri")
    if not uri:
        fail("MLflow habilitado pero tracking_uri no definido")

    if not ENV_FILE.exists():
        fail("MLflow habilitado pero falta .mlops4ofp/env.sh")

    content = ENV_FILE.read_text()
    if f"MLFLOW_TRACKING_URI={uri}" not in content:
        fail("MLFLOW_TRACKING_URI no exportado correctamente en env.sh")

    ok("MLflow: configuración válida")

def check_tensorflow_runtime():
    try:
        import tensorflow as tf
        print(f"[OK] TensorFlow runtime {tf.__version__}")
    except Exception as e:
        fail(f"TensorFlow no funcional: {e}")



# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    print("====================================")
    print(" CHECK-SETUP — MLOps4OFP")
    print("====================================")

    check_venv()

    if not CFG_FILE.exists():
        fail("No existe .mlops4ofp/setup.yaml (setup no ejecutado)")

    cfg = yaml.safe_load(CFG_FILE.read_text())
    if not isinstance(cfg, dict):
        fail("setup.yaml inválido")

    check_git(cfg)
    check_dvc(cfg)
    check_mlflow(cfg)
    check_tensorflow_runtime()

    print("\n✔ Setup verificado correctamente")


if __name__ == "__main__":
    main()
