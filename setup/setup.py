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


def parse_dagshub_repo(url):
    if not url:
        return None
    prefix = "dagshub://"
    if not url.startswith(prefix):
        return None
    value = url[len(prefix):].strip().strip("/")
    return value or None


def normalize_config(cfg):
    cfg = dict(cfg or {})

    git_cfg = dict(cfg.get("git", {}))
    if git_cfg.get("mode") is None:
        git_cfg["mode"] = "custom" if git_cfg.get("remote_url") else "none"
    git_cfg.setdefault("publish_remote_name", "publish")
    cfg["git"] = git_cfg

    dvc_cfg = dict(cfg.get("dvc", {}))
    storage = dvc_cfg.get("storage") if isinstance(dvc_cfg.get("storage"), dict) else {}
    backend = dvc_cfg.get("backend")

    if backend is None:
        if storage.get("type") == "dagshub" or parse_dagshub_repo(storage.get("url")):
            backend = "dagshub"
        elif dvc_cfg.get("path") or (isinstance(storage.get("url"), str) and storage.get("url").startswith("file://")):
            backend = "local"

    if backend == "dagshub" and not dvc_cfg.get("repo"):
        repo = parse_dagshub_repo(storage.get("url"))
        if repo:
            dvc_cfg["repo"] = repo

    if backend == "local" and not dvc_cfg.get("path"):
        storage_url = storage.get("url")
        if isinstance(storage_url, str) and storage_url.startswith("file://"):
            dvc_cfg["path"] = storage_url[len("file://"):]

    if backend is not None:
        dvc_cfg["backend"] = backend
    cfg["dvc"] = dvc_cfg

    ml_cfg = dict(cfg.get("mlflow", {}))
    if ml_cfg.get("enabled") is None:
        ml_cfg["enabled"] = bool(ml_cfg.get("tracking_uri"))
    if ml_cfg.get("backend") is None:
        tracking_uri = ml_cfg.get("tracking_uri", "")
        if isinstance(tracking_uri, str) and tracking_uri:
            ml_cfg["backend"] = "dagshub" if "dagshub.com" in tracking_uri else "local"
    cfg["mlflow"] = ml_cfg

    return cfg


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
        "python",
        "/usr/local/bin/python3.11",
        "/opt/homebrew/bin/python3.11",
    ]
    
    # En Windows, agregar más candidatos comunes
    if sys.platform == 'win32':
        candidates = [
            "python",
            "py",  # Launcher de Python en Windows
            "python3",
            r"C:\Python311\python.exe",
            r"C:\ProgramData\chocolatey\bin\python3.11.EXE",
        ] + candidates
    
    for c in candidates:
        path = shutil.which(c) 
        if path:
            return path
    print("[ERROR] No se encontró python3.11 en el sistema.")
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
    
    # En Windows, usar manejo más robusto debido a problemas con subprocess.run
    if sys.platform == 'win32':
        venv_cmd = [python311, "-m", "venv", str(VENV)]
        print("[CMD]", " ".join(venv_cmd))
        result = subprocess.run(venv_cmd, cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            print("[ERROR] Salida:")
            print(result.stdout)
            print(result.stderr)
            abort(f"Falló creación del venv (código {result.returncode})")
    else:
        # macOS/Linux: usar el método original que ya funciona
        run([python311, "-m", "venv", str(VENV)])

    pip = VENV / "Scripts" / "pip.exe" if sys.platform == 'win32' else VENV / "bin" / "pip"
    python = VENV / "Scripts" / "python.exe" if sys.platform == 'win32' else VENV / "bin" / "python"


    try:
        run([str(pip), "install", "--upgrade", "pip"])
    except subprocess.CalledProcessError:
        print("[INFO] Pip ya está actualizado o no es necesario actualizar.")


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

    venv_python = VENV / "Scripts" / "python.exe" if sys.platform == 'win32' else VENV / "bin" / "python"

     # Verifica si el script está siendo ejecutado dentro del entorno virtual
    if Path(sys.executable).resolve() != venv_python.resolve():
        print("[INFO] Reejecutando dentro de .venv")
        try:
            subprocess.run([str(venv_python), __file__, "--config", config_path], check=True)
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] El comando falló con el siguiente error: {e}")
            sys.exit(1)
        sys.exit(0)


# ============================================================
# GIT
# ============================================================

def setup_git(cfg):

    git_cfg = cfg.get("git", {})
    mode = git_cfg.get("mode")
    remote_url = git_cfg.get("remote_url")
    publish_remote_name = git_cfg.get("publish_remote_name", "publish")

    if mode is None:
        mode = "custom" if remote_url else "none"

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
            ["git", "remote", "get-url", publish_remote_name],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        if existing.returncode == 0:
            print(f"[INFO] Actualizando remote '{publish_remote_name}'")
            run(["git", "remote", "set-url", publish_remote_name, remote_url])
        else:
            print(f"[INFO] Añadiendo remote '{publish_remote_name}'")
            run(["git", "remote", "add", publish_remote_name, remote_url])


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

    venv_python = VENV / "Scripts" / "python.exe" if sys.platform == 'win32' else VENV / "bin" / "python"

    if not (ROOT / ".dvc").exists():
        print("[INFO] Inicializando DVC")
        run([str(venv_python), "-m", "dvc", "init"])

    dvc_cfg = cfg.get("dvc", {})
    backend = dvc_cfg.get("backend")

    legacy_storage = dvc_cfg.get("storage", {}) if isinstance(dvc_cfg.get("storage"), dict) else {}
    legacy_storage_type = legacy_storage.get("type")
    legacy_storage_url = legacy_storage.get("url")

    if backend is None:
        if legacy_storage_type == "dagshub" or parse_dagshub_repo(legacy_storage_url):
            backend = "dagshub"
        elif dvc_cfg.get("path") or (legacy_storage_url and legacy_storage_url.startswith("file://")):
            backend = "local"

    if backend == "local":

        local_path = dvc_cfg.get("path")
        if not local_path and legacy_storage_url and legacy_storage_url.startswith("file://"):
            local_path = legacy_storage_url[len("file://"):]
        path = ROOT / (local_path or ".dvc_storage")
        path.mkdir(parents=True, exist_ok=True)

        add_or_update_dvc_remote(venv_python, "storage", str(path))

    elif backend == "dagshub":

        repo = dvc_cfg.get("repo") or parse_dagshub_repo(legacy_storage_url)
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

    enabled = ml.get("enabled")
    if enabled is None:
        enabled = bool(ml.get("tracking_uri"))

    if not enabled:
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

    raw_cfg = yaml.safe_load(cfg_path.read_text())
    cfg = normalize_config(raw_cfg)

    setup_git(cfg)
    setup_dvc(cfg)
    setup_mlflow(cfg)

    CONFIG_DIR.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(yaml.dump(cfg))
    ensure_minimal_executions_structure()

    print("\n[OK] Setup completado correctamente")
    print("Ejecuta ahora: make check-setup")


if __name__ == "__main__":
    main()
