#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
VENV_PYTHON = VENV / "bin" / "python"
CONFIG_DIR = ROOT / ".mlops4ofp"
CONFIG_FILE = CONFIG_DIR / "setup.yaml"


# --------------------------------------------------
# Utilidades
# --------------------------------------------------

def run(cmd, cwd=ROOT, check=True):
    print("[CMD]", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=check)


def abort(msg):
    print(f"\n[ERROR] {msg}")
    sys.exit(1)


# --------------------------------------------------
# Bootstrap Python
# --------------------------------------------------

def ensure_venv():
    if VENV.exists():
        print("[INFO] .venv ya existe")
        return

    print("[INFO] Creando entorno virtual .venv")
    run([sys.executable, "-m", "venv", ".venv"])

    req = ROOT / "requirements.txt"
    if not req.exists():
        abort("requirements.txt no encontrado")

    pip = VENV / "bin" / "pip"
    print("[INFO] Instalando dependencias")
    run([str(pip), "install", "-r", str(req)])


def ensure_running_in_venv(argv):
    if sys.executable == str(VENV_PYTHON):
        return

    print("[INFO] Reejecutando setup dentro de .venv")
    run([str(VENV_PYTHON), __file__] + argv)
    sys.exit(0)


# --------------------------------------------------
# Validación estructural del setup
# --------------------------------------------------

def validate_cfg(cfg):
    # ---------- DVC ----------
    dvc = cfg.get("dvc", {})
    backend = dvc.get("backend")

    if backend not in ("local", "dagshub"):
        abort(f"Backend DVC no soportado: {backend}")

    if backend == "local":
        if not dvc.get("path"):
            abort("dvc.path obligatorio cuando backend=local")

    if backend == "dagshub":
        if not dvc.get("repo"):
            abort("dvc.repo obligatorio cuando backend=dagshub (formato org/repo)")

    # ---------- MLflow ----------
    ml = cfg.get("mlflow", {})
    if ml.get("enabled", False):
        uri = ml.get("tracking_uri")
        if not uri:
            abort("MLflow habilitado pero falta mlflow.tracking_uri")

        backend_ml = ml.get("backend", "local")
        if backend_ml == "dagshub" and "dagshub.com" not in uri:
            abort("MLflow backend dagshub requiere tracking_uri en dagshub.com")

    # ---------- Git ----------
    git = cfg.get("git", {})
    if git.get("mode") == "custom" and not git.get("remote_url"):
        abort("git.remote_url obligatorio cuando git.mode=custom")


# --------------------------------------------------
# env.sh (MLflow)
# --------------------------------------------------

def create_env_sh(cfg):
    ml = cfg.get("mlflow", {})
    if not ml.get("enabled", False):
        return

    env_file = CONFIG_DIR / "env.sh"
    content = [
        "#!/usr/bin/env sh",
        "# Generado por setup.py — NO editar",
        "",
        f"export MLFLOW_TRACKING_URI={ml['tracking_uri']}",
        "",
    ]
    env_file.write_text("\n".join(content))
    env_file.chmod(0o755)
    print("[INFO] Creado .mlops4ofp/env.sh")


# --------------------------------------------------
# DVC
# --------------------------------------------------

import os

def setup_dvc_remote_dagshub(cfg):
    dvc_cfg = cfg.get("dvc", {})
    repo = dvc_cfg.get("repo")
    if not repo:
        abort("dvc.repo no definido para backend dagshub")

    user = os.environ.get("DAGSHUB_USER")
    token = os.environ.get("DAGSHUB_TOKEN")

    if not user or not token:
        abort(
            "Backend DAGsHub seleccionado pero faltan credenciales.\n"
            "Define las variables de entorno:\n"
            "  export DAGSHUB_USER=...\n"
            "  export DAGSHUB_TOKEN=..."
        )

    remote_url = f"https://dagshub.com/{repo}.dvc"

    print(f"[INFO] Configurando DVC DAGsHub: {remote_url}")

    # Añadir o actualizar remoto
    run(["dvc", "remote", "add", "-d", "storage", remote_url], check=False)
    run(["dvc", "remote", "modify", "storage", "url", remote_url])

    # Autenticación obligatoria
    run(["dvc", "remote", "modify", "storage", "auth", "basic"])
    run(["dvc", "remote", "modify", "storage", "user", user])
    run(["dvc", "remote", "modify", "storage", "password", token])

    print("[OK] DVC DAGsHub configurado con autenticación")



def setup_dvc_remote(cfg):
    dvc = cfg["dvc"]
    backend = dvc["backend"]

    if backend == "local":
        path = Path(dvc["path"])
        path.mkdir(parents=True, exist_ok=True)
        run(["dvc", "remote", "add", "-d", "storage", str(path)], check=False)
        run(["dvc", "remote", "modify", "storage", "url", str(path)], check=False)
        print(f"[INFO] DVC local configurado: {path}")
        return

    elif backend == "dagshub":
        setup_dvc_remote_dagshub(cfg)


# --------------------------------------------------
# Git (remote publish)
# --------------------------------------------------

def setup_git_remote(cfg):
    git = cfg.get("git", {})
    url = git.get("remote_url")
    if not url:
        return

    if not (ROOT / ".git").exists():
        print("[WARN] No es un repo Git, no se configura remote 'publish'")
        return

    res = subprocess.run(
        ["git", "remote", "get-url", "publish"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    if res.returncode == 0:
        run(["git", "remote", "set-url", "publish", url])
        print("[INFO] Actualizado remote 'publish'")
    else:
        run(["git", "remote", "add", "publish", url])
        print("[INFO] Añadido remote 'publish'")


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="MLOps4OFP — Setup del proyecto (una sola vez)"
    )
    parser.add_argument(
        "-c", "--config",
        required=True,
        help="Fichero YAML de configuración (local.yaml, remote.yaml, etc.)",
    )

    args = parser.parse_args()

    print("====================================")
    print(" MLOps4OFP — Setup del proyecto")
    print("====================================")

    ensure_venv()
    ensure_running_in_venv(sys.argv[1:])

    import yaml

    if CONFIG_FILE.exists():
        print("[INFO] El setup ya fue realizado previamente")
        print("Ejecuta make check-setup")
        return

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        abort(f"No existe el fichero: {cfg_path}")

    cfg = yaml.safe_load(cfg_path.read_text())
    if not isinstance(cfg, dict):
        abort("Fichero de configuración inválido")

    validate_cfg(cfg)

    CONFIG_DIR.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(yaml.dump(cfg))

    create_env_sh(cfg)
    setup_dvc_remote(cfg)
    setup_git_remote(cfg)

    print("\n✔ Setup completado correctamente")
    print("Siguiente paso:")
    print("  make check-setup")


if __name__ == "__main__":
    main()
