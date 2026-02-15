#!/usr/bin/env python3

import subprocess
import sys
import shutil
from pathlib import Path
import argparse
import os

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
CONFIG_DIR = ROOT / ".mlops4ofp"
CONFIG_FILE = CONFIG_DIR / "setup.yaml"


# ============================================================
# UTILIDADES
# ============================================================

def abort(msg):
    print(f"\n[ERROR] {msg}")
    sys.exit(1)


def run(cmd, cwd=ROOT):
    print("[CMD]", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def find_python_311():
    candidates = [
        "python3.11",
        "/usr/local/bin/python3.11",
        "/opt/homebrew/bin/python3.11",
    ]
    for c in candidates:
        path = shutil.which(c)
        if path:
            return path
    return None


# ============================================================
# VENV
# ============================================================

def ensure_venv():

    if VENV.exists():
        return

    python311 = find_python_311()
    if not python311:
        abort(
            "No se encontró python3.11.\n"
            "Instálalo antes de continuar."
        )

    print(f"[INFO] Usando Python 3.11: {python311}")
    run([python311, "-m", "venv", str(VENV)])

    pip = VENV / "bin" / "pip"
    python = VENV / "bin" / "python"

    run([str(pip), "install", "--upgrade", "pip"])

    req = ROOT / "requirements.txt"
    if not req.exists():
        abort("requirements.txt no encontrado")

    run([str(pip), "install", "-r", str(req)])

    print("[INFO] Verificando TensorFlow...")
    subprocess.run(
        [str(python), "-c", "import tensorflow as tf; print(tf.__version__)"],
        check=True,
    )

    print("[OK] Entorno virtual creado correctamente")


def ensure_running_in_venv(config_path):

    venv_python = VENV / "bin" / "python"

    if Path(sys.executable).resolve() != venv_python.resolve():
        print("[INFO] Reejecutando dentro de .venv")
        subprocess.run(
            [str(venv_python), __file__, "--config", config_path],
            check=True,
        )
        sys.exit(0)


# ============================================================
# GIT
# ============================================================

def setup_git(cfg):

    git_cfg = cfg.get("git", {})
    mode = git_cfg.get("mode", "none")
    remote_url = git_cfg.get("remote_url")

    # Si no existe repo → crear
    if not (ROOT / ".git").exists():
        print("[INFO] Inicializando repositorio Git")
        run(["git", "init"])

    if mode == "none":
        return

    if mode == "custom":

        if not remote_url:
            abort("git.remote_url obligatorio en modo custom")

        existing = subprocess.run(
            ["git", "remote", "get-url", "publish"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        if existing.returncode == 0:
            print("[INFO] Actualizando remote 'publish'")
            run(["git", "remote", "set-url", "publish", remote_url])
        else:
            print("[INFO] Añadiendo remote 'publish'")
            run(["git", "remote", "add", "publish", remote_url])


# ============================================================
# DVC
# ============================================================

def add_or_update_dvc_remote(venv_python, name, url):

    result = subprocess.run(
        [str(venv_python), "-m", "dvc", "remote", "add", "-d", name, url],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("[INFO] Remote DVC ya existe → actualizando URL")
        run([
            str(venv_python), "-m", "dvc",
            "remote", "modify", name, "url", url
        ])


def setup_dvc(cfg):

    venv_python = VENV / "bin" / "python"

    if not (ROOT / ".dvc").exists():
        print("[INFO] Inicializando DVC")
        run([str(venv_python), "-m", "dvc", "init"])

    dvc_cfg = cfg.get("dvc", {})
    backend = dvc_cfg.get("backend")

    if backend == "local":

        path = ROOT / dvc_cfg.get("path", ".dvc_storage")
        path.mkdir(parents=True, exist_ok=True)

        add_or_update_dvc_remote(venv_python, "storage", str(path))

    elif backend == "dagshub":

        repo = dvc_cfg.get("repo")
        if not repo:
            abort("dvc.repo obligatorio para backend dagshub")

        user = os.environ.get("DAGSHUB_USER")
        token = os.environ.get("DAGSHUB_TOKEN")

        if not user or not token:
            abort(
                "Faltan variables de entorno:\n"
                "export DAGSHUB_USER=...\n"
                "export DAGSHUB_TOKEN=..."
            )

        remote_url = f"https://dagshub.com/{repo}.dvc"

        add_or_update_dvc_remote(venv_python, "storage", remote_url)

        run([str(venv_python), "-m", "dvc", "remote", "modify", "storage", "auth", "basic"])
        run([str(venv_python), "-m", "dvc", "remote", "modify", "storage", "user", user])
        run([str(venv_python), "-m", "dvc", "remote", "modify", "storage", "password", token])

    else:
        abort(f"Backend DVC no soportado: {backend}")


# ============================================================
# MLFLOW
# ============================================================

def setup_mlflow(cfg):

    ml = cfg.get("mlflow", {})

    if not ml.get("enabled", False):
        return

    tracking_uri = ml.get("tracking_uri")
    if not tracking_uri:
        abort("mlflow.tracking_uri obligatorio si enabled=true")

    CONFIG_DIR.mkdir(exist_ok=True)

    env_file = CONFIG_DIR / "env.sh"

    content = [
        "#!/usr/bin/env sh",
        "# Generado automáticamente por setup.py",
        f"export MLFLOW_TRACKING_URI={tracking_uri}",
    ]

    env_file.write_text("\n".join(content))
    env_file.chmod(0o755)

def ensure_minimal_executions_structure():
    base_src = ROOT / "setup" / "executions"
    base_dst = ROOT / "executions"

    base_dst.mkdir(exist_ok=True)

    if not base_src.exists():
        print("[WARN] No existe setup/executions — no se copian base_params")
        return

    for phase_dir in base_src.iterdir():
        if not phase_dir.is_dir():
            continue

        dst_phase = base_dst / phase_dir.name
        dst_phase.mkdir(exist_ok=True)

        for f in phase_dir.iterdir():
            dst_file = dst_phase / f.name
            if not dst_file.exists():
                shutil.copy(f, dst_file)
                print(f"[INFO] Copiado base estático: {dst_file}")

# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    print("====================================")
    print(" MLOps4OFP — Setup definitivo")
    print("====================================")

    ensure_venv()
    ensure_running_in_venv(args.config)

    import yaml

    if CONFIG_FILE.exists():
        abort(
            "El proyecto ya tiene un setup previo.\n"
            "Ejecuta primero: make clean-setup\n"
            "y después vuelve a lanzar make setup."
        )

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        abort(f"No existe {cfg_path}")

    cfg = yaml.safe_load(cfg_path.read_text())

    setup_git(cfg)
    setup_dvc(cfg)
    setup_mlflow(cfg)

    CONFIG_DIR.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(yaml.dump(cfg))
    ensure_minimal_executions_structure()

    print("\n✔ Setup completado correctamente")
    print("Ejecuta ahora: make check-setup")


if __name__ == "__main__":
    main()
